#!/usr/bin/env python3
"""Scoped visual correction for Grille's near-black, untextured metal parts.

These two diffuse swatches lose their detail in Hatch's diffuse-only material
adapter. This is an asset palette adjustment, not a global gamma conversion.
Keep black openings, camouflage, rubber, geometry, UVs and embedded images.
"""
import argparse
import json
import struct
from pathlib import Path

# Original authored factors remain here for an auditable, reversible change.
SWATCHES = {
    'blinn19': ([0.04999488099145083, 0.04372366082271345, 0.04372366082271345, 1.0],
                [0.24, 0.22, 0.22, 1.0]),
    'blinn20': ([0.04825934533322086, 0.043788264330772014, 0.043788264330772014, 1.0],
                [0.23, 0.22, 0.22, 1.0]),
}

def correct(data):
    if data[:4] != b'glTF' or struct.unpack_from('<I', data, 4)[0] != 2:
        raise ValueError('Expected GLB 2')
    length, kind = struct.unpack_from('<II', data, 12)
    if kind != 0x4e4f534a:
        raise ValueError('Missing GLB JSON chunk')
    doc = json.loads(data[20:20+length])
    found = set()
    for material in doc['materials']:
        name = material.get('name')
        if name not in SWATCHES:
            continue
        pbr = material['pbrMetallicRoughness']
        before, after = SWATCHES[name]
        if pbr.get('baseColorTexture') is not None or pbr.get('baseColorFactor') not in (before, after):
            raise ValueError('Unexpected material baseline: '+name)
        pbr['baseColorFactor'] = after
        found.add(name)
    if found != set(SWATCHES):
        raise ValueError('Expected both Grille metal materials')
    payload = json.dumps(doc, separators=(',', ':'), ensure_ascii=False).encode()
    if len(payload) > length:
        raise ValueError('Correction exceeds original JSON chunk')
    # Preserve BIN chunk offsets and every geometry/texture byte exactly.
    return data[:20] + payload.ljust(length, b' ') + data[20+length:]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    args = parser.parse_args()
    args.model.write_bytes(correct(args.model.read_bytes()))
