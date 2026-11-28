"""Convert the credited early T-28 into one game model shared by both control prefabs."""
import argparse, io, json
from pathlib import Path
import numpy as np
from PIL import Image as PILImage
from pygltflib import Scene, Image, Texture, BufferView, NormalMaterialTexture
from ..bt7.export import Output, quat
from ..bt7.forms import unit
from ..bt7.source import painted_star
from ..bt7.paint import texture as btpaint
from ..panzer2f.build import skin_track
from ..panzer4c.source import primitive
from .source import SOURCE_SHA, read

AUX=[('l',241,[241,246,249,257,311],[258,265,266,267],266),
     ('r',99,[99,123,129,151,202],[155,169,170,171],170)]
KEY = ['wheels', 'tread', 'hull', 'turret', 'mantlet']
class Basis:
    def __init__(self,ps):
        lo = np.min([p.box[0] for p in ps.values()], 0)
        hi = np.max([p.box[1] for p in ps.values()], 0)
        self.off = np.r_[(hi[:2] + lo[:2]) * 0.5, lo[2]]
        self.scale = np.array([2.87, 7.44, 2.82]) / (hi - lo)
    def point(self,p):
        return ((np.asarray(p) - self.off) * self.scale)[..., [0, 2, 1]] * [-1, 1, 1]
    def normal(self,n):
        return unit((n / self.scale)[..., [0, 2, 1]] * [-1, 1, 1])

def tex(images,key):
    if key=='red':
        return btpaint(None, 'red')
    atlas = KEY.index(key)
    a = np.asarray(images[2 * atlas].convert('RGB'), float)
    if atlas==1:
        # The source's V axis runs forward along the contact patch. Reflect the
        # V coordinate and matching texture together; retain every original shoe.
        return PILImage.fromarray(np.clip(
            a * 1.1 + 3,
            0,
            255
        ).astype('uint8')).transpose(PILImage.Transpose.FLIP_TOP_BOTTOM)
    lum = a @ np.array([0.26, 0.55, 0.19])
    out = lum[..., None] * [0.79, 1.015, 0.675] + [3, 7, 2]
    # Keep neutral rubber, bare edges and fasteners; preserve source grime and highlights.
    chroma = a.max(2) - a.min(2)
    mask = np.clip((chroma - 1.5) / 9, 0, 1)
    mask *= np.clip((lum - 16) / 32, 0, 1)
    if atlas==0:
        mask *= np.clip((lum - 26) / 30, 0, 1)
    out = a * (1 - mask[..., None]) + out * mask[..., None]
    return PILImage.fromarray(np.clip(out, 0, 255).astype('uint8'))

def add_normals(g,images):
    seen = {}
    for k,mi in g.materials.items():
        base = 'tread' if k in ('tread_l', 'tread_r') else k
        if base=='red':
            continue
        if base not in seen:
            src = images[KEY.index(base) * 2 + 1].convert('RGB')
            if base=='tread':
                a = np.array(src.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM))
                a[:, :, 1] = 255 - a[:, :, 1]
                src = PILImage.fromarray(a)
            buf = io.BytesIO()
            src.save(buf, format='PNG', optimize=True)
            raw = buf.getvalue()
            g.blob.extend(bytes(-len(g.blob) % 4))
            offset = len(g.blob)
            g.blob.extend(raw)
            bv = len(g.g.bufferViews)
            g.g.bufferViews.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw)))
            image = len(g.g.images)
            g.g.images.append(Image(name='T28_' + base + '_normal', mimeType='image/png', bufferView=bv))
            tid = len(g.g.textures)
            g.g.textures.append(Texture(sampler=0, source=image))
            seen[base] = tid
        g.g.materials[mi].normalTexture = NormalMaterialTexture(index=seen[base], scale=1.0)

def build(inp,out):
    out.mkdir(exist_ok=True, parents=True)
    ps, images, credit = read(inp)
    credit = dict(credit, adaptation='Repainted original UVs, articulated three turrets and running gear, supplied game rig and two red stars.')
    B = Basis(ps)
    g = Output(images, 'T28', tex)
    g.pos = []
    root = g.node('Hull')
    g.g.scenes = [Scene(nodes=[root])]
    g.g.scene = 0
    def ring(k):
        v = ps[k].p.reshape(-1, 3)
        base = v[v[:, 2] < v[:, 2].min() + 0.00016]
        return B.point((base.min(0) + base.max(0)) * 0.5)
    def tip(k):
        v = ps[k].p.reshape(-1, 3)
        v = v[v[:, 1] < v[:, 1].min() + 0.0011]
        return B.point((v.min(0) + v.max(0)) * 0.5)
    tur = g.node('Turret', root, ring(10009))
    pivot = B.point([0.00025, -0.61, 0.9071])
    gun = g.node('Gun', tur, pivot)
    rec = g.node('Barrel_Recoil', gun, pivot)
    muzzle, coax = (tip(20008), tip(10014))
    mn = g.node('Muzzle_Main', rec, muzzle)
    cn = g.node('Muzzle_Coax_DT', gun, coax)
    assigned = {}
    wheels = []
    aux = []
    marked = {}
    def take(k,n):
        if k in assigned:
            raise ValueError(('Duplicate island ownership', k))
        assigned[k] = n
    # Hull lamps and driver stay on the hull; antenna stanchions, cupola and rear ball port
    # stay on the main turret. Only the actual inner tube recoils inside the fixed jacket.
    for k in ps:
        if k//10000==1:
            take(k, gun if k in (10011, 10013, 10014, 10015) else tur)
        elif k//10000==2:
            take(k, rec if k == 20008 else gun)
    auxroot = g.node('T28_AuxRig', root)
    for tag,ringid,upper,mounts,bore in AUX:
        yaw = g.node('T28_Aux_' + tag, auxroot, ring(ringid))
        axis = B.point(ps[mounts[0]].c)
        pitch = g.node('T28_DT_' + tag, yaw, axis)
        tipnode = g.node('T28_DT_Muzzle_' + tag, pitch, tip(bore))
        for k in upper:
            take(k, yaw)
        for k in mounts:
            take(k, pitch)
        aux.append(dict(side=tag,yawNode=yaw,pitchNode=pitch,muzzleNode=tipnode,
                        pivot=g.pos[yaw].tolist(),mount=axis.tolist(),muzzle=g.pos[tipnode].tolist()))
    # Put nonstandard radii ahead of the road wheels in the node table. Older Hatch
    # clients cache 28 radii; leftover entries then use the identical mean road radius.
    wheel_geometry = []
    for group,side,tag in [(4,'left','l'),(3,'right','r')]:
        objs = {k: o for k, o in ps.items() if o.mesh == group}
        # The 12 outer wheel faces and four support rollers give exact axle locations.
        axles = sorted([o.c[1:] for o in objs.values() if 0.128 < o.span[2] < 0.145 and 0.09 < o.c[2] < 0.105 and (0.442 < abs(o.c[0]) < 0.47)], key=lambda p: p[0])
        returns = sorted([o.c[1:] for o in objs.values() if 0.105 < o.span[2] < 0.125 and o.c[2] > 0.38 and (0.442 < abs(o.c[0]) < 0.47)], key=lambda p: p[0])
        if len(axles)!=12 or len(returns)!=4:
            raise ValueError((side, len(axles), len(returns)))
        ag = [('road', f'{i + 1:02}', float(y), float(z), 0.0689) for i, (y, z) in enumerate(axles)]
        ag += [('return', f'return_{i + 1}', float(y), float(z), 0.059) for i, (y, z) in enumerate(returns)]
        ag += [('idler', 'idler', -1.2615, 0.345, 0.154), ('drive', 'drive', 1.291, 0.3169, 0.156)]
        wheel_geometry.append((group, side, tag, objs, axles, ag))
    wheel_lookup = {}
    for road_pass in (False,True):
        for group,side,tag,objs,axles,ag in wheel_geometry:
            s = 1 if side == 'left' else -1
            for kind,suffix,y,z,rr in ag:
                if (kind=='road') != road_pass:
                    continue
                center = B.point([s * 0.488, y, z])
                name = 'wheel_' + tag + '_' + suffix
                anchor = g.node('Suspension_' + name, root, center) if kind == 'road' else root
                n = g.node(name, anchor, center)
                wheel_lookup[side, suffix] = n
                w = dict(
                    node=n,
                    name=name,
                    center=center.tolist(),
                    radius=float(rr * B.scale[2]),
                    side=side,
                    wheelKind=kind,
                    roadWheel=kind == 'road'
                )
                if kind=='road':
                    w.update(suspensionNode=anchor, restLocalPosition=center.tolist())
                wheels.append(w)
    for group,side,tag,objs,axles,ag in wheel_geometry:
        s = 1 if side == 'left' else -1
        axleids = [wheel_lookup[side, w[1]] for w in ag]
        bogies = []
        for i in range(6):
            y = (axles[2 * i][0] + axles[2 * i + 1][0]) * 0.5
            bogies.append((y, g.node(f'Bogie_{tag}_{i + 1:02}', root, B.point([s * 0.488, y, 0.193]))))
        for k,o in objs.items():
            # All original discs, teeth, hubs and spokes are assigned by their actual
            # radius about an axle. The six suspension bridges span two wheels each.
            eligible = []
            for ii,(_,_,y,z,rr) in enumerate(ag):
                R = np.linalg.norm(o.p[:, :, [1, 2]] - [y, z], axis=2)
                if R.max()<rr+.012:
                    eligible.append((np.linalg.norm(o.c[1:] - [y, z]), ii))
            if eligible:
                take(k, axleids[min(eligible)[1]])
            else:
                dy, node = min(((abs(o.c[1] - y), n) for y, n in bogies))
                if dy>.025:
                    raise ValueError(('Unidentified running gear', k, o.c))
                take(k, node)
    def part(o):
        return primitive(B.point(o.p), B.normal(o.n), o.uv, KEY[o.atlas])
    group = {}
    for k,o in ps.items():
        if o.mesh==5:
            continue
        dest = assigned.get(k, root)
        group.setdefault(dest, []).append(part(o))
    for n,parts in group.items():
        g.mesh(n, parts)
    for side,sign in [('l',-1),('r',1)]:
        shell = part(ps[10009])
        cy = B.point([0, 0, 0.89])[1]
        cz = B.point([0, -0.25, 0])[2]
        p = painted_star(shell, sign, cy, cz, 0.234)
        decal = g.node('Red_star_' + side, tur, g.pos[tur])
        g.mesh(decal, [p])
        marked[side] = decal
    lengths = []
    periods = []
    for tag,side in [('l','left'),('r','right')]:
        pieces = [o for o in ps.values() if o.mesh == 5 and (o.c[0] > 0) == (side == 'left')]
        p = np.concatenate([o.p for o in pieces])
        uv = np.concatenate([o.uv for o in pieces]).copy()
        n = np.concatenate([o.n for o in pieces])
        uv[:, :, 1] *= -1
        v = B.point(p)
        bottom = (v[:, :, 1].max(1) < 0.035) & (abs(v[:, :, 2]).max(1) < 2)
        dz = np.ptp(v[:, :, 2], axis=1)
        du = np.ptp(uv[:, :, 1], axis=1)
        good = bottom & (dz > 0.03) & (du > 0.03) & (du < 1)
        per = float(np.median(dz[good] / du[good]))
        periods.append(per)
        # Exactly 45 full original UV cycles; account for the wrap on each atlas strip.
        probe = np.isclose(uv[:, :, 0], 0.276, atol=0.003)
        vspan = float(np.ptp(uv[:, :, 1][probe]))
        tiles = round(vspan)
        if tiles not in range(42,49):
            raise ValueError(('Belt seam', vspan))
        lengths.append(per * tiles)
        node = g.node('track_' + tag, root)
        g.mesh(node, [primitive(v, B.normal(n), uv, 'tread_' + tag)])
        skin_track(g, root, node, [w for w in wheels if w['side'] == side and w['roadWheel']], side)
        g.g.skins[-1].name = 'T28_' + side + '_contacts'
    assert np.isclose(periods[0], periods[1], rtol=0.003)
    t = np.linspace(0, 4, 49)
    g.clip('Road_and_return_wheels', [(w['node'], 'rotation', t, quat(0, -t / w['radius'])) for w in wheels])
    g.clip('Bogie_contact', [(
        w['suspensionNode'],
        'translation',
        t,
        np.array(w['center']) + np.c_[
            t * 0,
            0.036 * np.sin(t * np.pi / 2) * np.cos(t * 3 + w['center'][2] * 1.9),
            t * 0
        ]
    ) for w in wheels if w['roadWheel']])
    tt = [0, 1, 2, 3, 4]
    motion = [
        (tur, 'rotation', tt, quat(1, np.radians([0, 32, 0, -32, 0]))),
        (gun, 'rotation', tt, quat(0, np.radians([0, 12, 0, -7, 0]))),
        (rec, 'translation', [0, 1.25, 1.32, 1.65, 4], [[0, 0, 0], [0, 0, 0], [0, 0, 0.12], [0, 0, 0], [0, 0, 0]])
    ]
    for sub in aux:
        gl = [0, 12, 0, -27, 0] if sub['side'] == 'l' else [0, 27, 0, -12, 0]
        motion.extend([(
            sub['yawNode'],
            'rotation',
            tt,
            quat(1, np.radians(gl))
        ), (sub['pitchNode'], 'rotation', tt, quat(0, np.radians([0, 8, 0, -5, 0])))])
    g.clip('Three_turrets_and_recoil', motion)
    add_normals(g, images)
    g.g.asset.extras = dict(
        **credit,
        coordinates='metres, +Y up, -Z forward',
        variant='Early cylindrical turret and short KT-28'
    )
    g.save(out / 'model.glb')
    def box(v,org):
        lo, hi = (v.min((0, 1)), v.max((0, 1)))
        return dict(center=((lo + hi) / 2 - org).tolist(), size=(hi - lo).tolist())
    rig=dict(format=1,forward='-Z',turret=dict(node=tur,pivot=g.pos[tur].tolist(),speedDegSec=12),
             gun=dict(node=gun,pivot=pivot.tolist(),elevation=25,depression=5,recoil=.12,recoilNode=rec),
             muzzle=dict(node=mn,position=muzzle.tolist()),coaxMuzzle=dict(node=cn,position=coax.tolist()),
             wheels=wheels,tracks=['track_l','track_r'],trackLoopMeters=float(np.mean(periods)),trackAnimation=dict(axis='V',physicalLoopMeters=lengths,textureTilesPerLoop=tiles,lowerRunDirection='+Z'),
             auxiliaryTurrets=aux,markings=marked,suspension=dict(travel=.13,restCompression=.065,springPerWheel=177000,damperPerWheel=6650,totalMassKg=28000,contacts=24),
             colliders=dict(hull=box(B.point(ps[17].p),np.zeros(3)),turret=box(B.point(ps[10009].p),g.pos[tur]),unit=dict(center=[0,1.41,0],size=[2.87,2.82,7.44])),
             source=credit,sourceSha256=SOURCE_SHA)
    (out / 'rig.json').write_text(json.dumps(rig, ensure_ascii=False, indent=2) + '\n')
    print('T-28', len(wheels), 'wheel axles;', len(aux) + 1, 'turrets; track repeats', periods)
if __name__=='__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('input', type=Path)
    ap.add_argument('out', type=Path)
    a = ap.parse_args()
    build(a.input, a.out)
