"""Shared low-poly rural kits. Dimensions are game metres; primitive UVs address a single atlas."""

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from .layout import BRIDGES

TILES = [
    "log",
    "plank",
    "thatch",
    "shingle",
    "lime",
    "stone",
    "brick",
    "glass",
    "trim",
    "door",
    "bark",
    "reed",
    "hay",
    "darkwood",
    "sill",
    "sail",
]
COLORS = [
    (111, 87, 63),
    (130, 108, 77),
    (155, 135, 92),
    (110, 111, 101),
    (191, 183, 150),
    (115, 110, 94),
    (139, 84, 58),
    (72, 96, 100),
    (124, 143, 133),
    (91, 75, 57),
    (100, 77, 55),
    (103, 120, 66),
    (177, 151, 92),
    (81, 68, 52),
    (165, 158, 134),
    (188, 177, 143),
]


def atlas():
    n = 128
    im = np.zeros((n * 4, n * 4, 3), np.uint8)
    rng = np.random.default_rng(415)
    y, x = np.mgrid[0:n, 0:n]
    for i, k in enumerate(TILES):
        base = np.array(COLORS[i])
        grain = rng.normal(0, 3.8, (n, n))
        v = grain + 3 * np.sin(x / 19 + y / 21) + 2 * np.cos(y / 8 - x / 27)
        if k == "log":
            r = (y + 0.8 * np.sin(x / 32)) % 16
            v += (
                10 * np.sin(np.pi * r / 16)
                - 26 * np.exp(-((r / 1.9) ** 2))
                + 3 * np.sin(y * 2 + 0.7 * np.cos(x / 9))
            )
        elif k in (
            "plank",
            "shingle",
            "door",
            "darkwood",
            "bark",
            "sail",
            "thatch",
            "hay",
        ):
            p = (x + np.sin(y / 38) * 1.3) % 16
            v += 4 * np.sin(x * 2 + 1.7 * np.sin(y / 19)) - (
                14 if k in ("plank", "door", "darkwood", "sail") else 3
            ) * np.exp(-(p**2) / 2)
            if k == "shingle":
                v -= 21 * ((y % 16 < 2) | ((x + ((y // 16) % 2) * 8) % 19 < 1))
                v += 6 * ((y % 16) / 16)
            if k in ("thatch", "hay"):
                v += 5 * np.sin(x * 2 + y * 0.22 + np.sin(y * 0.24)) + 2 * np.cos(
                    x * 0.3 + y * 0.32
                )
                v -= 5 * (y % 40 < 2)
        elif k in ("stone", "brick"):
            yt = (y + 1.8 * np.sin(x / 21)) % 15
            xt = (x + (y // 15 % 2) * 13 + 2 * np.cos(y / 24)) % 27
            v -= 20 * ((yt < 1.8) | (xt < 1.5))
            v += 5 * np.sin(x // 24 + 3 * (y // 15))
        elif k == "glass":
            v += 13 * np.cos((x + y) / 40) - 15 * (y / n)
        im[(i // 4) * n : (i // 4 + 1) * n, (i % 4) * n : (i % 4 + 1) * n] = np.uint8(
            np.clip(base + v[..., None], 0, 255)
        )
    return Image.fromarray(im)


def crops():
    n = 256
    j, i = np.mgrid[0:n, 0:n]
    r = np.random.default_rng(620)
    grain = r.normal(0, 7, (n, n))
    waves = np.sin(i * 2 * np.pi / 16 + 0.32 * np.sin(j * 2 * np.pi / 128))
    v = grain + 8 * waves + 4 * np.cos(j * 2 * np.pi / 128 + i * 2 * np.pi / 32)
    w = grain * 0.65 + 10 * waves + 4 * np.sin(i * 2 * np.pi / 4)
    return [
        Image.fromarray(np.uint8(np.clip(np.array(c) + a[..., None], 0, 255)))
        for c, a in [((147, 142, 77), v), ((116, 91, 64), w)]
    ]


@dataclass
class Mesh:
    v: list = field(default_factory=list)
    n: list = field(default_factory=list)
    uv: list = field(default_factory=list)
    idx: list = field(default_factory=list)

    def face(self, pts, side, tile, uv=None):
        pts = np.array(pts, float)
        normal = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        length = np.linalg.norm(normal)
        if length < 1e-7:
            raise ValueError("Degenerate face")
        normal /= length
        order = list(range(len(pts)))
        uv = uv or (
            [(0, 0), (1, 0), (0.5, 1)]
            if len(pts) == 3
            else [(0, 0), (1, 0), (1, 1), (0, 1)]
        )
        idx = TILES.index(tile)
        i = len(self.v)
        if np.dot(normal, side) < 0:
            order = order[::-1]
            normal = -normal
        for j in order:
            a, b = uv[j]
            self.uv.append(
                (
                    (idx % 4 + 0.012 + 0.976 * a) / 4,
                    1 - (idx // 4 + 0.988 - 0.976 * b) / 4,
                )
            )
            self.v.append(pts[j])
            self.n.append(normal)
        for j in range(1, len(order) - 1):
            self.idx.extend([i, i + j, i + j + 1])

    def box(self, x, y, z, w, h, d, t, axes=None):
        # y is bottom. Face-specific UVs keep log courses horizontal on every elevation.
        o = np.array([x, y + h / 2, z])
        basis = np.eye(3) if axes is None else np.asarray(axes)
        s = np.array([w, h, d]) * 0.5
        for k, sign, a, b in [
            (2, -1, 0, 1),
            (2, 1, 0, 1),
            (0, -1, 2, 1),
            (0, 1, 2, 1),
            (1, -1, 0, 2),
            (1, 1, 0, 2),
        ]:
            n = np.eye(3)[k] * sign
            corners = []
            for i, j in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
                v = n * s
                v[a] = i * s[a]
                v[b] = j * s[b]
                corners.append(o + basis @ v)
            self.face(corners, basis @ n, t)

    def beam(self, p, q, r, t):
        p, q = np.array(p), np.array(q)
        dir = q - p
        length = np.linalg.norm(dir)
        b = dir / length
        seed = np.array([0, 0, 1.0]) if abs(b[2]) < 0.88 else np.array([1.0, 0, 0])
        a = np.cross(b, seed)
        a /= np.linalg.norm(a)
        c = np.cross(a, b)
        v = (p + q) / 2
        self.box(
            v[0], v[1] - length / 2, v[2], r, length, r, t, np.column_stack([a, b, c])
        )

    def roof(self, x, y, z, w, d, rise, wall, cover):
        for sg in (-1, 1):
            self.face(
                [
                    (x - w / 2, y, z + sg * d / 2),
                    (x + w / 2, y, z + sg * d / 2),
                    (x, y + rise, z + sg * d / 2),
                ],
                (0, 0, sg),
                wall,
            )
            self.face(
                [
                    (x + sg * (w / 2 + 0.45), y - 0.14, z - d / 2 - 0.58),
                    (x + sg * (w / 2 + 0.45), y - 0.14, z + d / 2 + 0.58),
                    (x, y + rise + 0.10, z + d / 2 + 0.58),
                    (x, y + rise + 0.10, z - d / 2 - 0.58),
                ],
                (sg, 0.6, 0),
                cover,
            )

    def stack(self, x, y, z, rings, t, sides=10):
        for (ya, ra), (yb, rb) in itertools.pairwise(rings):
            for i in range(sides):
                a = i * math.tau / sides
                b = (i + 1) * math.tau / sides
                ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
                pts = [
                    (x + ra * ca, y + ya, z + ra * sa),
                    (x + ra * cb, y + ya, z + ra * sb),
                    (x + rb * cb, y + yb, z + rb * sb),
                    (x + rb * ca, y + yb, z + rb * sa),
                ]
                self.face(pts, (ca + cb, 0.3, sa + sb), t)

    def arrays(self):
        return (
            np.asarray(self.v, "<f4"),
            np.asarray(self.n, "<f4"),
            np.asarray(self.uv, "<f4"),
            np.asarray(self.idx, "<u4"),
        )


# Per archetype, simple colliders in local coordinates: centre X/Y/Z, width/height/depth.
BOXES = {}


def make(kind, lod):
    m = Mesh()
    col = []
    far = lod > 0
    if kind.startswith("cottage") or kind in ("shed", "barn"):
        hut = kind.startswith("cottage")
        w, d, y, r = (
            (6.1, 10.6, 2.65, 2.05)
            if hut
            else ((8.0, 13.5, 3.7, 2.8) if kind == "barn" else (4.8, 6.5, 2.02, 1.42))
        )
        wall = {
            "cottage_log": "log",
            "cottage_lime": "lime",
            "cottage_shingle": "log",
            "shed": "plank",
            "barn": "plank",
        }[kind]
        roof = (
            "thatch" if kind in ("cottage_log", "cottage_lime", "barn") else "shingle"
        )
        m.box(0, -0.8, 0, w + 0.2, 1.14, d + 0.18, "stone")
        m.box(0, 0.26, 0, w, y - 0.26, d, wall)
        m.roof(0, y, 0, w, d, r, wall, roof)
        col.append((0, (y - 0.6) / 2, 0, w, y + 0.6, d))
        if hut:
            m.box(w * 0.23, y + r * 0.43, -d * 0.22, 0.57, 1.7, 0.63, "brick")
            m.box(w * 0.23, y + r * 0.43 + 1.58, -d * 0.22, 0.67, 0.22, 0.72, "sill")
            for s in [-1, 1]:
                for z in [-d * 0.31, 0, d * 0.31]:
                    if s == 1 and z == 0:
                        continue
                    m.box(s * (w / 2 + 0.04), 0.98, z, 0.10, 1.08, 1.25, "trim")
                    m.box(s * (w / 2 + 0.105), 1.09, z, 0.035, 0.86, 1.0, "glass")
                    if not far:
                        m.box(s * (w / 2 + 0.13), 1.07, z, 0.044, 0.9, 0.064, "sill")
                        m.box(s * (w / 2 + 0.13), 1.47, z, 0.045, 0.065, 1.02, "sill")
                        m.box(s * (w / 2 + 0.11), 0.91, z, 0.15, 0.12, 1.39, "sill")
            m.box(w / 2 + 0.045, 0.27, 0, 0.12, 1.99, 1.02, "door")
            m.box(0, 1.04, d / 2 + 0.035, 1.10, 0.96, 0.09, "glass")
            if not far:
                m.box(w / 2 + 0.58, 0.05, 0, 1.18, 0.25, 1.47, "stone")
                m.box(
                    -w / 2 + 0.04, 0.28, -d / 2 + 0.06, 0.16, y - 0.28, 0.16, "darkwood"
                )
        else:
            door = w * (0.62 if kind == "barn" else 0.45)
            m.box(0, 0.05, d / 2 + 0.035, door, y * 0.77, 0.11, "door")
            if not far:
                for a in [-1, 1]:
                    m.beam(
                        (0, 0.24, d / 2 + 0.12),
                        (a * (door / 2 - 0.05), y * 0.71, d / 2 + 0.12),
                        0.13,
                        "sill",
                    )
    elif kind == "fence":
        for x in [-3.75, 0, 3.75]:
            m.box(x, -0.40, 0, 0.19, 1.64, 0.21, "darkwood")
        for y in [0.37, 0.84]:
            m.box(0, y, 0, 7.8, 0.14, 0.13, "plank")
        col = [(0, 0.48, 0, 7.8, 1.05, 0.25)]
    elif "bridge" in kind:
        _, _, _, l, w = next(b for b in BRIDGES if b[0] == kind)
        m.box(0, -0.40, 0, l, 0.40, w, "plank")
        col = [(0, -0.20, 0, l, 0.40, w)]
        for s in [-1, 1]:
            m.box(0, -0.92, s * w * 0.36, l, 0.60, 0.48, "darkwood")
            m.box(0, 0.89, s * (w / 2 - 0.13), l, 0.17, 0.15, "darkwood")
            col.append((0, 0.53, s * (w / 2 - 0.13), l, 1.08, 0.20))
            if not far:
                m.box(0, 0.40, s * (w / 2 - 0.13), l, 0.1, 0.12, "plank")
            for x in np.linspace(-l / 2 + 0.22, l / 2 - 0.22, 12 if not far else 7):
                m.box(x, -0.25, s * (w / 2 - 0.13), 0.23, 1.41, 0.25, "plank")
        for x in [-l * 0.3, 0, l * 0.3]:
            m.box(x, -1.12, 0, 0.55, 0.35, w + 0.20, "darkwood")
            for s in [-1, 1]:
                m.box(x, -7.0, s * w * 0.32, 0.47, 6.2, 0.47, "darkwood")
            if not far:
                m.beam((x, -4, -w * 0.32), (x, -1.14, w * 0.32), 0.28, "plank")
        if not far:
            for x in np.arange(-l / 2 + 0.4, l / 2, 0.69):
                m.box(x, -0.004, 0, 0.027, 0.009, w - 0.16, "darkwood")
    elif kind == "reeds":
        rng = np.random.default_rng(743)
        count = 6 if far else 14
        for i in range(count):
            a, b = rng.uniform(-1.65, 1.65, 2)
            h = rng.uniform(0.78, 1.78)
            dx, dz = rng.uniform(-0.23, 0.23, 2)
            m.beam(
                (a, -0.28, b), (a + dx, h, b + dz), 0.033 if not far else 0.058, "reed"
            )
            if i % 3 == 0:
                m.box(a + dx, h - 0.10, b + dz, 0.075, 0.26, 0.075, "darkwood")
            for q in [-1, 1]:
                p = [
                    (a - 0.055, 0.18, b),
                    (a + 0.055, 0.18, b),
                    (a + dx + q * 0.38, h * 0.70, b + dz + 0.1),
                ]
                m.face(p, (0, 0, 1), "reed")
                m.face(p, (0, 0, -1), "reed")
    elif kind == "haystack":
        m.stack(
            0,
            -0.35,
            0,
            [(0, 1.86), (0.76, 2.12), (1.6, 1.76), (2.55, 0.7), (2.83, 0.10)],
            "hay",
            7 if far else 13,
        )
        m.box(0, 2.38, 0, 0.12, 0.93, 0.12, "darkwood")
    elif kind == "well":
        m.stack(0, -0.38, 0, [(0, 1.1), (0.45, 1.14), (1.27, 1.04)], "stone", 8)
        m.box(0, 1.9, 0, 1.9, 0.22, 0.2, "plank")
        for x in [-0.84, 0.84]:
            m.box(x, 0.58, 0, 0.20, 1.94, 0.20, "darkwood")
        m.roof(0, 2.4, 0, 1.8, 1.6, 0.63, "plank", "shingle")
        col = [(0, 0.6, 0, 2.2, 1.2, 2.2)]
    elif kind == "windmill":
        m.stack(0, -0.65, 0, [(0, 3.45), (1.65, 3.48)], "stone", 8)
        m.stack(0, 0.95, 0, [(0, 3.38), (4.4, 2.96), (7.15, 2.38)], "plank", 8)
        m.stack(0, 8.07, 0, [(0, 2.65), (1.43, 0.12)], "shingle", 8)
        m.box(1.0, 3.35, -2.79, 0.70, 1.1, 0.22, "glass")
        m.box(-1.05, 6.05, -2.46, 0.65, 0.86, 0.20, "glass")
        m.box(0, -0.10, -2.99, 1.47, 2.15, 0.31, "door")
        cz = -3.0
        cy = 6.8
        for n in range(4):
            a = math.radians(27 + 90 * n)
            u = np.array([math.cos(a), math.sin(a), 0])
            v = np.array([-math.sin(a), math.cos(a), 0])
            o = np.array([0.0, cy, cz])
            m.beam(o, o + u * 6.4, 0.23, "darkwood")
            p = [
                o + u * 2.05,
                o + u * 6.08,
                o + u * 6.08 + v * 1.43,
                o + u * 2.05 + v * 0.89,
            ]
            m.face(p, (0, 0, -1), "sail")
            m.face(p, (0, 0, 1), "sail")
            if not far:
                for t in [2.2, 3.2, 4.2, 5.2, 6.1]:
                    m.beam(
                        o + u * t - 0.06 * np.array([0, 0, 1]),
                        o
                        + u * t
                        + v * (0.63 + 0.085 * (t - 2))
                        - 0.06 * np.array([0, 0, 1]),
                        0.08,
                        "darkwood",
                    )
        col = [(0, 3.7, 0, 5.4, 8.0, 5.4)]
    else:
        raise ValueError(kind)
    BOXES[kind] = col
    return m.arrays()
