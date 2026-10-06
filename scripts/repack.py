#!/usr/bin/env python3
"""Binary manifest editing and ZIP primitives shared by the Hatch build."""
import argparse
import io
import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

NO_INDEX = 0xffffffff

def length8(data, at):
    value = data[at]
    return (((value & 127) << 8) | data[at+1], at+2) if value & 128 else (value, at+1)

def length16(data, at):
    value, = struct.unpack_from('<H', data, at)
    return (((value & 32767) << 16) | struct.unpack_from('<H', data, at+2)[0], at+4) if value & 32768 else (value, at+2)

def encode8(n):
    if n > 32767:
        raise ValueError('String too long')
    return bytes([128 | (n >> 8), n & 255]) if n > 127 else bytes([n])

def strings(chunk):
    _, header, _, count, styles, flags, start, style_start = struct.unpack_from('<HH6I', chunk)
    offsets = struct.unpack_from('<' + 'I'*count, chunk, header)
    decoded = []
    for offset in offsets:
        pos = start + offset
        if flags & 0x100:
            _, pos = length8(chunk, pos)
            size, pos = length8(chunk, pos)
            decoded.append(chunk[pos:pos+size].decode('utf8'))
        else:
            size, pos = length16(chunk, pos)
            decoded.append(chunk[pos:pos+size*2].decode('utf-16le'))
    return decoded

def extend_pool(chunk, added):
    kind, header, size, count, styles, flags, start, style_start = struct.unpack_from('<HH6I', chunk)
    old_offsets = list(struct.unpack_from('<'+'I'*count, chunk, header))
    style_offsets = chunk[header+count*4:header+(count+styles)*4]
    text = bytearray(chunk[start:style_start or size])
    style_data = chunk[style_start:] if style_start else b''
    for s in added:
        old_offsets.append(len(text))
        utf16 = s.encode('utf-16le')
        if flags & 0x100:
            utf8 = s.encode('utf8')
            text += encode8(len(utf16)//2) + encode8(len(utf8)) + utf8 + b'\0'
        else:
            text += struct.pack('<H', len(utf16)//2) + utf16 + b'\0\0'
    text += b'\0' * (-len(text) % 4)
    new_count = count + len(added)
    new_start = header + (new_count + styles)*4
    new_style_start = new_start+len(text) if style_start else 0
    new_size = new_start + len(text) + len(style_data)
    # Appended strings are attribute values, so the resource map stays intact.
    return (struct.pack('<HH6I',kind,header,new_size,new_count,styles,flags & ~1,new_start,new_style_start)
            + chunk[28:header] + struct.pack('<'+'I'*new_count,*old_offsets)
            + style_offsets + text + style_data)

def patch_manifest(data, launcher="com.luna17.aot.ModActivity", label="坦无敌3000", old_launchers=("com.unity3d.player.UnityPlayerActivity",)):
    kind, header, total = struct.unpack_from('<HHI',data)
    if kind != 3 or total != len(data):
        raise ValueError('Invalid binary AndroidManifest.xml')
    chunks = []
    pos = header
    while pos < total:
        typ, _, size = struct.unpack_from('<HHI',data,pos)
        if size < 8 or pos+size > total:
            raise ValueError('Invalid XML chunk')
        chunks.append((typ,bytearray(data[pos:pos+size])))
        pos += size
    pool = next(c for typ,c in chunks if typ == 1)
    names = strings(pool)
    added = [launcher, label]
    activity_index, label_index = len(names), len(names)+1
    names.extend(added)
    out = []; skipping = 0; activity_changed = False; split_removed = 0
    for typ,c in chunks:
        if typ == 1:
            out.append(extend_pool(c,added)); continue
        if skipping:
            if typ == 0x102: skipping += 1
            elif typ == 0x103: skipping -= 1
            continue
        if typ != 0x102:
            out.append(c); continue
        node_header = struct.unpack_from('<H',c,2)[0]
        tag = names[struct.unpack_from('<I',c,node_header+4)[0]]
        attr_start, attr_size, count = struct.unpack_from('<3H',c,node_header+8)
        start = node_header + attr_start
        attrs = [bytearray(c[start+i*attr_size:start+(i+1)*attr_size]) for i in range(count)]
        def value(a):
            raw = struct.unpack_from('<I',a,8)[0]
            return names[raw] if raw != NO_INDEX else (names[struct.unpack_from('<I',a,16)[0]] if a[15] == 3 else None)
        by_name = {names[struct.unpack_from('<I',a,4)[0]]:a for a in attrs}
        if tag == 'meta-data' and 'name' in by_name and value(by_name['name']) in {
            'com.android.vending.splits.required','com.android.vending.splits'}:
            skipping = 1; split_removed += 1; continue
        if tag == 'manifest':
            attrs = [a for a in attrs if names[struct.unpack_from('<I',a,4)[0]] not in {'requiredSplitTypes','splitTypes','isSplitRequired'}]
        if tag == 'activity' and 'name' in by_name and value(by_name['name']) in old_launchers:
            a = by_name['name']; struct.pack_into('<I',a,8,activity_index); a[15]=3; struct.pack_into('<I',a,16,activity_index)
            activity_changed = True
        if tag == 'application' or (tag == 'activity' and activity_changed and 'name' in by_name and value(by_name['name']) == added[0]):
            if 'label' in by_name:
                a = by_name['label']; struct.pack_into('<I',a,8,label_index); a[15]=3; struct.pack_into('<I',a,16,label_index)
        new = c[:start] + b''.join(attrs) + c[start+count*attr_size:]
        struct.pack_into('<I',new,4,len(new)); struct.pack_into('<H',new,node_header+12,len(attrs))
        out.append(new)
    if not activity_changed:
        raise ValueError('Unity launcher activity was not found')
    body = b''.join(out)
    return data[:4]+struct.pack('<I',header+len(body))+data[8:header]+body

def write_entry(out, name, content, compression=zipfile.ZIP_DEFLATED):
    info = zipfile.ZipInfo(name, (2026,10,4,0,0,0))
    info.compress_type = compression
    info.external_attr = 0o644 << 16
    if compression == zipfile.ZIP_STORED:
        position = out.fp.tell() + 30 + len(name.encode('utf8'))
        if position % 4:
            padding = -(position+4) % 4
            info.extra = struct.pack('<HH',0xd935,padding) + b'\0'*padding
    out.writestr(info,content,compresslevel=6)
