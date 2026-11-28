"""Pick a continuous planar patch of the actual hull, including stowage in the visibility test."""
import numpy as np
from ..panzer2f.surface import cross, Project

def apply(tri,sign):
    c = tri.mean(1)
    tar = tri[(c[:, 0] * sign > 0.36) & (tri[:, :, 1].max(1) > 1.12) & (tri[:, :, 1].min(1) < 1.67)]
    xy = tar[:, :, [2, 1]]
    lo = xy.min(1)
    hi = xy.max(1)
    P = Project(tar, 0, sign)
    # Evaluate one regular depth image rather than refitting an arbitrary chosen face.
    xs = np.arange(-1.43, 1.36, 0.027)
    ys = np.arange(1.205, 1.55, 0.016)
    Z = np.array([[P.ray(np.array([x, y])) * sign for x in xs] for y in ys])
    for size in [.245,.22,.195,.17,.148,.129]:
        w = int(np.ceil(size / 0.054))
        h = int(np.ceil(size / 0.032))
        can = []
        for j in range(h,len(ys)-h):
            for i in range(w,len(xs)-w):
                tile = Z[j - h:j + h + 1, i - w:i + w + 1]
                mid = Z[j, i]
                if not np.isfinite(tile).all() or not .77<mid<1.40:
                    continue
                sy = (tile[-1, w] - tile[0, w]) / (2 * h)
                sx = (tile[h, -1] - tile[h, 0]) / (2 * w)
                if abs(sx)>.012 or abs(sy)>.011:
                    continue
                err = abs(tile - mid - sy * np.arange(-h, h + 1)[:, None] - sx * np.arange(-w, w + 1)).max()
                if err<.011:
                    can.append((err * 5 + abs(xs[i] - 0.12) * 0.03 + abs(ys[j] - 1.4) * 0.4, i, j))
        for _,i,j in sorted(can)[:12]:
            st = np.array([xs[i], ys[j]])
            near = tar[((lo < st + size * 0.75) & (hi > st - size * 0.75)).all(1)]
            try:
                return (*cross(near, near, 0, sign, st, size), size)
            except ValueError:
                pass
    raise ValueError(('No unobstructed marking on original side', sign))


def turret_mark(tri,sign):
    from ..panzer2f.surface import cross
    xy = tri[:, :, [2, 1]]
    lo = xy.min(1)
    hi = xy.max(1)
    for size in [.29,.255,.22]:
        for st in [(-.80,1.84),(-.64,1.83),(.41,1.82),(-.13,1.87)]:
            st = np.array(st)
            near = tri[((lo < st + size * 1.5) & (hi > st - size * 1.5)).all(1)]
            try:
                return (*cross(near, near, 0, sign, st, size), size)
            except ValueError:
                pass
    raise ValueError('Turret marking: could not project on a continuous side')

def painted(tri,sign,center,size):
    """A single nonoverlapping tessellation: paint the black core and white border on
    adjoining cells, not coplanar layered patches that intersect on stepped armour."""
    from ..bt7.source import Part
    from ..bt7.forms import unit
    center = np.asarray(center)
    p = Project(tri, 0, sign)
    stations = np.unique(np.r_[np.linspace(-0.5, 0.5, 11), -0.143, -0.073, 0.073, 0.143])
    geo = {k: ([], [], [], []) for k in ('kreuz_white', 'kreuz_black')}
    for a,b in zip(stations,stations[1:]):
        for c,d in zip(stations,stations[1:]):
            x, y = ((a + b) / 2, (c + d) / 2)
            if min(abs(x),abs(y))>.143:
                continue
            key = 'kreuz_black' if min(abs(x), abs(y)) < 0.073 else 'kreuz_white'
            v, n, uv, ix = geo[key]
            q = []
            for i,j in [(a,c),(b,c),(b,d),(a,d)]:
                st = center + np.array([i, j]) * size
                dep = p.ray(st)
                if not np.isfinite(dep):
                    raise ValueError('Marking projects into an opening')
                q.append([dep + sign * 0.0042, st[1], st[0]])
            q = np.array(q)
            no = unit(np.cross(q[1] - q[0], q[2] - q[0]))
            ix0 = np.array([0, 1, 2, 0, 2, 3])
            if no[0]*sign<0:
                no = -no
                ix0 = ix0[[0, 2, 1, 3, 5, 4]]
            ix.extend(len(v) + ix0)
            v.extend(q)
            n.extend([no] * 4)
            uv.extend([(a + 0.5, c + 0.5), (b + 0.5, c + 0.5), (b + 0.5, d + 0.5), (a + 0.5, d + 0.5)])
    return [Part(
        np.array(v),
        np.array(n),
        np.array(uv),
        np.array(ix),
        key
    ) for key, (v, n, uv, ix) in geo.items()]
