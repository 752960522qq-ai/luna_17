"""Restore release packages split for repository transport and verify their hashes."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
release=root/'releases/texture-fix-20261011'
manifest=json.loads((release/'packages.json').read_text())
for item in manifest['packages']:
 target=release/item['filename'];data=b''.join((root/p['path']).read_bytes() for p in item['parts'])
 if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Package checksum mismatch: '+item['filename'])
 target.write_bytes(data);print(target)
