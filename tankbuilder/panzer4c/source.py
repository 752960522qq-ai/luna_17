"""Recover the original C-model's UV-mapped mechanical parts from its material-only OBJ export."""

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from ..bt7.forms import unit
from ..bt7.source import Part
from ..modelrig import Model

ID = "Panzer_IV_Ausf_C"
INPUT = "7d38f1a8195a7d60812f4b47ed77a522500149bef43375a51a9873a2b397a3af"
CREDIT = {
    "title": "Pz Kpfw_IV_ Ausf._C",
    "author": "patoburro",
    "source": "https://sketchfab.com/3d-models/pz-kpfw-iv--ausf-c-8c6502b1ddf7484a91a2bf529ee8295e",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "adaptation": "Repainted original mapped UV atlases, separated wheel assemblies and turret, reparameterized the original belts, restored bogie articulation and added three markings for Hatch.",
}


@dataclass
class Island:
    p: np.ndarray
    n: np.ndarray
    uv: np.ndarray
    mesh: int
    atlas: int

    @property
    def box(self):
        return self.p.min((0, 1)), self.p.max((0, 1))

    @property
    def c(self):
        lo, hi = self.box
        return (lo + hi) / 2

    @property
    def span(self):
        lo, hi = self.box
        return hi - lo


def read(path):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != INPUT:
        raise ValueError(
            "Unexpected source geometry; audit island IDs before rebuilding."
        )
    m = Model(path)
    parts = {}
    images = {}
    for j, mesh in enumerate(m.g.meshes):
        pr = mesh.primitives[0]
        ix = m.array(pr.indices).reshape(-1, 3)
        p, n, uv = (
            m.array(getattr(pr.attributes, attr))[ix]
            for attr in ("POSITION", "NORMAL", "TEXCOORD_0")
        )
        un, re = np.unique(np.round(p.reshape(-1, 3), 4), axis=0, return_inverse=True)
        tri = re.reshape(-1, 3)
        a = tri.ravel()
        b = tri[:, [1, 2, 0]].ravel()
        count, cc = connected_components(
            coo_matrix((np.ones(len(a)), (a, b)), shape=(len(un),) * 2), directed=False
        )
        labels = cc[tri[:, 0]]
        atlas = m.g.materials[pr.material].extensions[
            "KHR_materials_pbrSpecularGlossiness"
        ]["diffuseTexture"]["index"]
        if atlas not in images:
            src = m.g.images[m.g.textures[atlas].source]
            vi = m.g.bufferViews[src.bufferView]
            images[atlas] = Image.open(
                io.BytesIO(m.blob[vi.byteOffset : vi.byteOffset + vi.byteLength])
            ).convert("RGBA")
        for k in range(count):
            sel = labels == k
            parts[j * 10000 + k] = Island(
                p[sel].astype(float),
                n[sel].astype(float),
                uv[sel].astype(float),
                j,
                atlas,
            )
    return parts, images


class Basis:
    def __init__(self, parts):
        lo = np.min([x.box[0] for x in parts.values()], axis=0)
        hi = np.max([x.box[1] for i, x in parts.items() if i != 20000], axis=0)
        self.off = np.r_[(lo[:2] + hi[:2]) / 2, lo[2]]
        self.sc = np.array([2.83, 5.92, 2.68]) / (hi - lo)

    def point(self, p):
        return ((np.asarray(p) - self.off) * self.sc)[..., [0, 2, 1]] * [-1, 1, 1]

    def normal(self, n):
        return unit((n / self.sc)[..., [0, 2, 1]] * [-1, 1, 1])


def primitive(v, n, uv, mat):
    flat = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    mask = np.linalg.norm(flat, axis=1) > 1e-10
    if not np.any(mask):
        return None
    v, n, uv = v[mask], n[mask], uv[mask]
    face = unit(flat[mask])
    n = np.where(
        (np.einsum("tnc,tc->tn", n, face) < 0.71)[:, :, None], face[:, None, :], n
    )
    raw = np.concatenate([v, unit(n), uv], axis=2).reshape(-1, 8).astype("<f4")
    values, ix = np.unique(raw, axis=0, return_inverse=True)
    return Part(values[:, :3], values[:, 3:6], values[:, 6:], ix.ravel(), mat)


def wheels(ps, B):
    ws = []
    owner = {}
    for side, sign in [("left", 1), ("right", -1)]:
        near = {
            i: o
            for i, o in ps.items()
            if o.mesh in (10, 11, 12, 13) and sign * o.c[0] > 1.015
        }
        for kind, ntri, select, expected in [
            ("road", 162, lambda o: 0.44 < o.span[2] < 0.50, 8),
            ("return", 126, lambda o: 0.23 < o.span[2] < 0.25 and abs(o.c[0]) > 1.2, 4),
            ("drive", 1276, lambda o: True, 1),
            ("idler", 336, lambda o: abs(o.c[0]) > 1.20 and 0.63 < o.span[2] < 0.67, 1),
        ]:
            seeds = sorted(
                ((i, o) for i, o in near.items() if len(o.p) == ntri and select(o)),
                key=lambda x: x[1].c[1],
            )
            if len(seeds) != expected:
                raise ValueError((side, kind, "seeds", len(seeds)))
            for seq, (idx, o) in enumerate(seeds, 1):
                cy, cz = o.c[1:]
                w = []
                for i, other in near.items():
                    if other.mesh not in (10, 12):
                        continue
                    d = np.linalg.norm(other.c[1:] - [cy, cz])
                    if d < 0.017 or (
                        kind in ("idler", "drive")
                        and d < (0.146 if kind == "drive" else 0.089)
                        and other.span.max() < 0.08
                        and abs(other.c[0]) > 1.24
                    ):
                        if i in owner:
                            raise ValueError("overlapping wheels")
                        w.append(i)
                cenraw = o.c.copy()
                cenraw[0] = sign * 1.19
                points = np.unique(o.p.reshape(-1, 3)[:, 1:], axis=0)
                # Some polygonal tires are clocked differently. Recover the real axle from the outside ring.
                rr = np.linalg.norm(points - [cy, cz], axis=1)
                sel = rr > rr.max() * 0.985
                ring = points[sel]
                if kind == "road" and len(ring) >= 6:
                    y, z = ring.T
                    fit = np.linalg.lstsq(
                        np.column_stack([2 * y, 2 * z, np.ones(len(y))]),
                        y * y + z * z,
                        rcond=None,
                    )[0]
                    cenraw[1:] = fit[:2]
                rad = float(np.linalg.norm(points - cenraw[1:], axis=1).max() * B.sc[2])
                name = f"wheel_{side[0]}_{seq:02d}_{kind}"
                bounds = [ps[p].box for p in w]
                cx = (
                    min(lo[0] for lo, hi in bounds) + max(hi[0] for lo, hi in bounds)
                ) / 2
                cenraw[0] = cx
                cen = B.point(cenraw)
                rec = {
                    "name": name,
                    "side": side,
                    "wheelKind": kind,
                    "roadWheel": kind == "road",
                    "sourceParts": w,
                    "rawCenter": cenraw,
                    "center": cen,
                    "radius": rad,
                }
                for k in w:
                    owner[k] = rec
                ws.append(rec)
    return ws, owner


def repaint(images, key):
    if key.startswith("kreuz_"):
        return Image.new(
            "RGB", (16, 16), (200, 200, 189) if key.endswith("white") else (23, 26, 27)
        )
    ix = 0 if key == "tread" else int(key.split("_")[-1])
    im = images[ix].copy()
    limit = 768 if ix in (12, 15) else 512
    im.thumbnail((limit, limit), Image.Resampling.LANCZOS)
    col = np.asarray(im, dtype=float)
    a = col[:, :, 3:] / 255.0
    rgb = col[:, :, :3]
    lum = rgb @ [0.30, 0.55, 0.15]
    # Preserve baked welds, wheel hubs, tools and fine cast shadows in their original UVs.
    if ix == 0:
        tone = 25 + 0.78 * lum
        v = tone[:, :, None] * [1.01, 1, 0.96]
        v = a * v + (1 - a) * [31, 32, 33]
    elif ix in (9, 26):
        v = rgb * a + (1 - a) * [103, 101, 87]
    elif ix == 20:
        v = (12 + 0.77 * lum)[:, :, None] * np.array([0.96, 1, 1.01])
    else:
        tone = 13 + 0.59 * lum
        v = tone[:, :, None] * [0.94, 1.005, 1.035]
        # Warm, well-saturated painted texture fragments on the tools retain their wood/oxide tint.
        delta = np.maximum(rgb[:, :, 0] - rgb[:, :, 2], 0)
        retain = np.clip((delta - 13) / 47, 0, 1) * (0.54 if ix in (3, 15) else 0.20)
        v = v * (1 - retain[:, :, None]) + rgb * retain[:, :, None]
        v = v * a + (1 - a) * [43, 46, 47]
    return Image.fromarray(np.clip(v, 0, 255).astype("uint8"))
