"""Shared .hatch validation and packaging primitives for build tools."""
import hashlib
import json
import math
import re
import struct
import zipfile
from pathlib import Path

MAX_BYTES = 256 * 1024 * 1024
CORE_ID = 'tankinvincible3000'

def validate(path):
    path = Path(path)
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError('Package size limit')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) > 16 or len(names) != len(set(names)) or sum(e.file_size for e in entries) > MAX_BYTES or any(e.is_dir() or '/' in e.filename or '\\' in e.filename or '..' in e.filename for e in entries):
            raise ValueError('Invalid archive structure')
        if archive.getinfo('hatch.json').file_size > 16384:
            raise ValueError('Manifest size limit')
        doc = json.loads(archive.read('hatch.json'))
        if doc['format'] not in (1, 2) or doc['loader'] != 'Hatch' or doc['loader_version'] not in ('0.1', '0.2', '0.3') or doc['game_version'] != '5.1.0' or doc['abi'] != 'arm64-v8a':
            raise ValueError('Unsupported game or loader')
        if not re.fullmatch('[A-Za-z0-9_-]{1,48}', doc['id']):
            raise ValueError('Invalid package ID')
        kind = doc.get('type', 'tank')
        if kind == 'module':
            if doc['format'] != 2 or doc['id'] != CORE_ID or doc['version'] != '1.0' or doc['api_version'] != 2 or doc['entry_class'] != 'com.luna17.aot.TankInvincibleModule':
                raise ValueError('Unsupported prerequisite module')
            payloads = [('module.dex', 'dex'), ('module.so', 'native')]
        elif kind == 'tank' and doc['id'] != CORE_ID:
            payloads = [('runtime.bin', 'runtime')]
        else:
            raise ValueError('Invalid package type')
        for entry, prefix in payloads:
            content = archive.read(entry)
            if len(content) != doc[prefix + '_bytes'] or hashlib.sha256(content).hexdigest() != doc[prefix + '_sha256']:
                raise ValueError(entry + ' checksum mismatch')
        if kind == 'tank':
            content = archive.read('runtime.bin')
            magic, version, size, nodes, images = struct.unpack_from('<8sIIII', content)
            if magic != b'HATCH01\0' or version != 1 or size != len(content) or not 4 <= nodes <= 2048 or images > 128 or content[24:88].split(b'\0')[0].decode('ascii') != doc['id']:
                raise ValueError('Runtime header mismatch')
        for name, version in doc.get('requires', {}).items():
            if name != CORE_ID or version != '1.0':
                raise ValueError('Unsupported dependency: ' + name)
        if 'magazine' in doc:
            mag = doc['magazine']; cap, interval, reload = mag['capacity'], mag['shotInterval'], mag['reloadTime']
            if type(cap) is not int or not 2 <= cap <= 200 or type(interval) not in (int,float) or type(reload) not in (int,float) or not math.isfinite(interval) or not .03 <= interval <= 60 or not math.isfinite(reload) or not interval <= reload <= 300:
                raise ValueError('Invalid magazine parameters')
    return doc

def pack_module(dex, native, output):
    dex, native, output = Path(dex), Path(native), Path(output)
    content = {'module.dex': dex.read_bytes(), 'module.so': native.read_bytes()}
    doc = dict(format=2, loader='Hatch', loader_version='0.3', game_version='5.1.0', abi='arm64-v8a', id=CORE_ID, name='坦无敌3000', type='module', version='1.0', api_version=2, entry_class='com.luna17.aot.TankInvincibleModule')
    for entry, prefix in [('module.dex','dex'), ('module.so','native')]:
        doc[prefix+'_sha256'] = hashlib.sha256(content[entry]).hexdigest()
        doc[prefix+'_bytes'] = len(content[entry])
    output.parent.mkdir(parents=True,exist_ok=True)
    temp = output.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('hatch.json', json.dumps(doc, ensure_ascii=False, indent=2))
            for name, data in content.items(): archive.writestr(name, data)
        validate(temp)
        temp.replace(output)
    finally: temp.unlink(missing_ok=True)
    return doc
