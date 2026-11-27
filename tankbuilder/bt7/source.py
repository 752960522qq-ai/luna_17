"""Extract the conical-turret vehicle only. Flatten the FBX transforms, including mirrored parts."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..modelrig import Model
from .forms import Form, coil, repaired_shape, unit

SOURCE_SHA = "74a007c51a6d331ead6883b58b153239de028c5043bd2233d7d2f096744340f7"
CREDIT = {
    "author": "Sankocho_DePoligonos",
    "title": "BT 5 & BT 7 Jatkosota (Girls und Panzer)",
    "source": "https://sketchfab.com/3d-models/bt-5-bt-7-jatkosota-girls-und-panzer-e03f7079630b43caae2ae2c7872a775e",
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "adaptation": "BT-7 isolated, repaired, rescaled, retextured and rigged for luna_17. Photos used as visual references only.",
}
ROAD = {49, 50, 137, 138, 139, 140, 141, 142}
SMALL = {33, 34, 194, 197}
SUSP_COILS = {110, 112, 114, 116, 118, 120}
TURRET = {55, 56, 57, 58, 59, 60, 106, 186, 187, 190, 191, 210, 214, 218, 221}
GUN = {38, 102, 103, 107, 149, 176}
BARREL = {17, 18}


@dataclass
class Part:
    v: np.ndarray
    n: np.ndarray
    uv: np.ndarray
    ix: np.ndarray
    m: object

    def transform(self, mat):
        v = self.v @ mat[:3, :3].T + mat[:3, 3]
        n = unit(self.n @ np.linalg.inv(mat[:3, :3]))
        ix = self.ix.reshape(-1, 3)
        if np.linalg.det(mat[:3, :3]) < 0:
            ix = ix[:, [0, 2, 1]]
        return Part(v, n, self.uv.copy(), ix.ravel(), self.m)


def read(path):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError(
            "Different source geometry; inspect before reusing this mapping"
        )
    m = Model(path)
    parents = m.parents()
    g = m.g
    parts = {}
    orig = {}
    world = {}

    def frame(i):
        if i not in world:
            o = g.nodes[i]
            if o.rotation or o.scale or o.translation:
                raise ValueError("Unreviewed source node transform")
            mat = np.array(o.matrix).reshape(4, 4).T if o.matrix else np.eye(4)
            world[i] = frame(parents[i]) @ mat if i in parents else mat
        return world[i]

    def arrays(k):
        p = g.meshes[k].primitives[0]
        return (
            m.array(p.attributes.POSITION).astype(float),
            m.array(p.attributes.NORMAL).astype(float),
            m.array(p.attributes.TEXCOORD_0).astype(float),
            m.array(p.indices).ravel().astype(int),
        )

    corrected = []
    origin = {}
    for i, o in enumerate(g.nodes):
        k = o.mesh
        if k is None:
            continue
        mat = frame(i)
        if mat[0, 3] > 2.12:
            continue  # Separate vehicle at (+4.26, -7.7); independent of material colour.
        orig[k] = mat
        origin[k] = mat[:3, 3].copy()
        p = g.meshes[k].primitives[0]
        v, n, uv, ix = arrays(k)
        ma = p.material
        if k in ROAD - {49, 50}:
            v, n, uv, ix = arrays(49)
            ma = g.meshes[49].primitives[0].material
            corrected.append(k)
        elif k in SUSP_COILS or np.ptp(v, axis=0).max() < 1e-6:
            a = g.accessors[p.attributes.POSITION]
            lo, hi = np.array(a.min), np.array(a.max)
            v, n, uv, ix = coil() if k in SUSP_COILS else repaired_shape(k)
            dims = np.maximum(hi - lo, 1e-5)
            r0 = v.min(axis=0)
            s = dims / np.maximum(np.ptp(v, axis=0), 1e-7)
            v = (v - r0) * s + lo
            n = unit(n / s)
            if k not in SUSP_COILS:
                corrected.append(k)
        s = Part(v, n, uv, ix, ma).transform(mat)
        tt = s.ix.reshape(-1, 3)
        face = s.v[tt]
        valid = (
            np.linalg.norm(
                np.cross(face[:, 1] - face[:, 0], face[:, 2] - face[:, 0]), axis=1
            )
            > 1e-11
        )
        if not valid.any():
            raise ValueError("No visible surface: " + str(k))
        s.ix = tt[valid].ravel()
        parts[k] = s
    # Scale the two fenders and belts to the cited overall envelope. Driver's sight is included in the height.
    allv = np.concatenate([p.v for p in parts.values()])
    lo, hi = allv.min(0), allv.max(0)
    floor = min(parts[k].v[:, 1].min() for k in (206, 207))
    roof = allv[:, 1].max()
    scale = np.array(
        [2.29 / (hi[0] - lo[0]), 2.42 / (roof - floor), 5.66 / (hi[2] - lo[2])]
    )
    b = np.eye(4)
    b[:3, :3] = np.diag(scale * [-1, 1, -1])
    b[:3, 3] = -b[:3, :3] @ [(hi[0] + lo[0]) / 2, floor, (hi[2] + lo[2]) / 2]
    origin = {k: b[:3, :3] @ v + b[:3, 3] for k, v in origin.items()}
    pieces = {k: p.transform(b) for k, p in parts.items()}
    for k in ROAD | SMALL:
        p = pieces[k]
        center = (p.v.min(0) + p.v.max(0)) / 2
        # Do not turn circular cross-sections into ellipses when applying envelope dimensions.
        p.v[:, 2] = center[2] + (p.v[:, 2] - center[2]) * scale[1] / scale[2]
    for k, side in [(190, -1), (191, 1)]:
        pieces[k] = weld(pieces[210], side)
    return m, pieces, origin, corrected


def track_from_guide(part):
    """Use the original outer edge, with a single arc-length UV direction for both sides."""
    px = part.v[:, 0]
    cx = (px.max() + px.min()) / 2
    half = np.ptp(px) / 2
    points = np.unique(
        np.round(part.v[np.isclose(px, px.max(), atol=2e-5), 1:], 6), axis=0
    )
    c = (points.min(0) + points.max(0)) / 2
    points = points[np.argsort(np.arctan2(points[:, 0] - c[0], points[:, 1] - c[1]))]
    i = np.argmin(points[:, 0] + np.abs(points[:, 1]) * 0.00002)
    points = np.roll(points, -i, axis=0)
    # The long bottom edge must run from the nose to the rear as glTF V increases.
    if points[1, 1] < points[0, 1]:
        points = np.concatenate([points[:1], points[:0:-1]])
    # Subdivide long straight edges for smooth portable suspension near each contact.
    a = []
    for v, w in zip(points, np.roll(points, -1, axis=0)):
        a.extend(
            np.linspace(
                v,
                w,
                max(1, int(np.ceil(np.linalg.norm(v - w) / 0.082))),
                endpoint=False,
            )
        )
    pts = np.array(a)
    t = unit(np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0))
    norm = np.column_stack([-t[:, 1], t[:, 0]])
    if np.sum(norm * (pts - c)) < 0:
        norm *= -1
    arc = np.r_[0.0, np.cumsum(np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1))]
    period = arc[-1] / 73
    # Correct drift at the seam: exactly 73 tile periods per lap, never a texture phase jump.
    v = []
    n = []
    uv = []
    ix = []

    def at(i, side, inside):
        yz = pts[i] - norm[i] * (0.036 if inside else 0)
        return [cx + side * half, yz[0], yz[1]]

    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        a = arc[i] / period
        b = arc[i + 1] / period
        for sg, ins, sg2, ins2, nn, u0, u1 in [
            (-1, 0, 1, 0, [0, *norm[i]], 0, 1),
            (1, 1, -1, 1, [0, *-norm[i]], 1, 0),
            (-1, 1, -1, 0, [-1, 0, 0], 0.016, 0.17),
            (1, 0, 1, 1, [1, 0, 0], 0.83, 0.984),
        ]:
            q = np.array(
                [at(i, sg, ins), at(i, sg2, ins2), at(j, sg2, ins2), at(j, sg, ins)]
            )
            ii = np.array([[0, 1, 2], [0, 2, 3]])
            if np.dot(np.cross(q[1] - q[0], q[2] - q[0]), nn) < 0:
                ii = ii[:, [0, 2, 1]]
            tail = [0, *(-norm[j] if ins and ins2 else norm[j])] if nn[0] == 0 else nn
            ix.extend((len(v) + ii).ravel())
            v.extend(q)
            n.extend([nn, nn, tail, tail])
            uv.extend([[u0, a], [u1, a], [u1, b], [u0, b]])
    return (
        Part(np.array(v), np.array(n), np.array(uv), np.array(ix), "tread"),
        float(period),
        float(arc[-1]),
    )


def surface_projector(shell, side):
    """Project each decal vertex onto the side armour, rather than floating a vertical billboard."""
    tri = shell.v[shell.ix.reshape(-1, 3)]
    a = tri[:, 0, 1:]
    b = tri[:, 1, 1:] - a
    c = tri[:, 2, 1:] - a
    den = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
    valid = abs(den) > 1e-10
    den = np.where(valid, den, 1.0)

    def project(yz):
        d = yz - a
        u = (d[:, 0] * c[:, 1] - d[:, 1] * c[:, 0]) / den
        v = (b[:, 0] * d[:, 1] - b[:, 1] * d[:, 0]) / den
        good = np.where(valid & (u >= -1e-5) & (v >= -1e-5) & (u + v <= 1.00001))[0]
        if not len(good):
            raise ValueError("Star falls outside turret armour")
        x = (
            tri[:, 0, 0]
            + u * (tri[:, 1, 0] - tri[:, 0, 0])
            + v * (tri[:, 2, 0] - tri[:, 0, 0])
        )
        j = good[np.argmax(x[good] * side)]
        return np.array([x[j] + side * 0.0028, *yz])

    return project


def weld(shell, side):
    project = surface_projector(shell, side)
    line = [
        project(np.array([y, -0.29 + 0.033 * (y - 1.67) / 0.47]))
        for y in np.linspace(1.67, 2.14, 10)
    ]
    f = Form()
    f.tube(line, 0.008, 7)
    v, n, uv, i = f.arrays()
    return Part(v, n, uv, i, 39)


def painted_star(shell, side, cy, cz, r=0.185):
    project = surface_projector(shell, side)
    center = np.array([cy, cz])
    angles = np.arange(10) * np.pi / 5
    radii = np.tile([r, r * 0.382], 5)
    ring = center + np.stack([np.cos(angles), np.sin(angles)], axis=1) * radii[:, None]
    form = Form()
    for i in range(10):
        a0, b0, c0 = center, ring[i], ring[(i + 1) % 10]

        def grid(j, k, a0=a0, b0=b0, c0=c0):
            return project(a0 + (b0 - a0) * j / 4 + (c0 - a0) * k / 4)

        for j in range(4):
            for k in range(4 - j):
                triples = [[grid(j, k), grid(j + 1, k), grid(j, k + 1)]]
                if j + k < 3:
                    triples.append([grid(j + 1, k), grid(j + 1, k + 1), grid(j, k + 1)])
                for f in triples:
                    no = unit(np.cross(f[1] - f[0], f[2] - f[0]))
                    form.face(f, no * np.sign(side * no[0]))
    v, n, _, i = form.arrays()
    uv = (v[:, [2, 1]] - [cz - r, cy - r]) / (2 * r)
    return Part(v, n, uv, i, "red")
