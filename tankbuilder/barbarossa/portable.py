"""A self-contained glTF viewer copy: same height samples, splat weights, props and placements."""

import io
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image
from UnityPy.helpers.MeshHelper import MeshHandler

from . import layout as L
from . import props
from .native import FOUR, ONE, STOCK_MODELS, parse_complete


def imbytes(im, fmt):
    b = io.BytesIO()
    im.save(
        b,
        format=fmt,
        **(
            {"quality": 91, "subsampling": 0}
            if fmt == "JPEG"
            else {"compress_level": 5}
        ),
    )
    return b.getvalue()


def paint_ground(b, weights, res=2048):
    # Filter the source tiling textures to a pixel footprint before sampling; prevents moiré in the map view.
    grass, earth = [
        b.files[ONE].objects[k].read().image.convert("RGB") for k in (107, 144)
    ]
    crop, soil = props.crops()
    pal = [(grass, 5.0), (earth, 10.0), (crop, 9.0), (soil, 9.0)]
    v = (np.arange(res, dtype=np.float32) + 0.5) / res * L.SIZE - L.HALF
    colors = np.zeros((res, res, 3), np.float32)
    # Four channels are independent weights, not RGBA colours: do not alpha-premultiply during upscale.
    for i, (tex, tile) in enumerate(pal):
        n = max(8, round(res * tile / L.SIZE))
        t = np.asarray(tex.resize((n, n), Image.Resampling.LANCZOS), np.float32)
        u = ((v + L.HALF) / tile * n) % n
        ui = u.astype(int)
        f = (u - ui).astype("f4")
        a = (
            np.asarray(
                Image.fromarray(weights[:, :, i]).resize(
                    (res, res), Image.Resampling.BILINEAR
                ),
                np.float32,
            )
            / 255
        )
        tx = t[:, ui] * (1 - f[None, :, None]) + t[:, (ui + 1) % n] * f[None, :, None]
        col = (
            tx[(-ui - 1) % n] * (1 - f[:, None, None])
            + tx[(-ui - 2) % n] * f[:, None, None]
        )
        colors += a[..., None] * col
    return Image.fromarray(np.uint8(np.clip(colors, 0, 255))[::-1])


class GLB:
    def __init__(self):
        self.b = bytearray()
        self.views = []
        self.acc = []
        self.mesh = []
        self.nodes = []
        self.mats = []
        self.tex = []
        self.images = []

    def view(self, b, target=0):
        self.b.extend(bytes(-len(self.b) % 4))
        v = {"buffer": 0, "byteOffset": len(self.b), "byteLength": len(b)}
        self.b.extend(b)
        if target:
            v["target"] = target
        self.views.append(v)
        return len(self.views) - 1

    def accessor(self, a, ty, component, target, limits=False):
        a = np.ascontiguousarray(a)
        v = {
            "bufferView": self.view(a.tobytes(), target),
            "componentType": component,
            "count": len(a),
            "type": ty,
        }
        if limits:
            v.update(min=a.min(axis=0).tolist(), max=a.max(axis=0).tolist())
        self.acc.append(v)
        return len(self.acc) - 1

    def mat(self, name, im=None, base=None, cut=False, fmt="PNG"):
        p = {
            "baseColorFactor": base or [1.0, 1.0, 1.0, 1.0],
            "metallicFactor": 0.0,
            "roughnessFactor": 0.94,
        }
        if im is not None:
            view = self.view(imbytes(im, fmt))
            i = len(self.tex)
            self.images.append(
                {
                    "name": name,
                    "bufferView": view,
                    "mimeType": "image/jpeg" if fmt == "JPEG" else "image/png",
                }
            )
            self.tex.append({"source": i, "sampler": 0})
            p["baseColorTexture"] = {"index": i}
        m = {"name": name, "pbrMetallicRoughness": p, "doubleSided": cut}
        if cut:
            m.update(alphaMode="MASK", alphaCutoff=0.36)
        self.mats.append(m)
        return len(self.mats) - 1

    def geometry(self, name, v, n, uv, submeshes):
        # Unity +Z -> glTF -Z, reverse winding once; UV origin goes from bottom to top.
        v = np.asarray(v, "<f4").copy()
        n = np.asarray(n, "<f4")[:, :3].copy()
        uv = np.asarray(uv, "<f4").copy()
        v[:, 2] *= -1
        n[:, 2] *= -1
        uv[:, 1] = 1 - uv[:, 1]
        attrs = {
            "POSITION": self.accessor(v, "VEC3", 5126, 34962, True),
            "NORMAL": self.accessor(n, "VEC3", 5126, 34962),
            "TEXCOORD_0": self.accessor(uv, "VEC2", 5126, 34962),
        }
        ps = []
        for ix, mat in submeshes:
            ix = np.asarray(ix).reshape(-1, 3)[:, [0, 2, 1]].ravel()
            dtype = "<u4" if len(v) > 65535 else "<u2"
            ps.append(
                {
                    "attributes": attrs,
                    "indices": self.accessor(
                        ix.astype(dtype),
                        "SCALAR",
                        5125 if dtype == "<u4" else 5123,
                        34963,
                    ),
                    "material": mat,
                }
            )
        self.mesh.append({"name": name, "primitives": ps})
        return len(self.mesh) - 1

    def node(self, name, mesh=None, pos=None, yaw=0, scale=1.0, parent=None):
        o = {"name": name}
        j = len(self.nodes)
        self.nodes.append(o)
        if mesh is not None:
            o["mesh"] = mesh
        if pos is not None:
            o["translation"] = [float(pos[0]), float(pos[1]), float(-pos[2])]
        if yaw:
            a = math.radians(-yaw) * 0.5
            o["rotation"] = [0.0, math.sin(a), 0.0, math.cos(a)]
        if scale != 1.0:
            o["scale"] = [float(scale)] * 3
        if parent is not None:
            self.nodes[parent].setdefault("children", []).append(j)
        return j

    def write(self, path):
        self.b.extend(bytes(-len(self.b) % 4))
        d = {
            "asset": {
                "version": "2.0",
                "generator": "luna_17 / Polesie portable field",
            },
            "scene": 0,
            "scenes": [{"name": "Barbarossa · Polesie", "nodes": [0]}],
            "nodes": self.nodes,
            "meshes": self.mesh,
            "materials": self.mats,
            "images": self.images,
            "textures": self.tex,
            "samplers": [
                {"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}
            ],
            "accessors": self.acc,
            "bufferViews": self.views,
            "buffers": [{"byteLength": len(self.b)}],
        }
        j = json.dumps(d, separators=(",", ":")).encode()
        j += b" " * (-len(j) % 4)
        Path(path).write_bytes(
            struct.pack("<4sII", b"glTF", 2, 28 + len(j) + len(self.b))
            + struct.pack("<I4s", len(j), b"JSON")
            + j
            + struct.pack("<I4s", len(self.b), b"BIN\0")
            + self.b
        )


def export(path, b, h, weights, items, archetypes=None):
    g = GLB()
    root = g.node("Polesie_Summer")
    ground_im = paint_ground(b, weights)
    ground_mat = g.mat("Stock meadow, tracks and strip fields", ground_im, fmt="JPEG")
    wood = g.mat("Weathered rural timber atlas", props.atlas())
    water = g.mat("Daylight water • portable still", base=[0.14, 0.28, 0.26, 1])
    x, z = L.grid(L.RES)
    yy = h.astype("f4") * (64 / 32766)
    dz, dx = np.gradient(yy, L.SIZE / (L.RES - 1))
    norm = np.stack([-dx, np.ones_like(dx), -dz], axis=-1)
    norm /= np.linalg.norm(norm, axis=2, keepdims=True)
    v = np.stack([x, yy, z], axis=-1).reshape(-1, 3)
    uv = np.stack([(x + 700) / 1400, (z + 700) / 1400], axis=-1).reshape(-1, 2)
    i = (np.arange(L.RES - 1)[:, None] * L.RES + np.arange(L.RES - 1)[None, :]).ravel()
    a, c, d, e = i, i + 1, i + L.RES, i + L.RES + 1
    ix = np.column_stack([a, d, e, a, e, c]).ravel()
    terrain = g.geometry("Field_257", v, norm.reshape(-1, 3), uv, [(ix, ground_mat)])
    g.node("Field_Polesie", terrain, parent=root)
    wm = g.geometry(
        "Water_Surface",
        [
            [-700, L.WATER, -700],
            [-700, L.WATER, 700],
            [700, L.WATER, 700],
            [700, L.WATER, -700],
        ],
        [[0, 1, 0]] * 4,
        [(0, 0), (0, 1), (1, 1), (1, 0)],
        [([0, 1, 2, 0, 2, 3], water)],
    )
    g.node("Water Daytime", wm, parent=root)
    mats = {}
    kit = {}
    tree_scale = {}
    for k in sorted({o["kind"] for o in items}):
        if k not in STOCK_MODELS:
            arr = archetypes[k][0] if archetypes else props.make(k, 0)
            kit[k] = g.geometry(k, *arr[:3], [(arr[3], wood)])
            continue
        meshes, mm, sc, _si = STOCK_MODELS[k]
        raw = b.files[FOUR].objects[meshes[0] if k == "brush" else meshes[1]]
        mh = MeshHandler(raw.read())
        mh.process()
        ms = []
        for mat in mm:
            if mat not in mats:
                d = parse_complete(b.files[FOUR].objects[mat])
                ptr = next(
                    val["m_Texture"]["m_PathID"]
                    for n, val in d["m_SavedProperties"]["m_TexEnvs"]
                    if n == "_MainTex"
                )
                im = b.files[FOUR].objects[ptr].read().image.convert("RGBA")
                im.thumbnail((512, 512), Image.Resampling.LANCZOS)
                cut = mat in (18, 20, 21)
                mats[mat] = g.mat(
                    d["m_Name"],
                    im if cut else im.convert("RGB"),
                    cut=cut,
                    fmt="PNG" if cut else "JPEG",
                )
            ms.append(mats[mat])
        if k == "brush":
            sc = 2.1 / max(
                2
                * np.array(
                    list(parse_complete(raw)["m_LocalAABB"]["m_Extent"].values())
                )
            )
        tree_scale[k] = sc
        kit[k] = g.geometry(
            k, mh.m_Vertices, mh.m_Normals, mh.m_UV0, list(zip(mh.get_triangles(), ms))
        )
    groups = {}
    for i, o in enumerate(items):
        k, n = o["kind"], o["group"]
        if n not in groups:
            groups[n] = g.node(n, parent=root)
        g.node(
            f"{k}_{i:04}",
            kit[k],
            (o["x"], o["y"], o["z"]),
            o["yaw"],
            o["scale"] * tree_scale.get(k, 1),
            groups[n],
        )
    g.write(path)
    return ground_im
