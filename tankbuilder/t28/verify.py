"""Check the exported GLB, including actual belt UV direction, wheel axes and three turret hierarchies."""
import argparse
import json
from pathlib import Path

import numpy as np

from ..modelrig import Model
from .source import SOURCE_SHA


def check(project):
    m = Model(project / 'model.glb')
    rig = json.loads((project / 'rig.json').read_text())
    nodes, parent = m.g.nodes, m.parents()
    by_name = {n.name: i for i, n in enumerate(nodes)}
    assert len(by_name) == len(nodes) and rig['sourceSha256'] == SOURCE_SHA
    bounds = [m.bounds(i) for i, n in enumerate(nodes) if n.mesh is not None]
    extent = np.max([b[1] for b in bounds], axis=0) - np.min([b[0] for b in bounds], axis=0)
    assert np.allclose(extent, [2.87, 2.82, 7.44], atol=.006), extent
    wheels = sorted(rig['wheels'], key=lambda w: w['node'])
    assert len(wheels) == len({w['node'] for w in wheels}) == 36
    assert len([n for n in nodes if n.name.startswith('Bogie_') and n.mesh is not None]) == 12
    assert {w['wheelKind'] for w in wheels[28:]} == {'road'}
    assert np.ptp([w['radius'] for w in wheels if w['roadWheel']]) < .0001
    for w in wheels:
        i = w['node']
        assert by_name[w['name']] == i and nodes[i].mesh is not None
        assert np.allclose(m.translation(i), w['center'], atol=.0001)
        if w['roadWheel']:
            assert parent[i] == w['suspensionNode']
        lo, hi = m.bounds(i)
        assert np.allclose((lo + hi)[1:] / 2, w['center'][1:], atol=.02)
    materials, periods = [], []
    for side in ('left', 'right'):
        sw = [w for w in wheels if w['side'] == side]
        road = [w for w in sw if w['roadWheel']]
        assert sorted(w['wheelKind'] for w in sw) == sorted(['road']*12 + ['return']*4 + ['drive', 'idler'])
        assert np.all(np.diff([w['center'][2] for w in road]) > 0)
        node = nodes[by_name['track_' + side[0]]]
        skin = m.g.skins[node.skin]
        assert skin.joints == [by_name['Hull'], *[w['suspensionNode'] for w in road]]
        p, = m.g.meshes[node.mesh].primitives
        weights, joints = [m.array(getattr(p.attributes, k)) for k in ('WEIGHTS_0', 'JOINTS_0')]
        assert max(abs(weights.sum(1) - 1)) < .00001
        assert set(joints[weights > .03].tolist()) == set(range(13))
        tris = m.array(p.indices).reshape(-1, 3)
        v = m.array(p.attributes.POSITION)[tris]
        uv = m.array(p.attributes.TEXCOORD_0)[tris]
        # Compare vertices of the same face to avoid UV seams between individual track plates.
        dz, dv = np.diff(v[:, :, 2]), np.diff(uv[:, :, 1])
        lower = ((v[:, :, 1].max(1) < .035) & (abs(v[:, :, 2]).max(1) < 2))[:, None]
        valid = lower & (abs(dz) > .03) & (abs(dv) > .03) & (abs(dv) < 1)
        assert valid.sum() > 100
        period = dz[valid] / dv[valid]
        assert np.allclose(period, rig['trackLoopMeters'], rtol=.028)
        periods.append(float(np.median(period)))
        materials.append(p.material)
    assert len(set(materials)) == 2
    yaw, pitch, recoil = rig['turret']['node'], rig['gun']['node'], rig['gun']['recoilNode']
    assert parent[yaw] == by_name['Hull'] and parent[pitch] == yaw and parent[recoil] == pitch
    assert parent[rig['muzzle']['node']] == recoil and parent[rig['coaxMuzzle']['node']] == pitch
    assert m.translation(rig['muzzle']['node'])[2] < m.translation(pitch)[2] - .35
    anchor = by_name['T28_AuxRig']
    assert parent[anchor] == by_name['Hull']
    assert len(rig['auxiliaryTurrets']) == 2
    for aux in rig['auxiliaryTurrets']:
        y, p, t = (aux[k] for k in ('yawNode', 'pitchNode', 'muzzleNode'))
        assert parent[y] == anchor and parent[p] == y and parent[t] == p
        assert nodes[y].mesh is not None and nodes[p].mesh is not None
        assert m.translation(t)[2] < m.translation(p)[2] < m.translation(y)[2] < m.translation(yaw)[2]
        assert (m.translation(y)[0] < -.4) if aux['side'] == 'l' else (m.translation(y)[0] > .4)
    assert {nodes[i].name for i in rig['markings'].values()} == {'Red_star_l', 'Red_star_r'}
    assert all(parent[i] == yaw for i in rig['markings'].values())
    maps = {m.g.textures[mat.normalTexture.index].source for mat in m.g.materials if mat.normalTexture}
    assert len(maps) == 5 and all((mat.emissiveFactor or [0, 0, 0]) == [0, 0, 0] for mat in m.g.materials)
    assert [(a.name, len(a.channels)) for a in m.g.animations] == [
        ('Road_and_return_wheels', 36), ('Bogie_contact', 24), ('Three_turrets_and_recoil', 7)]
    return dict(boundsMetres=extent.tolist(), rotatingWheels=36, contacts=24, linkedTurrets=3,
                stars=2, originalNormalMaps=len(maps), lowerBeltTextureMetres=periods)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    print(json.dumps(check(parser.parse_args().project), indent=2))
