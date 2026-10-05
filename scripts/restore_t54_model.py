#!/usr/bin/env python3
"""Restore the exact GLB from repository parts; never access the network."""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

def restore(path):
    manifest_path = path.with_name(path.name + '.parts.json')
    manifest = json.loads(manifest_path.read_text())
    if manifest['format'] != 1: raise ValueError('Unsupported part format')
    if path.exists():
        if path.stat().st_size == manifest['size_bytes'] and hashlib.sha256(path.read_bytes()).hexdigest() == manifest['sha256']:
            return path
        raise ValueError('Existing model differs; refusing to overwrite')
    fd, temporary = tempfile.mkstemp(prefix='.model-restore-', dir=path.parent)
    try:
        h = hashlib.sha256(); total = 0
        with os.fdopen(fd, 'wb') as output:
            for part in manifest['parts']:
                name = part['file']
                if Path(name).name != name: raise ValueError('Unsafe model part path')
                data = (path.parent / name).read_bytes()
                if len(data) != part['size_bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
                    raise ValueError('Model part fingerprint differs: ' + name)
                output.write(data); h.update(data); total += len(data)
        if total != manifest['size_bytes'] or h.hexdigest() != manifest['sha256']:
            raise ValueError('Restored model fingerprint differs')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return path

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, default=Path(__file__).resolve().parents[1] / 'tanks/T54_1949/model.glb')
    print(restore(p.parse_args().model))
