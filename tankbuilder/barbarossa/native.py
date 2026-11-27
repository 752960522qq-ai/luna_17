"""Build an additional player scene with native terrain, LOD trees, scenery and colliders."""

import copy
import hashlib
import math
import struct
import zipfile
from pathlib import Path

import numpy as np
import UnityPy
from PIL import Image

from ..serialization import NODES, assert_roundtrip, encode_complete, parse_complete
from ..unity_assets import EditableObject, aabb, pp, xyz
from . import layout as L
from . import props

ONE = "sharedassets1.assets"
THREE = "sharedassets3.assets"
FOUR = "sharedassets4.assets"
SCENE_PATH = "Assets/Scenes/ExtraCampaign/Barbarossa_Polesie_Summer.unity"
FINGERPRINTS = {
    "level11": "fb8625ef9c18d760e4f5dee9f48a87c1654e8eb3df3c4c61b9a47c925517f185",
    "level20": "c155f06fadbdc30350fb68bc22ba169450e025c19c72940345a6f755b737197b",
    ONE: "d14937c7eff618c1caabaad977eefc1cb969ebb94dbd9f507e13cd8e5149d303",
    THREE: "d52cde8120c7a9a6566682226ccb6d88f7ed1006286b55a8f49c79337ca70cf9",
    FOUR: "ed8360f09871dc6d2e861583a70bc8472e3f8f0339150c6ac29e6d4b3aabff02",
}


def check(ok, msg):
    if not ok:
        raise ValueError(msg)


def read_bundle(p):
    if zipfile.is_zipfile(p):
        with zipfile.ZipFile(p) as z:
            raw = z.read("assets/bin/Data/data.unity3d")
    else:
        raw = Path(p).read_bytes()
    b = next(iter(UnityPy.load(raw).files.values()))
    for name, sha in FINGERPRINTS.items():
        check(
            hashlib.sha256(b.files[name].reader.bytes).hexdigest() == sha,
            "Unreviewed donor: " + name,
        )
        for t in b.files[name].objects.values():
            if t.type.name in NODES:
                t.serialized_type.node = NODES[t.type.name]
    return b


def quat(yaw=0, pitch=0):
    y, p = (math.radians(x) * 0.5 for x in (yaw, pitch))
    return dict(
        zip(
            "xyzw",
            (
                math.cos(y) * math.sin(p),
                math.sin(y) * math.cos(p),
                -math.sin(y) * math.sin(p),
                math.cos(y) * math.cos(p),
            ),
        )
    )


def remap(v, fn):
    if isinstance(v, dict):
        if set(v) == {"m_FileID", "m_PathID"}:
            return fn(v)
        return {k: remap(x, fn) for k, x in v.items()}
    if isinstance(v, (tuple, list)):
        return [remap(x, fn) for x in v]
    return v


def patch_tree(h):
    """Unity's row-major 16-cell patches followed by each 2× coarser quadtree level."""
    v = h.astype("f8") / 32766
    bounds = []
    errors = []
    for step in (1, 2, 4, 8, 16):
        size = 16 * step
        for z in range(0, 256, size):
            for x in range(0, 256, size):
                t = v[z : z + size + 1, x : x + size + 1]
                bounds.extend([float(t.min()), float(t.max())])
                if step == 1:
                    errors.append(0.0)
                    continue
                iz, ix = np.indices(t.shape)
                i = np.minimum(ix // step, 15)
                j = np.minimum(iz // step, 15)
                u = ix / step - i
                q = iz / step - j
                k = t[::step, ::step]
                a = k[j, i]
                b = k[j, i + 1]
                c = k[j + 1, i]
                d = k[j + 1, i + 1]
                v1 = a + (b - a) * u + (c - a) * q + (d - b - c + a) * np.minimum(u, q)
                v2 = (
                    a
                    + (b - a) * u
                    + (c - a) * q
                    + (d - b - c + a) * np.maximum(u + q - 1, 0)
                )
                errors.append(
                    float(max(np.max(np.abs(t - v1)), np.max(np.abs(t - v2))))
                )
    return bounds, errors


class Scene:
    def __init__(self, b):
        self.b = b
        self.base = b.files["level11"]
        sf = self.sf = copy.copy(b.files["level20"])
        sf.objects = {}
        sf.types = []
        sf.script_types = []
        sf.ref_types = []
        sf.externals = self.base.externals.copy()
        self.p = 1
        self.g = {}
        self.components = {}
        self.kinds = {}
        self.samples = {}
        for name in ["level11", "level20", FOUR, ONE]:
            for o in b.files[name].objects.values():
                if o.type.name not in self.samples:
                    self.samples[o.type.name] = o
        for k, pid in [
            ("Transform", 62041),
            ("MeshRenderer", 94771),
            ("BoxCollider", 146288),
            ("LODGroup", 155161),
        ]:
            self.samples[k] = self.base.objects[pid]
        self.samples["Mesh"] = b.files[FOUR].objects[65]
        self.samples["Texture2D"] = b.files[FOUR].objects[44]
        self.samples["Material"] = b.files[FOUR].objects[11]
        self.base_t = {}

    def id(self):
        p = self.p
        self.p += 1
        return p

    def external(self, name, p):
        if not p:
            return pp()
        idx = next(
            (i for i, e in enumerate(self.sf.externals, 1) if e.path == name), None
        )
        if idx is None:
            e = next(
                e
                for f in self.b.files.values()
                if hasattr(f, "externals")
                for e in f.externals
                if e.path == name
            )
            self.sf.externals.append(copy.copy(e))
            idx = len(self.sf.externals)
        return pp(p, idx)

    def from_file(self, fn, tree):
        f = self.b.files[fn]
        return remap(
            tree,
            lambda r: self.external(
                f.externals[r["m_FileID"] - 1].path if r["m_FileID"] else fn,
                r["m_PathID"],
            ),
        )

    def put(self, kind, data, *, src=None, p=None, raw=False):
        p = self.id() if p is None else p
        src = src or self.samples[kind]
        idx = self.kinds.get(kind)
        if idx is None:
            idx = len(self.sf.types)
            self.kinds[kind] = idx
            self.sf.types.append(copy.copy(src.serialized_type))
        obj = object.__new__(EditableObject)
        obj.__dict__.update(src.__dict__)
        obj.assets_file = self.sf
        obj.path_id = p
        obj.type_id = idx
        obj.serialized_type = self.sf.types[idx]
        obj.set_raw_data(data if raw else encode_complete(src, data))
        self.sf.objects[p] = obj
        return p

    def baseval(self, kind):
        if kind not in self.base_t:
            self.base_t[kind] = assert_roundtrip(self.samples[kind])
        return copy.deepcopy(self.base_t[kind])

    def node(
        self, name, parent=None, pos=(0, 0, 0), rotation=None, scale=1.0, layer=0, tag=0
    ):
        g, tr = self.id(), self.id()
        self.g[g] = {
            "name": name,
            "tr": tr,
            "parent": parent,
            "children": [],
            "layer": layer,
            "tag": tag,
            "pos": xyz(pos),
            "rot": rotation or quat(),
            "scale": xyz((scale,) * 3 if np.isscalar(scale) else scale),
        }
        self.components[g] = [tr]
        if parent is not None:
            self.g[parent]["children"].append(tr)
        return g

    def part(self, g, kind, t, **opts):
        if not opts.get("raw"):
            t = dict(t, m_GameObject=pp(g))
        p = self.put(kind, t, **opts)
        self.components[g].append(p)
        return p

    def finish(self):
        for g, v in self.g.items():
            tr = self.baseval("Transform")
            tr.update(
                m_GameObject=pp(g),
                m_Father=pp(
                    self.g[v["parent"]]["tr"] if v["parent"] is not None else 0
                ),
                m_Children=[pp(t) for t in v["children"]],
                m_LocalRotation=v["rot"],
                m_LocalPosition=v["pos"],
                m_LocalScale=v["scale"],
            )
            self.put("Transform", tr, p=v["tr"])
            self.put(
                "GameObject",
                {
                    "m_Component": [{"component": pp(c)} for c in self.components[g]],
                    "m_Layer": v["layer"],
                    "m_Name": v["name"],
                    "m_Tag": v["tag"],
                    "m_IsActive": True,
                },
                p=g,
            )
        return self.sf.save()

    def texture(self, name, im, linear=False, weight=False):
        im = im.convert("RGBA")
        w, h = im.size
        native = im if weight else im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        levels = [native.tobytes()]
        n = native
        while min(n.size) > 1:
            if weight:
                # Alpha is a fourth soil weight, not opacity. RGBA image resampling
                # premultiplies by alpha and would erase distant grass and roads.
                a = np.asarray(n, dtype=np.uint16)
                sums = a[::2, ::2] + a[1::2, ::2] + a[::2, 1::2] + a[1::2, 1::2]
                q = sums // 4
                ranks = np.argsort(
                    np.argsort(-(sums % 4).astype(np.int32), axis=-1, kind="stable"),
                    axis=-1,
                    kind="stable",
                )
                q += (ranks < (255 - q.sum(axis=-1))[..., None]).astype(np.uint16)
                n = Image.fromarray(q.astype("u1"))
            else:
                n = n.resize(
                    (max(1, n.width // 2), max(1, n.height // 2)), Image.Resampling.BOX
                )
            levels.append(n.tobytes())
        buf = b"".join(levels)
        t = self.baseval("Texture2D")
        t.update(
            m_Name=name,
            m_Width=w,
            m_Height=h,
            m_TextureFormat=4,
            m_CompleteImageSize=len(buf),
            m_MipCount=len(levels),
            m_MipsStripped=0,
            m_IsReadable=weight,
            m_StreamingMipmaps=False,
            m_ColorSpace=0 if linear else 1,
            m_StreamData={"offset": 0, "size": 0, "path": ""},
            m_PlatformBlob=b"",
        )
        t["image data"] = buf
        t["m_TextureSettings"].update(
            m_WrapU=1 if weight else 0, m_WrapV=1 if weight else 0, m_FilterMode=1
        )
        return self.put("Texture2D", t)

    def material(self, texture):
        t = self.from_file(FOUR, self.baseval("Material"))
        t["m_Name"] = "Polesie_Weathered_Timber"
        p = t["m_SavedProperties"]
        for k, a in p["m_TexEnvs"]:
            a["m_Texture"] = pp(texture) if k == "_MainTex" else pp()
            a["m_Scale"] = {"x": 1.0, "y": 1.0}
            a["m_Offset"] = {"x": 0.0, "y": 0.0}
        for k, a in p["m_Colors"]:
            if k == "_Color":
                a.update(r=1.0, g=1.0, b=1.0, a=1.0)
        return self.put("Material", t)

    def mesh(self, name, arrays):
        v, n, uv, ix = arrays
        pts = np.column_stack([v, n, uv]).astype("<f4")
        k = len(ix)
        bounds = aabb(v)
        ch = [
            {"stream": 0, "offset": 0, "format": 0, "dimension": 0} for i in range(14)
        ]
        for i, off, dim in [(0, 0, 3), (1, 12, 3), (4, 24, 2)]:
            ch[i].update(offset=off, dimension=dim)
        t = self.baseval("Mesh")
        t.update(
            m_Name=name,
            m_SubMeshes=[
                {
                    "firstByte": 0,
                    "indexCount": k,
                    "topology": 0,
                    "baseVertex": 0,
                    "firstVertex": 0,
                    "vertexCount": len(v),
                    "localAABB": bounds,
                }
            ],
            m_MeshCompression=0,
            m_IsReadable=False,
            m_IndexFormat=0,
            m_IndexBuffer=ix.astype("<u2").tobytes(),
            m_VertexData={
                "m_VertexCount": len(v),
                "m_Channels": ch,
                "m_DataSize": pts.tobytes(),
            },
            m_LocalAABB=bounds,
            m_BindPose=[],
            m_BoneNameHashes=[],
            m_BonesAABB=[],
            m_RootBoneNameHash=0,
            m_BakedConvexCollisionMesh=b"",
            m_BakedTriangleCollisionMesh=b"",
            m_StreamData={"offset": 0, "size": 0, "path": ""},
            m_MeshLodInfo={
                "m_LodSelectionCurve": {"m_LodSlope": 0.0, "m_LodBias": 0.0},
                "m_NumLevels": 1,
                "m_SubMeshes": [{"m_Levels": [{"m_IndexStart": 0, "m_IndexCount": k}]}],
            },
        )
        return self.put("Mesh", t)

    def render(self, g, mesh, mats):
        self.part(g, "MeshFilter", {"m_Mesh": mesh})
        t = self.baseval("MeshRenderer")
        t.update(m_Materials=mats, m_LightmapIndex=65535, m_LightmapIndexDynamic=65535)
        return self.part(g, "MeshRenderer", t)

    def box(self, g, col):
        t = self.baseval("BoxCollider")
        t.update(m_Center=xyz(col[:3]), m_Size=xyz(col[3:]))
        return self.part(g, "BoxCollider", t)

    def lod(self, g, renderers, center, size, thresholds):
        t = self.baseval("LODGroup")
        t.update(
            m_LocalReferencePoint=xyz(center),
            m_Size=float(size),
            m_LODs=[
                {
                    "screenRelativeHeight": float(q),
                    "fadeTransitionWidth": 0.0,
                    "renderers": [{"renderer": pp(r)}],
                }
                for q, r in zip(thresholds, renderers)
            ],
        )
        return self.part(g, "LODGroup", t)


STOCK_MODELS = {
    "pine": ([64, 62, 63], [22, 21], 0.5, 9.73),
    "broadleaf": ([65, 60, 61], [20, 23], 0.7, 9.84),
    "orchard_tree": ([65, 60, 61], [20, 23], 0.43, 6.05),
    "brush": ([67, 69, 68], [18], 1.0, 2.1),
}


def build(b, h, weights, items):
    s = Scene(b)
    root = s.node("Barbarossa_Polesie_Summer")
    tg = s.node("Field_Polesie", root, (-700, 0, -700), layer=8, tag=20000)
    at = s.texture("Polesie_Splat_512", Image.fromarray(weights), True, True)
    layerrefs = [s.external(ONE, 449), s.external(ONE, 450)]
    for name, im in zip(["StandingRye", "TilledLoam"], props.crops()):
        tid = s.texture("Polesie_" + name, im)
        source = b.files[ONE].objects[450]
        t = s.from_file(ONE, assert_roundtrip(source))
        t.update(
            m_Name="Polesie_" + name,
            m_DiffuseTexture=pp(tid),
            m_NormalMapTexture=pp(),
            m_MaskMapTexture=pp(),
            m_TileSize={"x": 9.0, "y": 9.0},
        )
        layerrefs.append(pp(s.put("TerrainLayer", t, src=source)))
    source = b.files[FOUR].objects[126]
    data = s.from_file(FOUR, assert_roundtrip(source))
    data["m_Name"] = "Polesie_FieldData"
    data["m_SplatDatabase"].update(m_TerrainLayers=layerrefs, m_AlphaTextures=[pp(at)])
    bounds, errs = patch_tree(h)
    data["m_Heightmap"].update(
        m_Heights=h.ravel().tolist(),
        m_MinMaxPatchHeights=bounds,
        m_PrecomputedError=errs,
        m_Scale=xyz((L.SIZE / (L.RES - 1), 64, L.SIZE / (L.RES - 1))),
    )
    td = s.put("TerrainData", data, src=source)
    tr = s.base.objects[155402]
    t = parse_complete(tr)
    raw = tr.get_raw_data()
    restored = encode_complete(tr, t)
    check(
        [i for i, (a, c) in enumerate(zip(raw, restored)) if a != c] == [195]
        and len(raw) == len(restored) == 200,
        "Unexpected Terrain padding",
    )
    t["m_TerrainData"] = pp(td)
    v = bytearray(encode_complete(tr, dict(t, m_GameObject=pp(tg))))
    v[195] = raw[195]
    s.part(tg, "Terrain", bytes(v), src=tr, raw=True)
    co = s.base.objects[149672]
    t = assert_roundtrip(co)
    t["m_TerrainData"] = pp(td)
    s.part(tg, "TerrainCollider", t, src=co)
    water = s.node("Water Daytime", root, (0, L.WATER, 0), scale=(700, 1, 700), layer=4)
    s.render(water, s.external(THREE, 79), [s.external(THREE, 6)])
    atlas = s.texture("Polesie_Timber_Atlas", props.atlas())
    mat = s.material(atlas)
    templates = {}
    archetypes = {}
    for k in sorted({o["kind"] for o in items}):
        if k in STOCK_MODELS:
            continue
        lods = [props.make(k, j) for j in (0, 1)]
        lo = lods[0][0].min(axis=0)
        hi = lods[0][0].max(axis=0)
        templates[k] = (
            [s.mesh(k + "_LOD" + str(j), a) for j, a in enumerate(lods)],
            (hi + lo) * 0.5,
            max(hi - lo),
        )
        archetypes[k] = lods
    groups = {}
    anchors = s.node("Mission Anchors", root)
    for name, (x, z) in L.ANCHORS.items():
        s.node(
            name,
            anchors,
            (
                x,
                L.DECK
                if name in [q[0] for q in L.BRIDGES]
                else float(L.ground(h, x, z)),
                z,
            ),
        )
    walls = s.node("Field Wall", root)
    for lab, x, z, dx, dz in [
        ("North", 0, 705, 1420, 10),
        ("South", 0, -705, 1420, 10),
        ("East", 705, 0, 10, 1420),
        ("West", -705, 0, 10, 1420),
    ]:
        s.box(
            s.node("Field Wall " + lab, walls, (x, 0, z), layer=20),
            (0, 44, 0, dx, 100, dz),
        )
    for i, p in enumerate(items):
        k, gr = p["kind"], p["group"]
        if gr not in groups:
            groups[gr] = s.node(gr, root)
        is_tree = k in STOCK_MODELS
        is_bridge = k.endswith("_bridge")
        g = s.node(
            f"{k}_{i:04}",
            groups[gr],
            (p["x"], p["y"], p["z"]),
            quat(p["yaw"]),
            p["scale"],
            8 if is_bridge else 17,
            20000 if is_bridge else (20011 if is_tree else 20005),
        )
        rs = []
        if is_tree:
            meshes, mats, scale, size = STOCK_MODELS[k]
            center = (0, size * 0.5, 0)
            ths = (0.1009, 0.0464, 0.0125) if k != "brush" else (0.08, 0.035, 0.009)
            bbox = b.files[FOUR].objects[meshes[0]]
            if k == "brush":
                extent = np.array(
                    list(parse_complete(bbox)["m_LocalAABB"]["m_Extent"].values())
                )
                scale = 2.1 / max(2 * extent)
                center = tuple(
                    v * scale
                    for v in parse_complete(bbox)["m_LocalAABB"]["m_Center"].values()
                )
            for j, m in enumerate(meshes):
                rs.append(
                    s.render(
                        s.node("LOD" + str(j), g, scale=scale),
                        s.external(FOUR, m),
                        [s.external(FOUR, v) for v in mats],
                    )
                )
            if k != "brush":
                s.box(g, (0, size * 0.23, 0, 0.28, 0.46 * size, 0.28))
        else:
            meshes, center, size = templates[k]
            ths = (0.063, 0.006) if not is_bridge else (0.08, 0.006)
            for j, m in enumerate(meshes):
                rs.append(s.render(s.node("LOD" + str(j), g), pp(m), [pp(mat)]))
            for c in props.BOXES[k]:
                s.box(g, c)
        s.lod(g, rs, center, size, ths)
    src_light = s.base.objects[148730]
    lz = parse_complete(s.base.objects[62963])
    sun = s.node(
        "Directional light Field Polesie", root, (0, 500, 0), lz["m_LocalRotation"]
    )
    light = s.part(
        sun,
        "Light",
        struct.pack("<iq", 0, sun) + src_light.get_raw_data()[12:],
        src=src_light,
        raw=True,
    )
    rs = s.base.objects[148729]
    r = assert_roundtrip(rs)
    r.update(m_Sun=pp(light), m_FogDensity=0.00145)
    s.put("RenderSettings", r, src=rs)
    empty = b.files["level20"]
    lm = next(
        o for o in s.base.objects.values() if o.type.name == "LightmapSettings"
    )  # Use the field's own unbaked lighting and matching external slots. Preserve the Unity 6 tail.
    s.put("LightmapSettings", lm.get_raw_data(), src=lm, raw=True)
    ns = next(o for o in empty.objects.values() if o.type.name == "NavMeshSettings")
    s.put("NavMeshSettings", {"m_NavMeshData": pp()}, src=ns)
    c = s.node("Map Preview Camera", None, (-315, 90, -203), quat(43, 24), tag=5)
    cam = next(o for o in empty.objects.values() if o.type.name == "Camera")
    cv = assert_roundtrip(cam)
    cv.update(
        {
            "near clip plane": 0.3,
            "far clip plane": 2000.0,
            "field of view": 53.0,
            "orthographic": False,
            "m_ClearFlags": 1,
            "m_OcclusionCulling": False,
            "m_TargetTexture": pp(),
            "m_CullingMask": {"m_Bits": 0xFFFFFFFF},
        }
    )
    s.part(c, "Camera", cv, src=cam)
    return s.finish(), archetypes


def register(b):
    """Append the environment slot, keeping every existing scene index and manager object."""
    sf = b.files["globalgamemanagers"]
    bs = next(o for o in sf.objects.values() if o.type.name == "BuildSettings")
    v = assert_roundtrip(bs)
    check(
        len(v["scenes"]) == 21
        and v["scenes"][-1].endswith("/Test_Select.unity")
        and "level21" not in b.files,
        "Scene slot 21 is already occupied",
    )
    v["scenes"].append(SCENE_PATH)
    bs.set_raw_data(encode_complete(bs, v))
    return sf.save()
