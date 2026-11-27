"""Rebuild a moving belt along the centers of the author's 94 individual shoes; paint the historic crosses on actual faces."""

import numpy as np
from PIL import Image, ImageDraw

from ..bt7.forms import unit
from ..bt7.source import Part


def tread_tile(shoe):
    # Look at an actual lower shoe from underneath and tile it at the measured source pitch.
    v = shoe.p.copy()
    v -= shoe.center
    w, h = 512, 208
    scaleX = w / np.ptp(v[:, :, 0])
    pitch = 187.2
    face = unit(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]))
    im = Image.new("RGB", (w, h), (37, 39, 40))
    d = ImageDraw.Draw(im)
    maxz = v[:, :, 2].min()
    cent = v.mean(1)
    for idx in np.argsort(-cent[:, 2]):
        tri = v[idx]
        lum = np.clip(
            72
            + (17 if abs(face[idx, 2]) > 0.85 else -14)
            + (-cent[idx, 2] + maxz + 12) * 0.23
            + face[idx, 1] * 14,
            31,
            112,
        )
        base = (int(lum * 1.03), int(lum), int(lum * 0.95))
        for shift in (-1, 0, 1):
            xy = [
                (float(x * scaleX + w / 2), float((y / pitch + 0.5 + shift) * h))
                for x, y, _ in tri
            ]
            d.polygon(xy, fill=base)
    return im


def belt(items, B):
    shoes = list(items)
    vs = [B.point(o.p.reshape(-1, 3)) for o in shoes]
    c = np.array([(v.min(0) + v.max(0)) / 2 for v in vs])
    mid = (c.min(0) + c.max(0)) / 2
    order = np.argsort(np.arctan2(c[:, 1] - mid[1], c[:, 2] - mid[2]))
    c = c[order]
    vs = [vs[i] for i in order]
    lo = min(x[:, 0].min() for x in vs)
    hi = max(x[:, 0].max() for x in vs)
    pts = c[:, 1:]
    off = np.roll(pts, -1, axis=0) - np.roll(pts, 1, axis=0)
    n = unit(np.column_stack([-off[:, 1], off[:, 0]]))
    if (n * (pts - mid[1:])).sum() < 0:
        n *= -1
    depth = np.array([((v[:, 1:] - p) @ nn).max() for v, p, nn in zip(vs, pts, n)])
    profile = pts + n * depth[:, None]
    flat = np.flatnonzero((profile[:, 0] < 0.008) & (np.abs(profile[:, 1]) < 1.1))
    start = flat[np.argmin(profile[flat, 1])]
    profile = np.roll(profile, -start, axis=0)
    if profile[1, 1] < profile[0, 1]:
        profile = np.concatenate([profile[:1], profile[:0:-1]])
    profile[:, 0] = np.maximum(profile[:, 0], 0)
    near = profile[:, 0] < 0.0015
    profile[near, 0] = 0
    prof = []
    for a, b in zip(profile, np.roll(profile, -1, axis=0)):
        prof.extend(np.linspace(a, b, 2, endpoint=False))
    yz = np.asarray(prof)
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.roll(yz, -1, axis=0) - yz, axis=1))]
    length = arc[-1]
    period = length / len(shoes)
    norm = unit(
        np.column_stack(
            [
                -(np.roll(yz, -1, axis=0) - np.roll(yz, 1, axis=0))[:, 1],
                (np.roll(yz, -1, axis=0) - np.roll(yz, 1, axis=0))[:, 0],
            ]
        )
    )
    if (norm * (yz - mid[1:])).sum() < 0:
        norm *= -1
    thickness = 0.0505
    v = []
    nn = []
    uv = []
    ix = []

    def point(i, x, h):
        return np.r_[x, yz[i] - norm[i] * h]

    for i in range(len(yz)):
        j = (i + 1) % len(yz)
        va = arc[i] / period
        vb = arc[i + 1] / period
        for x, h, x2, h2, side, us in [
            (lo, 0, hi, 0, "out", (0, 1)),
            (hi, thickness, lo, thickness, "in", (1, 0)),
            (lo, thickness, lo, 0, "left", (0.01, 0.18)),
            (hi, 0, hi, thickness, "right", (0.82, 0.99)),
        ]:
            q = np.array(
                [point(i, x, h), point(i, x2, h2), point(j, x2, h2), point(j, x, h)]
            )
            nt = (
                np.r_[0, norm[i] * (1 if side == "out" else -1)]
                if side in ("out", "in")
                else np.array([-1 if side == "left" else 1, 0, 0])
            )
            ntj = (
                np.r_[0, norm[j] * (1 if side == "out" else -1)]
                if side in ("out", "in")
                else nt
            )
            idx = np.array([[0, 1, 2], [0, 2, 3]])
            idx = (
                idx
                if np.cross(q[1] - q[0], q[2] - q[0]) @ nt > 0
                else idx[:, [0, 2, 1]]
            )
            ix.extend((len(v) + idx).ravel())
            v.extend(q)
            nn.extend([nt, nt, ntj, ntj])
            uv.extend([(us[0], va), (us[1], va), (us[1], vb), (us[0], vb)])
    return (
        Part(np.array(v), np.array(nn), np.array(uv), np.array(ix), "tread"),
        float(period),
        float(length),
        thickness,
    )


class Project:
    def __init__(self, tri, axis, sgn):
        self.axis = axis
        self.s = sgn
        self.uv = [2, 1] if axis == 0 else [0, 1]
        q = tri[:, :, self.uv]
        a = q[:, 0]
        b = q[:, 1] - a
        c = q[:, 2] - a
        den = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
        valid = abs(den) > 1e-9
        self.a = a[valid]
        self.b = b[valid]
        self.c = c[valid]
        self.den = den[valid]
        self.d = tri[valid, :, axis]
        self.lo = q[valid].min(1)
        self.hi = q[valid].max(1)

    def ray(self, v):
        mask = np.all((self.lo <= v + 1e-7) & (self.hi >= v - 1e-7), axis=1)
        d = v - self.a[mask]
        b = self.b[mask]
        c = self.c[mask]
        den = self.den[mask]
        u = (d[:, 0] * c[:, 1] - d[:, 1] * c[:, 0]) / den
        w = (b[:, 0] * d[:, 1] - b[:, 1] * d[:, 0]) / den
        f = (u >= -1e-5) & (w >= -1e-5) & (u + w <= 1.00001)
        vv = self.d[mask][f]
        u = u[f]
        w = w[f]
        if not len(vv):
            return np.nan
        x = vv[:, 0] + u * (vv[:, 1] - vv[:, 0]) + w * (vv[:, 2] - vv[:, 0])
        return self.s * np.max(self.s * x)


def cross(target, all_fixed, axis, sign, prefer, size):
    A = Project(target, axis, sign)
    B = Project(all_fixed, axis, sign)
    uv = A.uv
    best = None
    # Find a continuous, visibly exposed plane large enough for the printed marking.
    for du in (0, 0.045, -0.045, 0.09, -0.09, 0.15, -0.15, 0.21, -0.21, 0.29, -0.29):
        for dv in (0, 0.022, -0.022, 0.045, -0.045):
            center = prefer + [du, dv]
            samples = np.array(
                [
                    center + size * np.array([x, y])
                    for x in np.linspace(-0.5, 0.5, 4)
                    for y in np.linspace(-0.5, 0.5, 4)
                ]
            )
            depth = np.array([A.ray(p) for p in samples])
            if not np.isfinite(depth).all():
                continue
            # Reject surfaces split by protruding shelves, spare links, hinges or tools.
            full = np.array([B.ray(p) for p in samples])
            delta = np.max(abs(full - depth))
            res = np.max(
                abs(
                    np.column_stack([samples, np.ones(len(samples))])
                    @ np.linalg.lstsq(
                        np.column_stack([samples, np.ones(len(samples))]),
                        depth,
                        rcond=None,
                    )[0]
                    - depth
                )
            )
            score = res + delta + (0.21 * abs(du) + abs(dv)) * 0.009
            if res < 0.008 and delta < 0.004 and (best is None or score < best[0]):
                best = (score, center)
    if best is None:
        raise ValueError(f"No unobscured marking face {axis}/{sign}/{prefer}")
    center = best[1]
    pieces = []
    for label, extent, arm, dist in [
        ("kreuz_white", 0.5, 0.143, 0.0020),
        ("kreuz_black", 0.497, 0.073, 0.0030),
    ]:
        coords = np.array([-extent, -arm, arm, extent]) * size
        v = []
        n = []
        uvs = []
        ix = []
        for i in range(3):
            for j in range(3):
                if i != 1 and j != 1:
                    continue
                corners = [
                    (coords[i], coords[j]),
                    (coords[i + 1], coords[j]),
                    (coords[i + 1], coords[j + 1]),
                    (coords[i], coords[j + 1]),
                ]
                q = []
                for x, y in corners:
                    st = center + [x, y]
                    vec = np.empty(3)
                    vec[uv] = st
                    vec[axis] = A.ray(st) + dist * sign
                    q.append(vec)
                q = np.array(q)
                no = unit(np.cross(q[1] - q[0], q[2] - q[0]))
                idx = np.array([[0, 1, 2], [0, 2, 3]])
                if no[axis] * sign < 0:
                    no = -no
                    idx = idx[:, [0, 2, 1]]
                ix.extend((len(v) + idx).ravel())
                v.extend(q)
                n.extend([no] * 4)
                uvs.extend([(x / size + 0.5, y / size + 0.5) for x, y in corners])
        pieces.append(
            Part(np.array(v), np.array(n), np.array(uvs), np.array(ix), label)
        )
    return pieces, center.tolist()
