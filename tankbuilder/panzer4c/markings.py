"""Choose exposed vertical plate sections before projecting opaque-safe Balkenkreuze onto them."""

import numpy as np

from ..panzer2f.surface import cross


def mount(tri, ax, sign, prefer, size):
    uv = [2, 1] if ax == 0 else [0, 1]
    proj = tri[:, :, uv]
    lo = proj.min(1)
    hi = proj.max(1)
    res = 0.0125
    org = lo.min(0) - 0.03
    shape = np.ceil((hi.max(0) + 0.03 - org) / res).astype(int) + 1
    dep = np.full((shape[1], shape[0]), -np.inf)
    for pts, z in zip((proj - org) / res, sign * tri[:, :, ax]):
        a, b, c = pts[0], pts[1] - pts[0], pts[2] - pts[0]
        det = b[0] * c[1] - b[1] * c[0]
        if abs(det) < 1.0e-5:
            continue
        x0, y0 = np.ceil(pts.min(0)).astype(int)
        x1, y1 = np.floor(pts.max(0)).astype(int)
        if x0 > x1 or y0 > y1:
            continue
        y, x = np.ogrid[y0 : y1 + 1, x0 : x1 + 1]
        dx = x - a[0]
        dy = y - a[1]
        u = (dx * c[1] - dy * c[0]) / det
        v = (dy * b[0] - dx * b[1]) / det
        d = z[0] + u * (z[1] - z[0]) + v * (z[2] - z[0])
        old = dep[y0 : y1 + 1, x0 : x1 + 1]
        np.maximum(
            old,
            np.where((u >= -1e-7) & (v >= -1e-7) & (u + v <= 1.0000001), d, -np.inf),
            out=old,
        )
    for sz in [size, 0.20, 0.176, 0.15]:
        h = int(np.ceil(sz / (2 * res)))
        candidates = []
        for iy in range(h + 1, dep.shape[0] - h - 1, 3):
            for ix in range(h + 1, dep.shape[1] - h - 1, 4):
                st = org + np.array([ix, iy]) * res
                if not (
                    (1.25 < st[1] < 1.64 and abs(st[0]) < 2.22)
                    if ax == 0
                    else (0.75 < st[1] < 1.61 and abs(st[0]) < 1.14)
                ):
                    continue
                if dep[iy, ix] < (1.02 if ax == 0 else 1.9):
                    continue
                tile = dep[iy - h : iy + h + 1, ix - h : ix + h + 1]
                if not np.isfinite(tile).all():
                    continue
                sx = (tile[h, -1] - tile[h, 0]) / (2 * h)
                sy = (tile[-1, h] - tile[0, h]) / (2 * h)
                if max(abs(sx), abs(sy)) > 0.70 * res:
                    continue
                pred = (
                    tile[h, h]
                    + sx * np.arange(-h, h + 1)[None, :]
                    + sy * np.arange(-h, h + 1)[:, None]
                )
                err = float(np.max(abs(tile - pred)))
                if err > 0.006:
                    continue
                candidates.append(
                    (err * 50 + np.linalg.norm((st - prefer) * [0.7, 2]), ix, iy)
                )
        for _, ix, iy in sorted(candidates)[:15]:
            st = org + np.array([ix, iy]) * res
            nearby = tri[np.logical_and(lo < st + sz, hi > st - sz).all(1)]
            try:
                marks, center = cross(nearby, nearby, ax, sign, st, sz)
            except ValueError:
                continue
            return marks, center, sz
    raise ValueError(("No exposed plate", ax, sign))
