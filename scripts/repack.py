#!/usr/bin/env python3
"""Merge the user's APKS, add the mod DEX/library, and edit only binary XML.

The game APK, game libraries, metadata and signing key are never committed.
"""
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

def patch_manifest(data):
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
    added = ['com.luna17.aot.ModActivity', '坦无敌3000']
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
        if tag == 'activity' and 'name' in by_name and value(by_name['name']) == 'com.unity3d.player.UnityPlayerActivity':
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

def repack(apks, dex, native, output, profile_path=None,unity_data=None,hatch_packages=None):
    profile=json.loads(Path(profile_path or Path(__file__).resolve().parents[1]/'profiles/attack-on-tank-5.1.0.json').read_text())
    replacement=None
    if unity_data:
        unity_data=Path(unity_data);replacement=unity_data.read_bytes();asset_report=json.loads((unity_data.parent/'asset_report.json').read_text())
        if asset_report['input_sha256']!=profile['unity_data_sha256'] or asset_report['output_sha256']!=hashlib.sha256(replacement).hexdigest() or asset_report.get('adapter')!='aot-5.1.0-arm64-v1':raise ValueError('Derived Unity bundle or its source fingerprint does not match')
    with zipfile.ZipFile(apks) as bundle:
        with zipfile.ZipFile(io.BytesIO(bundle.read('base.apk'))) as base:
            metadata=base.read('assets/bin/Data/Managed/Metadata/global-metadata.dat')
            if hashlib.sha256(metadata).hexdigest()!=profile['metadata_sha256']:
                raise ValueError('Unsupported game metadata; use the original 5.1.0 APKS')
            manifest = patch_manifest(base.read('AndroidManifest.xml'))
            if 'lib/arm64-v8a/libaotmod.so' in base.namelist():
                raise ValueError('Already modified input')
            if 'lib/arm64-v8a/libil2cpp.so' in base.namelist() and hashlib.sha256(base.read('lib/arm64-v8a/libil2cpp.so')).hexdigest()!=profile['libil2cpp_sha256']:
                raise ValueError('Unsupported libil2cpp.so')
            dex_indices = [int(m.group(1) or 1) for name in base.namelist()
                           if (m := re.fullmatch(r'classes(\d*)\.dex',name))]
            with zipfile.ZipFile(output,'w',allowZip64=False) as out:
                written = set()
                for info in base.infolist():
                    name = info.filename
                    if name == 'stamp-cert-sha256' or name == 'META-INF/MANIFEST.MF' or re.match(r'META-INF/[^/]+\.(?:RSA|DSA|EC|SF)$',name,re.I):
                        continue
                    content = manifest if name == 'AndroidManifest.xml' else replacement if replacement is not None and name=='assets/bin/Data/data.unity3d' else base.read(name)
                    write_entry(out,name,content,info.compress_type); written.add(name)
                arm_found = 'lib/arm64-v8a/libil2cpp.so' in written
                for entry in bundle.namelist():
                    if not entry.endswith('.apk') or entry == 'base.apk': continue
                    with zipfile.ZipFile(io.BytesIO(bundle.read(entry))) as split:
                        for info in split.infolist():
                            if not info.filename.startswith('lib/arm64-v8a/') or info.is_dir(): continue
                            if info.filename not in written:
                                content=split.read(info.filename)
                                if info.filename.endswith('/libil2cpp.so') and hashlib.sha256(content).hexdigest()!=profile['libil2cpp_sha256']:
                                    raise ValueError('Unsupported libil2cpp.so; the native offsets are version-specific')
                                write_entry(out,info.filename,content); written.add(info.filename); arm_found=True
                if not arm_found: raise ValueError('ARM64 split is missing')
                write_entry(out,f'classes{max(dex_indices)+1}.dex',Path(dex).read_bytes())
                write_entry(out,'lib/arm64-v8a/libaotmod.so',Path(native).read_bytes())
                if hatch_packages:
                    from hatch.standalone.integrate import validate_pack
                    mods = [validate_pack(Path(path)) for path in hatch_packages]
                    if len(mods)>16 or len({m['id'] for m in mods})!=len(mods):
                        raise ValueError('Built-in tank count/identity mismatch')
                    catalog=[]
                    for mod in mods:
                        write_entry(out,'assets/Hatch/mods/'+mod['id']+'.hatch',mod['path'].read_bytes(),zipfile.ZIP_STORED)
                        catalog.append({key:mod[key] for key in ['id','name','sha256','size','runtime_bytes']})
                    write_entry(out,'assets/Hatch/catalog.json',json.dumps({'format':1,'mods':catalog},ensure_ascii=False,indent=2).encode())

    return Path(output)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apks',required=True); parser.add_argument('--dex',required=True)
    parser.add_argument('--native',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=repack(args.apks,args.dex,args.native,args.output)
    print(f'Unsigned APK: {output} ({output.stat().st_size:,} bytes)')

