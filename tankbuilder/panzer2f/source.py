"""Recover functional islands from the supplied OBJ-style GLB; stay in the author's coordinates until final export."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from ..bt7.forms import unit
from ..bt7.source import Part
from ..modelrig import Model

HASH = "5f090a35d73477e5f8d36c56ec771f17797801b6e183fd5331060c4e857e7660"
ID = "Panzer_II_Ausf_F"
CREDIT = {
    "title": "Panzer II Light Tank - Toshueyi",
    "author": "Joanthan To (Toshueyi)",
    "source": "https://sketchfab.com/3d-models/panzer-ii-light-tank-toshueyi-e237b8939e4343aba3b9c55afed86321",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "adaptation": "Separated original rigid parts, recreated moving track surfaces from supplied shoes, textured, rescaled, marked and rigged for luna_17.",
}


def read(src):
    if hashlib.sha256(Path(src).read_bytes()).hexdigest() != HASH:
        raise ValueError("Different input; recheck the island mapping")
    model = Model(src)
    P = []
    N = []
    materials = []
    for mesh in model.g.meshes:
        p = mesh.primitives[0]
        idx = model.array(p.indices).reshape(-1, 3)
        P.append(model.array(p.attributes.POSITION)[idx])
        N.append(model.array(p.attributes.NORMAL)[idx])
        materials.extend([p.material] * len(idx))
    P = np.concatenate(P)
    N = np.concatenate(N)
    mat = np.array(materials)
    unique, rev = np.unique(np.round(P.reshape(-1, 3), 2), axis=0, return_inverse=True)
    tri = rev.reshape(-1, 3)
    a = tri.ravel()
    b = tri[:, [1, 2, 0]].ravel()
    count, cc = connected_components(
        coo_matrix((np.ones(len(a)), (a, b)), shape=(len(unique),) * 2), directed=False
    )
    cluster = cc[tri[:, 0]]
    assert count == 945
    result = {}
    for i in range(count):
        sel = np.flatnonzero(cluster == i)
        v = P[sel].astype(float)
        n = N[sel].astype(float)
        key = np.unique(mat[sel])
        assert len(key) == 1
        result[i] = Island(v, n, int(key[0]))
    return result


@dataclass
class Island:
    p: np.ndarray
    n: np.ndarray
    m: int

    @property
    def bounds(self):
        return self.p.min((0, 1)), self.p.max((0, 1))

    @property
    def center(self):
        a, b = self.bounds
        return (a + b) / 2

    @property
    def span(self):
        a, b = self.bounds
        return b - a


class Basis:
    def __init__(self, parts):
        lo = np.min([p.bounds[0] for p in parts.values()], axis=0)
        hi = np.max([p.bounds[1] for p in parts.values()], axis=0)
        roof = max(p.bounds[1][2] for i, p in parts.items() if i != 902)
        self.scale = np.array(
            [2.28 / (hi[0] - lo[0]), 4.81 / (hi[1] - lo[1]), 2.15 / (roof - lo[2])]
        )
        self.origin = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])

    def override(self, x):
        return x[..., [0, 2, 1]] * [-1, 1, 1]

    def point(self, x):
        return self.override((np.asarray(x) - self.origin) * self.scale)

    def normal(self, n):
        return unit(self.override(n / self.scale))

    def part(self, o, material):
        v = self.point(o.p)
        n = self.normal(o.n)
        flat = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
        ok = np.linalg.norm(flat, axis=1) > 2e-10
        v = v[ok]
        n = n[ok]
        flat = flat[ok]
        face_normal = unit(flat)
        dots = np.sum(n * face_normal[:, None, :], axis=2)
        bad = (np.linalg.norm(n, axis=2) < 0.40) | (dots < 0.82)
        n = np.where(bad[:, :, None], face_normal[:, None, :], n)
        if not len(v):
            return None
        # Box-projected physical UVs, including the originally textureless objects. Preserve per-corner normals.
        axis = np.argmax(np.abs(flat), axis=1)
        uv = np.empty((len(v), 3, 2))
        for dim, axes in enumerate(((2, 1), (0, 2), (0, 1))):
            uv[axis == dim] = v[axis == dim][:, :, axes] * [1.18, -1.18]
        allv = np.concatenate((v, n, uv), axis=2).reshape(-1, 8).astype("<f4")
        unique, ix = np.unique(allv, axis=0, return_inverse=True)
        return Part(unique[:, :3], unique[:, 3:6], unique[:, 6:8], ix, material)


def wheels(ps):
    # These are the tire, wheel disk, end-cap and axle centres recovered after welding OBJ material seams.
    # Each wheel has an independent X axis. Do not rotate leaf spring packs, fixed stub axles or fender spares.
    W = []
    owner = {}
    for tag, offset in [("left", 0), ("right", 1)]:
        rd = (
            list(zip(range(818, 823), range(827, 832)))
            if not offset
            else list(zip(range(161, 166), range(214, 219)))
        )
        rt = (
            list(zip(range(578, 582), range(823, 827)))
            if not offset
            else list(zip(range(190, 194), range(194, 198)))
        )
        for cls, items in [
            ("road", rd),
            ("return", rt),
            ("drive", [(833, 832, 809) if not offset else (180, 246, 247)]),
            ("idler", [(817,) if not offset else (122,)]),
        ]:
            for j, ids in enumerate(items):
                outer = ps[
                    ids[-1]
                    if cls in ("road", "return")
                    else ids[1]
                    if cls == "drive"
                    else ids[0]
                ]
                cen = outer.center.copy()
                span = outer.span
                if cls in ("road", "return"):
                    cen[0] = outer.center[0]
                rad = (span[1] + span[2]) / 4
                nm = (
                    "wheel_"
                    + tag[0]
                    + "_"
                    + (
                        f"{j + 1:02}"
                        if cls == "road"
                        else cls + (str(j + 1) if cls == "return" else "")
                    )
                )
                w = {
                    "name": nm,
                    "side": tag,
                    "kind": cls,
                    "center": cen,
                    "rawRadius": rad,
                    "parts": list(ids),
                }
                for i in ids:
                    owner[i] = nm
                if cls in ("drive", "idler"):
                    for i, o in ps.items():
                        if i in owner or o.m != 3:
                            continue
                        delta = o.center - cen
                        s = o.span
                        # End wheel bolts/castings rotate as one; axle bracket remains a hull component.
                        if (
                            abs(delta[0]) < 215
                            and np.linalg.norm(delta[1:]) < rad * 0.91
                            and s.max() < 265
                        ):
                            w["parts"].append(i)
                            owner[i] = nm
                W.append(w)
    return W, owner


def shoe_sets(ps):
    out = {k: [] for k in ("left", "right")}
    for i, o in ps.items():
        if o.m != 5 or len(o.p) != 117:
            continue
        x = o.center[0]
        side = "left" if x > 1000 else "right" if x < -1800 else None
        if side:
            out[side].append(i)
    assert [len(v) for v in out.values()] == [94, 94]
    return out
