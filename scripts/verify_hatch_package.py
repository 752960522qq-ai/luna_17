#!/usr/bin/env python3
"""Validate runtime geometry, textures, collider ground plane and revision data."""
import argparse
import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from hatch.standalone.integrate import validate_pack


def inspect(path):
    validated = validate_pack(path)
    with zipfile.ZipFile(path) as archive:
        data = archive.read('runtime.bin')
        rig = json.loads(archive.read('rig.json'))
        weapon = json.loads(archive.read('weapon.json'))
    count, images = struct.unpack_from('<II', data, 16)
    offset = 616
    nodes, geometry = [], []
    triangles = maximum = 0
    for _ in range(count):
        record = struct.unpack_from('<iI10fIIii4f96s', data, offset)
        offset += 176
        vertices, indices = record[12:14]
        points = np.frombuffer(data, '<f4', vertices * 8, offset).reshape(-1, 8)
        offset += vertices * 32
        faces = np.frombuffer(data, '<u4', indices, offset)
        offset += indices * 4
        assert -1 <= record[0] < count and vertices <= 65535
        assert indices % 3 == 0 and np.isfinite(points).all()
        assert not indices or faces.max() < vertices
        nodes.append(dict(name=record[-1].split(b'\0')[0].decode(),
                          parent=record[0], flags=record[1], position=np.array(record[2:5])))
        geometry.append(points)
        triangles += indices // 3
        maximum = max(maximum, vertices)
    world = {}
    def position(index, visiting):
        if index in world:
            return world[index]
        assert index not in visiting, 'Cyclic hierarchy'
        visiting = visiting | {index}
        node = nodes[index]
        world[index] = node['position'] + (position(node['parent'], visiting) if node['parent'] >= 0 else 0)
        return world[index]
    tracks = []
    for index, points in enumerate(geometry):
        position(index, set())
        parent = nodes[index]['parent']
        if len(points) and parent >= 0 and nodes[parent]['flags'] & 64:
            tracks.append(float((points[:, :3] + world[index])[:, 1].min()))
    for _ in range(images):
        size, = struct.unpack_from('<I', data, offset)
        offset += 4
        with Image.open(io.BytesIO(data[offset:offset + size])) as image:
            image.load()
            assert max(image.size) <= 4096
        offset += size
    assert offset == len(data) and len(tracks) == 2 and all(abs(y) < 1e-6 for y in tracks)
    box = rig['colliders']['hull']
    assert abs(box['center'][1] - box['size'][1] / 2) < 1e-6
    result = dict(runtime_nodes=count, images=images, triangles=triangles,
                  max_mesh_vertices=maximum, track_minimum_y=tracks,
                  hull_support_bottom_y=0,
                  road_wheels=sum(bool(n['flags'] & 16) for n in nodes),
                  track_renderers=sum(bool(n['flags'] & 64) for n in nodes),
                  android_device_test=False, unity_gpu_test=False)
    if validated['id'] == 'Matilda_III':
        assert weapon['shells']['AP']['penetrationMm'] == 89
        assert struct.unpack_from('<i', data, 348)[0] == 89
        result['ap_penetration_mm'] = 89
    elif validated['id'] == 'T54_1949':
        names = {n['name']: i for i, n in enumerate(nodes)}
        for name in ['details_73_turret', 'antenna_79']:
            assert nodes[names[name]]['parent'] == names['Turret']
        assert nodes[names['details_73']]['parent'] == names['Hull']
        result['turret_attachment_parentage_valid'] = True
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.package)
    args.report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
