"""Build only the vehicle in the user's mod workspace; does not build an APK."""
import argparse, json
from pathlib import Path
import numpy as np
from pygltflib import Scene
from ..bt7.export import Output, quat
from ..panzer2f.build import skin_track
from .markings import apply, turret_mark, painted
from .source import ID, INNER, CREDIT, AXLES, B, T, ROOF, read, parts, rings, fixed, wheel
from .track import belt, texture

def build(src,out):
    out.mkdir(exist_ok=True, parents=True)
    h, t = read(src)
    g = Output(None, 'Pz3F', texture)
    g.pos = []
    root = g.node('Hull')
    g.g.scenes = [Scene(nodes=[root])]
    g.g.scene = 0
    hp, fh = fixed(h)
    g.mesh(root, hp)
    pivot = T([97.49, 125.93, 10.69])
    tur = g.node('Turret', root, B(ROOF))
    gun = g.node('Gun', tur, pivot)
    rec = g.node('Barrel_Recoil', gun, pivot)
    t = t[t[:, :, 2].min(1) > 7.18]
    c = t.mean(1)
    barrel = (c[:, 1] < 121.325) & (np.linalg.norm(c[:, [0, 2]] - [97.49, 10.69], axis=1) < 1.3)
    mantlet = (c[:, 1] < 125.84) & (c[:, 2] > 8.04) & ~barrel
    shell = t[~mantlet & ~barrel]
    g.mesh(tur, parts(T(shell), 'panels'))
    g.mesh(gun, parts(T(t[mantlet]), 'panzer_grau'))
    muzzle = T([97.49, 109.19, 10.69])
    coax = T([94.29, 123.25, 11.11])
    bar = t[barrel & (t[:, :, 1].max(1) > 109.191)]
    # The tabletop print exaggerated radial dimensions for strength. Preserve the
    # photographed stepped silhouette and the axial positions of the mouth and collar.
    # This is an external art profile only. The sleeve, trunnions and weapon data stay put.
    bar = bar.copy()
    u = np.clip((bar[:, :, 1] - 109.19) / (121.31 - 109.19), 0, 1)
    radial = 0.57 + 0.09 * u
    for axis, line in [(0, 97.49), (2, 10.69)]:
        bar[:, :, axis] = line + (bar[:, :, axis] - line) * radial
    barrelparts = parts(T(bar), 'gunmetal')
    lip = rings([(0.002, 0.043), (-0.001, 0.043), (-0.001, 0.025),
                 (0.027, 0.025), (0.027, 0)], muzzle, 'z', 48)
    barrelparts += parts(lip, 'gunmetal')
    g.mesh(rec, barrelparts)
    mn = g.node('Muzzle_Main', rec, muzzle)
    cn = g.node('Muzzle_Coax_MG34', gun, coax)
    marks = []
    # Hull-side identification crosses on the removable superstructure armour, above the fenders.
    for sign,tag in [(-1,'L'),(1,'R')]:
        _, center, sz = apply(fh, sign)
        mp = painted(fh, sign, center, sz)
        d = g.node('Balkenkreuz_' + tag, root)
        g.mesh(d, mp)
        marks.append(['hull_' + tag, center, sz])
        _, center, sz = turret_mark(T(shell), sign)
        mp = painted(T(shell), sign, center, sz)
        d = g.node('Turret_Balkenkreuz_' + tag, tur, B(ROOF))
        g.mesh(d, mp)
        marks.append(['turret_' + tag, center, sz])
    wheels = []
    tracks = []
    lengths = []
    for sgn,tag,side in [(1,'l','left'),(-1,'r','right')]:
        for suffix,kind,y,z,r in AXLES:
            ps, center, rad, fac = wheel(h, sgn, y, z, r, kind)
            name = 'wheel_' + tag + '_' + suffix
            a = g.node('Suspension_' + name, root, center) if kind == 'road' else root
            n = g.node(name, a, center)
            g.mesh(n, ps)
            e = dict(
                node=n,
                name=name,
                center=center.tolist(),
                radius=rad,
                side=side,
                roadWheel=kind == 'road',
                wheelKind=kind,
                sourceFaces=fac
            )
            if kind=='road':
                e.update(suspensionNode=a, restLocalPosition=center.tolist())
            wheels.append(e)
        p, period, length, cycles = belt(sgn)
        n = g.node('track_' + tag, root)
        g.mesh(n, [p])
        tracks.append(n)
        lengths.append(length)
        skin_track(g, root, n, [w for w in wheels if w['side'] == side and w['roadWheel']], side)
        g.g.skins[-1].name = 'Pz3F_track_' + side
    tm = np.linspace(0, 4, 49)
    g.clip('Independent_wheel_drive', [(w['node'], 'rotation', tm, quat(0, -tm / w['radius'])) for w in wheels])
    g.clip('Torsion_bar_contact', [(
        w['suspensionNode'],
        'translation',
        tm,
        np.array(w['center'])[None, :] + np.c_[
            tm * 0,
            0.045 * np.sin(np.pi * tm / 2) * np.sin(tm * 3 + w['center'][2] * 3),
            tm * 0
        ]
    ) for w in wheels if w['roadWheel']])
    g.clip('Traverse_elevation_recoil', [
        (tur, 'rotation', [0, 1, 2, 3, 4], quat(1, np.radians([0, 30, 0, -30, 0]))),
        (gun, 'rotation', [0, 1, 2, 3, 4], quat(0, np.radians([0, 16, 0, -8, 0]))),
        (rec, 'translation', [0, 1.3, 1.38, 1.7, 4], [[0, 0, 0], [0, 0, 0], [0, 0, 0.13], [0, 0, 0], [0, 0, 0]])
    ])
    g.g.asset.extras = dict(
        **CREDIT,
        variant='Panzer III Ausf.F, external mantlet, short 5 cm',
        coordinates='metres, -Z forward, +Y up'
    )
    g.save(out / 'model.glb')
    def box(v,org):
        lo = v.min((0, 1))
        hi = v.max((0, 1))
        return dict(center=((lo + hi) / 2 - org).tolist(), size=(hi - lo).tolist())
    r = dict(
        format=1,
        forward='-Z',
        turret=dict(node=tur, pivot=B(ROOF).tolist(), speedDegSec=14),
        gun=dict(node=gun, pivot=pivot.tolist(), elevation=20, depression=10, recoil=0.13, recoilNode=rec),
        muzzle=dict(node=mn, position=muzzle.tolist()),
        coaxMuzzle=dict(node=cn, position=coax.tolist()),
        wheels=wheels,
        tracks=['track_l', 'track_r'],
        trackLoopMeters=period,
        trackAnimation=dict(
            axis='V',
            physicalLoopMeters=lengths,
            texturePeriodMeters=period,
            textureTilesPerLoop=cycles,
            treadsPerTile=4,
            lowerRunDirection='+Z'
        ),
        suspension=dict(
            travel=0.16,
            restCompression=0.08,
            springPerWheel=203000,
            damperPerWheel=8500,
            totalMassKg=19800,
            contacts=12
        ),
        colliders=dict(
            hull={'size': [2.74, 1.54, 5.19], 'center': [0, 0.77, 0]},
            turret=box(T(shell), g.pos[tur]),
            unit={'size': [2.91, 2.44, 5.38], 'center': [0, 1.22, 0]}
        ),
        markings=marks,
        source=CREDIT,
        sourceInnerSha256=INNER
    )
    (out / 'rig.json').write_text(json.dumps(r, indent=2, ensure_ascii=False) + '\n')
    print(ID, len(wheels), lengths, marks)
if __name__=='__main__':
    a = argparse.ArgumentParser()
    a.add_argument('source', type=Path)
    a.add_argument('out', type=Path)
    b = a.parse_args()
    build(b.source, b.out)
