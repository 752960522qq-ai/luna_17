"""Check the final, re-opened GLB. The runtime prefab checks live in integrate.inspect."""
import json
from pathlib import Path
import numpy as np
from ..modelrig import Model

def check(project):
    rig = json.loads((project / 'rig.json').read_text())
    g = Model(project / 'model.glb')
    nodes = g.g.nodes
    parents = g.parents()
    def world(i):
        t = np.array(nodes[i].translation or [0, 0, 0], dtype=float)
        return t if i not in parents else t + world(parents[i])

    def meshes(i):
        return g.g.meshes[nodes[i].mesh].primitives

    points = []
    for i, n in enumerate(nodes):
        if n.mesh is not None:
            points.extend((g.array(p.attributes.POSITION) + world(i) for p in meshes(i)))
    points = np.concatenate(points)
    actual = np.ptp(points, axis=0)
    hull = next((i for i, n in enumerate(nodes) if n.name == 'Hull'))
    hull_length = float(np.ptp(np.concatenate([g.array(p.attributes.POSITION)[:, 2] for p in meshes(hull)])))
    assert np.allclose([actual[0], actual[1], hull_length], [2.91, 2.44, 5.38], atol=0.012)
    assert 0 < actual[2] - hull_length < 0.2  # the muzzle extends beyond the front mudguards
    wheels = rig['wheels']
    assert len(wheels) == len({w['node'] for w in wheels}) == 22
    assert {x['name'] for x in wheels} == {n.name for n in nodes if n.name.startswith('wheel_')}
    surface = []
    for side in ('left', 'right'):
        ws = [w for w in wheels if w['side'] == side]
        assert sorted((w['wheelKind'] for w in ws)) == sorted(['road'] * 6 + ['return'] * 3 + ['drive', 'idler'])
        road = [w for w in ws if w['roadWheel']]
        assert np.all(np.diff([w['center'][2] for w in road]) > 0)
        for w in ws:
            assert np.allclose(world(w['node']), w['center'])
            assert w['sourceFaces'] > 75
            if w['roadWheel']:
                assert parents[w['node']] == w['suspensionNode']
        track = next((i for i, n in enumerate(nodes) if n.name == 'track_' + side[0]))
        skin = g.g.skins[nodes[track].skin]
        assert skin.joints[1:] == [w['suspensionNode'] for w in road]
        p, = meshes(track)
        v, weights, joints, uv = [g.array(getattr(p.attributes, a)) for a in (
            'POSITION',
            'WEIGHTS_0',
            'JOINTS_0',
            'TEXCOORD_0'
        )]
        assert np.max(abs(weights.sum(1) - 1)) < 1e-05
        assert set(joints[weights > 0.03].tolist()) == set(range(7))
        assert 0 <= v[:, 1].min() < 0.008
        low = (v[:, 1] < 0.011) & (abs(v[:, 2]) < 0.8) & (uv[:, 0] > 0.5)
        assert low.sum() > 5
        u = uv[low, 1]
        z = v[low, 2]
        assert abs(np.polyfit(z, u, 1)[0] * rig['trackLoopMeters'] - 1) < 0.03
        surface.append(p.material)
    assert surface[0] != surface[1]
    turret, gun, recoil = (rig['turret']['node'], rig['gun']['node'], rig['gun']['recoilNode'])
    assert parents[gun] == turret and parents[recoil] == gun
    assert parents[rig['muzzle']['node']] == recoil and parents[rig['coaxMuzzle']['node']] == gun
    assert world(rig['muzzle']['node'])[2] < world(gun)[2] - 1.0
    assert len(rig['markings']) == 4 and len(g.g.animations) == 3
    return {'boundsMetresXYZ':actual.tolist(),'hullLengthMetres':hull_length,'wheelAxes':22,'contactAnchors':12,
            'independentTrackMaterials':2,'paintedCrosses':4,'motionClips':3}

if __name__ == '__main__':
    import sys
    print(json.dumps(check(Path(sys.argv[1])), indent=2))
