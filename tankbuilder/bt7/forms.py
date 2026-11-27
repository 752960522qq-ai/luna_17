"""Small replacement shapes for damaged meshes, in their original local bounds."""

from itertools import pairwise

import numpy as np


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


class Form:
    def __init__(self):
        self.pos = []
        self.nor = []
        self.uv = []
        self.ind = []

    def face(self, verts, normal, uv=None):
        pts = np.asarray(verts)
        n = unit(np.asarray(normal))
        i = len(self.pos)
        if np.dot(np.cross(pts[1] - pts[0], pts[2] - pts[0]), n) < 0:
            pts = pts[::-1]
        self.pos.extend(pts)
        self.nor.extend([n] * len(pts))
        self.uv.extend(
            uv if uv is not None else [(0, 0), (1, 0), (1, 1), (0, 1)][: len(pts)]
        )
        for j in range(1, len(pts) - 1):
            self.ind.extend([i, i + j, i + j + 1])

    def box(self, center, size):
        lo = np.asarray(center) - np.asarray(size) / 2
        hi = lo + size
        vs = np.array(
            [[hi[k] if i & (1 << k) else lo[k] for k in range(3)] for i in range(8)]
        )
        for face, n in [
            ([0, 1, 3, 2], (0, 0, -1)),
            ([4, 6, 7, 5], (0, 0, 1)),
            ([0, 4, 5, 1], (0, -1, 0)),
            ([2, 3, 7, 6], (0, 1, 0)),
            ([0, 2, 6, 4], (-1, 0, 0)),
            ([1, 5, 7, 3], (1, 0, 0)),
        ]:
            self.face(vs[face], n)

    def tube(self, path, radius, steps=12, cap=True):
        path = np.array(path, float)
        rings = []
        for i, p in enumerate(path):
            t = unit(path[min(len(path) - 1, i + 1)] - path[max(i - 1, 0)])
            v = unit(np.cross(t, [1, 0, 0] if abs(t[0]) < 0.85 else [0, 0, 1]))
            u = np.cross(v, t)
            rings.append(
                [
                    p + radius * (v * np.cos(a) + u * np.sin(a))
                    for a in np.arange(steps) * 2 * np.pi / steps
                ]
            )
        for i, (a, b) in enumerate(pairwise(rings)):
            for j in range(steps):
                k = (j + 1) % steps
                vs = [a[j], a[k], b[k], b[j]]
                normal = np.mean(vs, axis=0) - (path[i] + path[i + 1]) / 2
                self.face(vs, normal)
        if cap:
            for r, p, n in [
                (rings[0], path[0], path[0] - path[1]),
                (rings[-1], path[-1], path[-1] - path[-2]),
            ]:
                for j in range(steps):
                    self.face([r[j], r[(j + 1) % steps], p], n)

    def arrays(self):
        return tuple(
            np.array(x, dtype=np.uint32 if i == 3 else float)
            for i, x in enumerate((self.pos, self.nor, self.uv, self.ind))
        )


def repaired_shape(k):
    f = Form()
    if (
        k == 149
    ):  # Curved front and chamfered, flat-sided mantlet. Local +Z is up in source FBX.
        cross = [
            (-0.43, -0.42),
            (-0.50, -0.24),
            (-0.50, 0.28),
            (-0.35, 0.46),
            (0.12, 0.50),
            (0.42, 0.37),
            (0.50, 0.13),
            (0.50, -0.22),
            (0.33, -0.48),
            (-0.18, -0.50),
        ]
        for j, (a, b) in enumerate(cross):
            c, d = cross[(j + 1) % len(cross)]
            v = [(-0.5, a, b), (0.5, a, b), (0.5, c, d), (-0.5, c, d)]
            f.face(v, (0, d - b, a - c))
        for side in (-1, 1):
            for j, (a, b) in enumerate(cross):
                c, d = cross[(j + 1) % len(cross)]
                f.face(
                    [(side * 0.5, 0, 0), (side * 0.5, a, b), (side * 0.5, c, d)],
                    (side, 0, 0),
                )
    elif k in (169, 170):
        f.tube(
            [
                (0, -0.46, -0.44),
                (0, -0.36, -0.16),
                (0, -0.16, 0.11),
                (0, 0.25, 0.31),
                (0, 0.46, 0.38),
            ],
            0.135,
            18,
        )
    elif 178 <= k <= 181:
        f.box([0, 0, -0.06], [0.91, 0.94, 0.83])
        f.box([0, 0, 0.41], [1, 1, 0.12])
        for x in (-0.3, 0.3):
            f.box([x, -0.47, 0.13], [0.07, 0.055, 0.24])
    elif k in (186, 187):
        f.box([0, 0, 0], [0.91, 0.95, 0.94])
        f.box([0, -0.1, 0.34], [1, 1, 0.29])
    elif k in (190, 191):
        f.box([0, 0, 0], [1, 0.68, 0.68])
    elif 159 <= k <= 164:
        f.tube([(0, 0, -0.46), (0, 0, 0.45)], 0.46, 8)
    elif k in (133, 134, 151, 152, 155, 156, 172, 173):
        f.tube(
            [(-0.27, -0.41, -0.32), (0.07, -0.03, -0.15), (0.28, 0.42, 0.34)], 0.16, 9
        )
    else:
        f.box([0, 0, 0], [1, 1, 1])
    return f.arrays()


def coil():
    f = Form()
    t = np.linspace(0, 2 * np.pi * 10, 81)
    f.tube(
        np.stack(
            [0.39 * np.cos(t), 0.39 * np.sin(t), np.linspace(-0.47, 0.47, len(t))],
            axis=1,
        ),
        0.072,
        5,
    )
    return f.arrays()
