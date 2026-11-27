"""Emit a single, attribution-preserving GLB and its indexed Hatch vehicle rig."""

import io

import numpy as np
from pygltflib import (
    GLTF2,
    Animation,
    AnimationChannel,
    AnimationChannelTarget,
    AnimationSampler,
    Attributes,
    Buffer,
    BufferView,
    Image,
    Material,
    Mesh,
    Node,
    PbrMetallicRoughness,
    Primitive,
    Sampler,
    Scene,
    Skin,
    Texture,
    TextureInfo,
)

from ..modelrig import Model
from . import paint
from .source import (
    BARREL,
    CREDIT,
    GUN,
    ROAD,
    SMALL,
    TURRET,
    Part,
    painted_star,
    read,
    track_from_guide,
)


class Output(Model):
    def __init__(self, src, prefix="BT7", texture_fn=paint.texture):
        self.g = GLTF2()
        self.g.buffers = [Buffer(byteLength=0)]
        self.blob = bytearray()
        self.src = src
        self.prefix = prefix
        self.texture_fn = texture_fn
        self.materials = {}
        self.texmap = {}
        self.g.samplers = [
            Sampler(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)
        ]

    def material(self, key):
        base = "tread" if key in ("tread_l", "tread_r") else key
        if key in self.materials:
            return self.materials[key]
        if base not in self.texmap:
            im = self.texture_fn(self.src, base)
            b = io.BytesIO()
            im.save(b, format="PNG", optimize=True)
            data = b.getvalue()
            self.blob.extend(bytes(-len(self.blob) % 4))
            off = len(self.blob)
            self.blob.extend(data)
            i = len(self.g.bufferViews)
            self.g.bufferViews.append(
                BufferView(buffer=0, byteOffset=off, byteLength=len(data))
            )
            t = len(self.g.images)
            self.g.images.append(
                Image(name=f"{self.prefix}_{base}", mimeType="image/png", bufferView=i)
            )
            self.g.textures.append(Texture(sampler=0, source=t))
            self.texmap[base] = t
        idx = len(self.g.materials)
        self.g.materials.append(
            Material(
                name=f"{self.prefix}_{key}",
                pbrMetallicRoughness=PbrMetallicRoughness(
                    metallicFactor=0,
                    roughnessFactor=0.88,
                    baseColorFactor=[1, 1, 1, 1],
                    baseColorTexture=TextureInfo(index=self.texmap[base]),
                ),
                doubleSided=False,
            )
        )
        self.materials[key] = idx
        return idx

    def node(self, name, parent=None, point=None):
        p = np.array(point if point is not None else (0.0, 0.0, 0.0))
        i = len(self.g.nodes)
        local = p if parent is None else p - self.pos[parent]
        self.pos.append(p)
        self.g.nodes.append(Node(name=name, translation=local.tolist(), children=[]))
        if parent is not None:
            self.g.nodes[parent].children.append(i)
        return i

    def mesh(self, node, parts):
        mats = {}
        for p in parts:
            mats.setdefault(p.m, []).append(p)
        ps = []
        pt = self.pos[node]
        for key, array in mats.items():
            v = np.vstack([p.v for p in array])
            n = np.vstack([p.n for p in array])
            uv = np.vstack([p.uv for p in array])
            offset = np.cumsum([0] + [len(p.v) for p in array])
            ix = np.concatenate([p.ix + offset[i] for i, p in enumerate(array)])
            if len(v) > 65535:
                raise ValueError("Split material group for mobile")
            at = Attributes(
                POSITION=self.add_array(v - pt),
                NORMAL=self.add_array(n),
                TEXCOORD_0=self.add_array(uv, "VEC2"),
            )
            ps.append(
                Primitive(
                    attributes=at,
                    indices=self.add_array(ix, "SCALAR", 5123),
                    material=self.material(key),
                    mode=4,
                )
            )
        self.g.nodes[node].mesh = len(self.g.meshes)
        self.g.meshes.append(Mesh(name=self.g.nodes[node].name, primitives=ps))

    def clip(self, name, dat):
        a = Animation(name=name, channels=[], samplers=[])
        for node, path, t, v in dat:
            t_i = self.add_array(t, "SCALAR")
            v_i = self.add_array(v, "VEC4" if path == "rotation" else "VEC3")
            a.channels.append(
                AnimationChannel(
                    sampler=len(a.samplers),
                    target=AnimationChannelTarget(node=node, path=path),
                )
            )
            a.samplers.append(
                AnimationSampler(input=t_i, output=v_i, interpolation="LINEAR")
            )
        self.g.animations.append(a)


def quat(axis, angles):
    a = np.asarray(angles) / 2
    q = np.zeros((len(a), 4))
    q[:, axis] = np.sin(a)
    q[:, 3] = np.cos(a)
    return q


def build(path, out):
    m, parts, org, repaired = read(path)
    g = Output(m)
    g.pos = []
    root = g.node("Hull")
    g.g.scenes = [Scene(nodes=[root])]
    g.g.scene = 0
    turret = g.node("Turret", root, org[218])
    gun = g.node("Gun", turret, org[38])
    recoil = g.node("Barrel_Recoil", gun, org[38])

    def tip(k):
        p = parts[k].v
        end = p[p[:, 2] < p[:, 2].min() + 0.011]
        return np.array(
            [
                (end[:, 0].min() + end[:, 0].max()) / 2,
                (end[:, 1].min() + end[:, 1].max()) / 2,
                p[:, 2].min() - 0.004,
            ]
        )

    muzzle = tip(17)
    coax = tip(107)
    mz = g.node("Muzzle_Main", recoil, muzzle)
    mg = g.node("Muzzle_Coax_DT", gun, coax)
    group = {root: [], turret: [], gun: [], recoil: []}
    for k, p in parts.items():
        if k in ROAD | SMALL | {206, 207}:
            continue
        if k in (169, 170):
            p.m = "exhaust"
        group[
            turret
            if k in TURRET
            else gun
            if k in GUN
            else recoil
            if k in BARREL
            else root
        ].append(p)
    for node, ps in group.items():
        g.mesh(node, ps)
    shell = parts[210]
    cy = shell.v[:, 1].min() + np.ptp(shell.v[:, 1]) * 0.56
    cz = org[218][2] + 0.60
    for name, side in [("L", -1), ("R", 1)]:
        dec = g.node("Red_Star_" + name, turret, org[218])
        g.mesh(dec, [painted_star(shell, side, cy, cz)])
    wheels = []
    anchors = {}
    track_nodes = []
    periods = []
    physical = []
    for side, tag in [("left", "l"), ("right", "r")]:
        sign = -1 if side == "left" else 1
        ii = sorted(
            (k for k in ROAD | SMALL if np.sign(org[k][0]) == sign),
            key=lambda k: (k not in ROAD, org[k][2]),
        )
        for order, k in enumerate(ii):
            p = parts[k]
            cen = (p.v.min(0) + p.v.max(0)) / 2
            r = np.ptp(p.v[:, 1]) / 2
            road = k in ROAD
            nm = (
                "wheel_"
                + tag
                + "_"
                + (
                    f"{order + 1:02}"
                    if road
                    else ("idler" if k in (33, 34) else "drive")
                )
            )
            pr = g.node("Suspension_" + nm, root, cen) if road else root
            wn = g.node(nm, pr, cen)
            if road:
                anchors[wn] = pr
                tri = p.ix.reshape(-1, 3)
                rad = np.linalg.norm((p.v[tri].mean(axis=1) - cen)[:, 1:], axis=1)
                rub = rad > r * 0.87
                g.mesh(
                    wn,
                    [
                        Part(p.v, p.n, p.uv, tri[~rub].ravel(), p.m),
                        Part(p.v, p.n, p.uv, tri[rub].ravel(), "rubber"),
                    ],
                )
            else:
                g.mesh(wn, [p])
            entry = {
                "node": wn,
                "name": nm,
                "center": cen.tolist(),
                "radius": float(r),
                "side": side,
                "roadWheel": road,
            }
            if road:
                entry.update(suspensionNode=pr, restLocalPosition=cen.tolist())
            wheels.append(entry)
        # Creation order is significant: the shipped body controller reads left, then right.
        k = 206 if side == "left" else 207
        t, per, length = track_from_guide(parts[k])
        periods.append(per)
        physical.append(length)
        t.m = "tread_" + tag
        node = g.node("track_" + tag, root)
        g.mesh(node, [t])
        track_nodes.append(node)

    if abs(periods[0] - periods[1]) > 1e-4:
        raise ValueError("Track pitch mismatch")
    for i, side in enumerate(("left", "right")):
        ws = [w for w in wheels if w["roadWheel"] and w["side"] == side]
        joints = [root] + [w["suspensionNode"] for w in ws]
        ib = []
        for j in joints:
            M = np.eye(4)
            M[:3, 3] = -g.pos[j]
            ib.append(M.T.ravel())
        tn = track_nodes[i]
        g.g.nodes[tn].skin = len(g.g.skins)
        g.g.skins.append(
            Skin(
                name="Track_Contact_" + side,
                joints=joints,
                skeleton=root,
                inverseBindMatrices=g.add_array(ib, "MAT4"),
            )
        )
        pr = g.g.meshes[g.g.nodes[tn].mesh].primitives[0]
        v = g.array(pr.attributes.POSITION)
        wz = np.array([q["center"][2] for q in ws])
        j = np.zeros((len(v), 4), dtype=np.uint16)
        w = np.zeros((len(v), 4))
        w[:, 0] = 1
        blend = (
            np.clip(1 - v[:, 1] / 0.57, 0, 1)
            * np.clip((v[:, 2] - wz[0] + 0.55) / 0.55, 0, 1)
            * np.clip((wz[-1] + 0.55 - v[:, 2]) / 0.55, 0, 1)
        )
        for k, p in enumerate(v):
            z = p[2]
            b = np.clip(np.searchsorted(wz, z), 1, len(ws) - 1)
            a = b - 1
            t = np.clip((z - wz[a]) / (wz[b] - wz[a]), 0, 1)
            j[k, :3] = [0, a + 1, b + 1]
            w[k, :3] = [1 - blend[k], blend[k] * (1 - t), blend[k] * t]
        pr.attributes.JOINTS_0 = g.add_array(j, "VEC4", 5123)
        pr.attributes.WEIGHTS_0 = g.add_array(w, "VEC4")
    tm = np.linspace(0, 4, 49)
    g.clip(
        "Wheels_forward_1m_s",
        [(w["node"], "rotation", tm, quat(0, -tm / w["radius"])) for w in wheels],
    )
    g.clip(
        "Suspension_contact",
        [
            (
                w["suspensionNode"],
                "translation",
                tm,
                np.array(w["center"])[None, :]
                + np.stack(
                    [
                        tm * 0,
                        0.065
                        * np.sin(2 * np.pi * tm / 4)
                        * np.cos(tm * 2.4 + w["center"][2] * 2),
                        tm * 0,
                    ],
                    axis=1,
                ),
            )
            for w in wheels
            if w["roadWheel"]
        ],
    )
    t = np.arange(5.0)
    g.clip(
        "Turret_and_barrel",
        [
            (turret, "rotation", t, quat(1, np.radians([0, 28, 0, -28, 0]))),
            (gun, "rotation", t, quat(0, np.radians([0, 13, 0, -4, 0]))),
            (
                recoil,
                "translation",
                np.array([0, 1, 1.06, 1.45, 4]),
                np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0.13], [0, 0, 0], [0, 0, 0]]),
            ),
        ],
    )
    g.g.asset.extras = {
        **CREDIT,
        "variant": "BT-7 Model 1937: conical turret and twin exhausts",
        "coordinates": "metres, +Y up, -Z forward",
    }
    g.save(out / "model.glb")

    def box(v, origin):
        lo = v.min(0)
        hi = v.max(0)
        return {"center": ((lo + hi) / 2 - origin).tolist(), "size": (hi - lo).tolist()}

    hc = box(parts[70].v, np.zeros(3))
    hc["size"][1] = float(parts[70].v[:, 1].max())
    hc["center"][1] = hc["size"][1] / 2
    r = {
        "format": 1,
        "forward": "-Z",
        "turret": {"node": turret, "pivot": g.pos[turret].tolist(), "speedDegSec": 16},
        "gun": {
            "node": gun,
            "pivot": g.pos[gun].tolist(),
            "elevation": 40,
            "depression": 4,
            "recoil": 0.13,
            "recoilNode": recoil,
        },
        "muzzle": {"node": mz, "position": muzzle.tolist()},
        "coaxMuzzle": {"node": mg, "position": coax.tolist()},
        "wheels": wheels,
        "tracks": ["track_l", "track_r"],
        "trackLoopMeters": periods[0],
        "trackAnimation": {
            "axis": "V",
            "texturePeriodMeters": periods[0],
            "physicalLoopMeters": physical,
            "linksPerLoop": 73,
            "glTFVIncreasesOnLowerRunToward": "+Z (rear)",
            "gameplay": "Independent material phase from left/right speed; eight separate vertical wheel contacts.",
        },
        "suspension": {
            "travel": 0.16,
            "restCompression": 0.08,
            "springPerWheel": 211500,
            "damperPerWheel": 8000,
            "totalMassKg": 13800,
            "contacts": 8,
        },
        "colliders": {
            "hull": hc,
            "turret": box(shell.v, g.pos[turret]),
            "unit": {"center": [0, 1.21, 0], "size": [2.29, 2.42, 5.66]},
        },
        "source": CREDIT,
        "repairedSourceMeshIndices": repaired,
    }
    return r
