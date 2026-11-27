"""Authored, fictional early-summer Polesie landscape in the stock Field_04 coordinate system.
World origin at centre; +Z is map north. No missions, real coordinates or unit placement.
"""

import itertools
import math

import numpy as np

SIZE, HALF, RES, ALPHA, WATER, DECK, SEED = 1400, 700.0, 257, 512, 8.0, 11.25, 194106
# Route points are in metres. Both bridge approaches stay straight and level.
ROADS = {
    "village_road": (
        12.0,
        [
            (-700, -161),
            (-535, -143),
            (-432, -114),
            (-322, -83),
            (-205, -58),
            (-111, -43),
            (-22, -30),
            (90, -30),
            (208, -30),
            (312, -30),
            (413, -51),
            (530, -33),
            (625, -6),
            (700, 16),
        ],
    ),
    "north_lane": (
        9.0,
        [
            (-432, -114),
            (-414, -7),
            (-385, 112),
            (-317, 230),
            (-215, 302),
            (-73, 329),
            (69, 337),
            (211, 337),
            (298, 317),
            (391, 253),
            (452, 169),
            (501, 60),
            (530, -33),
        ],
    ),
    "south_farm_lane": (
        7.5,
        [
            (-205, -58),
            (-215, -154),
            (-252, -256),
            (-261, -352),
            (-347, -459),
            (-391, -556),
            (-405, -700),
        ],
    ),
    "wood_lane": (
        7.0,
        [(-317, 230), (-409, 306), (-502, 356), (-564, 440), (-600, 556), (-653, 700)],
    ),
    "east_farm_lane": (
        7.0,
        [(391, 253), (445, 339), (514, 426), (575, 488), (603, 595), (634, 700)],
    ),
    "mill_lane": (
        7.0,
        [
            (413, -51),
            (389, -139),
            (375, -239),
            (300, -344),
            (238, -420),
            (278, -526),
            (316, -620),
            (315, -700),
        ],
    ),
    "orchard_lane": (
        6.0,
        [(-22, -30), (-45, 34), (-95, 101), (-133, 182), (-131, 256), (-73, 329)],
    ),
}
RZ = np.array(
    [
        -700,
        -592,
        -506,
        -424,
        -346,
        -266,
        -200,
        -125,
        -30,
        64,
        149,
        236,
        337,
        429,
        498,
        578,
        700,
    ]
)
RX = np.array(
    [146, 195, 220, 202, 155, 116, 120, 154, 150, 89, 78, 112, 142, 118, 84, 68, 106]
)
BRIDGES = [
    ("village_bridge", 150.0, -30.0, 72.0, 8.8),
    ("meadow_bridge", 142.0, 337.0, 64.0, 7.6),
]
POND = (-103.0, -342.0, 48.0, 28.0)
ANCHORS = {
    "west_road": (-609, -151),
    "village_green": (-177, -48),
    "orchard": (-73, 60),
    "south_farm": (-254, -305),
    "mill_yard": (353, -263),
    "east_road": (584, -17),
    "north_meadow": (-158, 317),
    "wood_lane": (-483, 347),
    "east_hamlet": (375, 253),
    "village_bridge": (150, -30),
    "meadow_bridge": (142, 337),
}
# Elliptical woodland masses, broken up by fields, small clearings, roads and river banks.
WOODS = [
    (-534, 532, 209, 193),
    (-632, 159, 153, 158),
    (-528, -437, 188, 223),
    (-86, -592, 171, 149),
    (349, -516, 172, 184),
    (563, -316, 183, 143),
    (602, 450, 146, 204),
    (16, 549, 142, 183),
    (271, 86, 89, 76),
    (-357, 124, 73, 92),
    (-76, -238, 70, 64),
]


def smooth(x):
    t = np.clip(x, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def curve(z):
    """Local cubic Hermite interpolation for a continuous stream centre and tangent."""
    z = np.asarray(z)
    i = np.clip(np.searchsorted(RZ, z, side="right") - 1, 0, len(RZ) - 2)
    d = RZ[i + 1] - RZ[i]
    t = (z - RZ[i]) / d
    m = np.gradient(RX, RZ)
    return (
        (2 * t**3 - 3 * t * t + 1) * RX[i]
        + (t**3 - 2 * t * t + t) * d * m[i]
        + (-2 * t**3 + 3 * t * t) * RX[i + 1]
        + (t**3 - t * t) * d * m[i + 1]
    )


def river_width(z):
    return 12.9 + 2.2 * np.sin((z + 40) / 117) + 1.35 * np.cos(z / 64)


def shore(x, z):
    return np.abs(x - curve(z)) / np.sqrt(
        1 + ((curve(z + 1) - curve(z - 1)) * 0.5) ** 2
    ) - river_width(z)


def ellipse(x, z, a, b, rx, rz):
    return np.sqrt(((x - a) / rx) ** 2 + ((z - b) / rz) ** 2)


def smooth_road(points):
    # Straight segments at the bridge mouths; elsewhere gently round the authored bends.
    a = np.array(points, dtype=float)
    p = [a[0]]
    for prev, mid, nxt in zip(a, a[1:], a[2:]):
        k = min(16.0, np.linalg.norm(mid - prev) * 0.2, np.linalg.norm(nxt - mid) * 0.2)
        u = mid + (prev - mid) * k / np.linalg.norm(prev - mid)
        v = mid + (nxt - mid) * k / np.linalg.norm(nxt - mid)
        for t in (0.0, 0.25, 0.5, 0.75, 1.0):
            p.append((1 - t) ** 2 * u + 2 * t * (1 - t) * mid + t * t * v)
    return np.array([*p, a[-1]])


LINES = {name: (width, smooth_road(points)) for name, (width, points) in ROADS.items()}


def road_dist(x, z):
    d = np.full(np.broadcast(x, z).shape, 9999.0, dtype=np.float32)
    for width, points in LINES.values():
        for (a, b), (c, e) in itertools.pairwise(points):
            dx, dz = c - a, e - b
            t = np.clip(((x - a) * dx + (z - b) * dz) / (dx * dx + dz * dz), 0, 1)
            d = np.minimum(d, np.hypot(x - a - t * dx, z - b - t * dz) - width * 0.5)
    return d


_segments = np.array(
    [
        (a, b, c, e, width / 2)
        for width, pts in LINES.values()
        for (a, b), (c, e) in itertools.pairwise(pts)
    ]
).T


def clearance(x, z):
    a, b, c, e, w = _segments
    dx, dz = c - a, e - b
    t = np.clip(((x - a) * dx + (z - b) * dz) / (dx * dx + dz * dz), 0, 1)
    return float(np.min(np.hypot(x - a - t * dx, z - b - t * dz) - w))


def fieldplots():
    rng = np.random.default_rng(SEED)
    plots = []
    # Adjacent, unequal strips with grassy balks. Different farms use different alignments.
    for x, z, ang, n, length, spacing in [
        (-361, -257, -16, 8, 157, 32),
        (-457, 42, -12, 7, 149, 30),
        (-252, 126, 21, 6, 122, 29),
        (-128, -139, 8, 6, 118, 23),
        (-222, 416, 12, 8, 144, 33),
        (-483, 296, 34, 6, 110, 26),
        (392, 92, -21, 8, 154, 30),
        (511, -191, 18, 7, 145, 30),
        (346, 419, 30, 7, 122, 26),
        (22, -507, 20, 6, 132, 31),
        (497, 572, -17, 5, 110, 33),
    ]:
        a = math.radians(ang)
        c, s = math.cos(a), math.sin(a)
        for j in range(n):
            step = (j - (n - 1) / 2) * spacing
            ox = rng.uniform(-10, 10)
            plots.append(
                (
                    x + c * step - s * ox,
                    z + s * step + c * ox,
                    spacing * rng.uniform(0.73, 0.90),
                    length * rng.uniform(0.79, 1.12),
                    c,
                    s,
                    ("rye", "soil", "rye", "pasture", "soil", "rye")[
                        (j + len(plots) // 5) % 6
                    ],
                )
            )
    return plots


PLOTS = fieldplots()


def fields(x, z):
    rye = np.zeros(np.broadcast(x, z).shape, np.float32)
    soil = rye.copy()
    allf = rye.copy()
    for a, b, w, l, c, s, kind in PLOTS:
        dx = x - a
        dz = z - b
        u = dx * c + dz * s
        v = -dx * s + dz * c
        d = np.minimum(
            w * 0.5 - np.abs(u + 1.2 * np.sin(v / 23 + a * 0.31)),
            l * 0.5 - np.abs(v + 0.7 * np.sin(u / 16 + b * 0.34)),
        )
        f = smooth((d + 1.4) / 3.0)
        allf = np.maximum(allf, f)
        if kind == "rye":
            rye = np.maximum(rye, f)
        if kind == "soil":
            soil = np.maximum(soil, f)
    return rye, soil, allf


def groves(x, z):
    val = np.zeros(np.broadcast(x, z).shape, np.float32)
    for a, b, rx, rz in WOODS:
        val = np.maximum(val, 1 - ellipse(x, z, a, b, rx, rz))
    return val + 0.087 * np.sin(x / 31 + z / 57) + 0.05 * np.cos(z / 17 - x / 41)


def height(x, z):
    x = np.asarray(x)
    z = np.asarray(z)
    bank = shore(x, z)
    h = (
        20
        + 4.0 * np.sin(x / 184 + z / 285)
        + 3.1 * np.cos(z / 131 - x / 238)
        + 1.5 * np.sin(x / 57 + z / 91)
        + 1.1 * np.cos(z / 49)
    )
    for a, b, rx, rz, amp in [
        (-490, 447, 248, 210, 19),
        (516, -390, 300, 223, 14),
        (-383, -478, 243, 168, 7),
        (355, 382, 154, 145, 7),
    ]:
        h += amp * np.exp(-(ellipse(x, z, a, b, rx, rz) ** 2))
    # Higher dry ground grades through wet grass to a shallow, asymmetric floodplain.
    bed = 5.5 + 0.50 * np.sin(z / 47)
    h = (
        bed
        + (8.35 - bed) * smooth((bank + 10) / 11)
        + (12.2 - 8.35) * smooth((bank - 1) / 23)
        + (h - 12.2) * smooth((bank - 24) / 245)
    )
    p = ellipse(x, z, *POND)
    pond = 5.9 + 2.2 * smooth((p - 0.45) / 0.55)
    h = pond + (h - pond) * smooth((p - 0.94) / 0.64)
    for name, bx, bz, length, width in BRIDGES:
        away = np.abs(x - bx)
        belt = (1 - smooth((np.abs(z - bz) - width * 0.55) / 11)) * (
            1 - smooth((away - length / 2 - 9) / 42)
        )
        edge = smooth((away - (length / 2 - 18)) / 13)
        h += belt * edge * (DECK - h)
    return h


def grid(n, tex=False):
    v = np.linspace(-HALF, HALF, n + 1 if tex else n, dtype=np.float32)
    v = (v[:-1] + v[1:]) / 2 if tex else v
    return np.meshgrid(v, v)


def heightgrid():
    x, z = grid(RES)
    return np.rint(np.clip(height(x, z) / 64, 0, 1) * 32766).astype("<u2")


def ground(h, x, z):
    # Barycentric sampling on the same small quads used by the preview. Quantized samples in metres.
    u = np.clip((np.asarray(x) + HALF) * (RES - 1) / SIZE, 0, RES - 1 - 1e-6)
    v = np.clip((np.asarray(z) + HALF) * (RES - 1) / SIZE, 0, RES - 1 - 1e-6)
    i = u.astype(int)
    j = v.astype(int)
    du = u - i
    dv = v - j
    a = h[j, i].astype(float)
    b = h[j, i + 1].astype(float)
    c = h[j + 1, i].astype(float)
    d = h[j + 1, i + 1].astype(float)
    return (a + (b - a) * du + (c - a) * dv + (d - c - b + a) * np.minimum(du, dv)) * (
        64 / 32766
    )


def splat(items=()):
    x, z = grid(ALPHA, True)
    d = road_dist(x, z)
    rng = np.random.default_rng(703)
    j = rng.random(x.shape) * 0.75
    rye, soil, _ = fields(x, z)
    dry = smooth((shore(x, z) - 15) / 21) * smooth((ellipse(x, z, *POND) - 1.22) / 0.3)
    r = 1 - smooth((d + 1 + j) / 3.2)
    # Dirt access to each gate + a worked kitchen strip behind the cottage. Paint the
    # narrow regions locally so the stock terrain layer count and control resolution remain unchanged.
    coords = np.linspace(-HALF + SIZE / ALPHA / 2, HALF - SIZE / ALPHA / 2, ALPHA)
    aa, bb, cc, ee, _ww = _segments
    for o in items:
        if not o["kind"].startswith("cottage"):
            continue
        px, pz = o["x"], o["z"]
        vx = cc - aa
        vz = ee - bb
        t = np.clip(((px - aa) * vx + (pz - bb) * vz) / (vx * vx + vz * vz), 0, 1)
        qx0 = aa + vx * t
        qz0 = bb + vz * t
        i = np.argmin(np.hypot(px - qx0, pz - qz0))
        qx, qz = qx0[i], qz0[i]
        v = np.array([px - qx, pz - qz])
        ll = np.linalg.norm(v)
        ux, uz = v / ll
        gx, gz = px + ux * 13, pz + uz * 13
        sx = slice(
            np.searchsorted(coords, min(px, qx, gx) - 22),
            np.searchsorted(coords, max(px, qx, gx) + 22),
        )
        sz = slice(
            np.searchsorted(coords, min(pz, qz, gz) - 22),
            np.searchsorted(coords, max(pz, qz, gz) + 22),
        )
        xx, zz = x[sz, sx], z[sz, sx]
        frac = np.clip(((xx - qx) * ux + (zz - qz) * uz) / ll, 0, 1)
        dist = np.hypot(xx - qx - frac * ll * ux, zz - qz - frac * ll * uz)
        access = 1 - smooth((dist - 1.9) / 2.1)
        yard = 0.62 * (1 - smooth((np.hypot(xx - px, zz - pz) - 5.2) / 4.1))
        r[sz, sx] = np.maximum(r[sz, sx], np.maximum(access, yard))
        a = (xx - gx) * ux + (zz - gz) * uz
        b = -(xx - gx) * uz + (zz - gz) * ux
        bed = smooth((6.1 - np.abs(a)) / 1.45) * smooth((8 - np.abs(b)) / 1.45)
        soil[sz, sx] = np.maximum(soil[sz, sx], bed * 0.9)
        rye[sz, sx] *= 1 - bed * 0.92
    w = (1 - r) * dry
    rye *= w
    soil *= (w - rye).clip(0, 1)
    raw = np.stack([1 - r - rye - soil, r, rye, soil], axis=-1)
    a = np.floor(np.clip(raw, 0, 1) * 255).astype(np.uint8)
    v = 255 - a.sum(axis=2, dtype=np.int16)
    xx = np.indices(v.shape)
    a[xx[0], xx[1], raw.argmax(axis=2)] += v.astype("u1")
    return a


def road_z(x):
    pts = np.array(ROADS["village_road"][1])
    return np.interp(x, pts[:, 0], pts[:, 1])


def placements(h):
    rng = np.random.default_rng(SEED)
    out = []
    occupied = []

    def add(kind, x, z, yaw=0.0, scale=1.0, group="village", y=None, space=0.0):
        if kind in (
            "cottage_log",
            "cottage_lime",
            "cottage_shingle",
            "barn",
            "shed",
            "well",
            "windmill",
            "fence",
            "haystack",
        ):
            rr = {
                "cottage_log": 7.4,
                "cottage_lime": 7.4,
                "cottage_shingle": 7.4,
                "barn": 8.5,
                "shed": 5.1,
                "well": 2.1,
                "windmill": 7.3,
                "fence": 4.2,
                "haystack": 3.5,
            }[kind] * scale
            opts = [(0, 0)] + [
                (d * math.cos(t), d * math.sin(t))
                for d in range(3, 43, 3)
                for t in np.arange(16) * math.pi / 8
            ]
            for dx, dz in opts:
                xx, zz = x + dx, z + dz
                if (
                    clearance(xx, zz) >= rr + 1
                    and shore(xx, zz) > 14
                    and not any(
                        math.hypot(xx - a, zz - b) < rr + r + 0.6
                        for a, b, r in occupied
                    )
                ):
                    x, z = xx, zz
                    break
            else:
                raise ValueError(f"No clear yard for {kind}")
            space = rr
        obj = {
            "kind": kind,
            "x": round(float(x), 3),
            "z": round(float(z), 3),
            "y": round(float(ground(h, x, z) if y is None else y), 4),
            "yaw": round(float(yaw), 3),
            "scale": round(float(scale), 4),
            "group": group,
        }
        out.append(obj)
        if space:
            occupied.append((x, z, space))

    for ii, x in enumerate([-388, -342, -299, -251, -203, -159, -107, -59]):
        for side in [-1, 1]:
            if (ii, side) in [(0, -1), (2, 1), (4, 1), (6, -1)]:
                continue
            xx = x + (8 if side < 0 else -2)
            zz = road_z(xx) + side * rng.uniform(19, 26)
            yaw = (200 if side > 0 else 18) + rng.uniform(-7, 7)
            add(
                ["cottage_log", "cottage_lime", "cottage_shingle"][
                    ((ii * 3) // 2 + (side > 0)) % 3
                ],
                xx,
                zz,
                yaw,
                1.0,
                "street_village",
                space=10,
            )
            sx = xx + 12
            sz = zz + side * 17
            add(
                "barn" if ii % 3 == 1 else "shed",
                sx,
                sz,
                yaw + 90,
                1.0,
                "street_village",
                space=9,
            )
            for q in (-1, 1):
                add("fence", xx + q * 8, zz - side * 7, yaw - 15, 1.0, "farm_fences")
    farms = [
        (-244, -307, 24, "south_farm"),
        (355, -259, -31, "mill_yard"),
        (367, 245, 115, "east_hamlet"),
        (422, 274, 122, "east_hamlet"),
        (-276, 283, -36, "north_farm"),
        (-74, 59, -27, "orchard"),
        (-510, 365, -34, "wood_farm"),
    ]
    for i, (x, z, a, g) in enumerate(farms):
        add(
            ["cottage_lime", "cottage_shingle", "cottage_log"][i % 3],
            x,
            z,
            a,
            1.0,
            g,
            space=10,
        )
        add("barn", x + 18, z + 10, a + 82, 1.0, g, space=11)
        add("shed", x - 15, z + 13, a + 5, 0.94, g, space=8)
        add("haystack", x + 24, z + 23, 0, 1.0, g, space=5)
        add("fence", x - 8, z - 9, a, 1.0, g)
    add("windmill", 330, -278, -15, 1.0, "mill_yard", space=12)
    add("well", -166, -64, 0, 1.0, "street_village", space=3)
    add("well", 386, 255, 0, 1.0, "east_hamlet", space=3)
    for k, x, z, l, w in BRIDGES:
        add(k, x, z, 0, 1.0, "crossings", DECK)
    for gx, gz in [(-109, 73), (-275, -329), (385, 278)]:
        for i in range(3):
            for j in range(4):
                x = gx + i * 11 + rng.uniform(-1.2, 1.2)
                z = gz + j * 11 + rng.uniform(-1.2, 1.2)
                if (
                    min(
                        (math.hypot(x - a, z - b) - r for a, b, r in occupied),
                        default=999,
                    )
                    > 1
                    and road_dist(x, z) > 3
                ):
                    add(
                        "orchard_tree",
                        x,
                        z,
                        rng.uniform(-180, 180),
                        rng.uniform(0.72, 1.04),
                        "orchards",
                        space=2.2,
                    )
    # Stratified scatter; shared stock tree meshes, no per-frame generator. Every cluster is repeatable.
    v = np.arange(-681, 690, 18.5)
    x, z = np.meshgrid(v, v)
    x = x.ravel() + rng.uniform(-6.8, 6.8, x.size)
    z = z.ravel() + rng.uniform(-6.8, 6.8, z.size)
    d = road_dist(x, z)
    _, _, f = fields(x, z)
    g = groves(x, z)
    bank = shore(x, z)
    pond = ellipse(x, z, *POND)
    accept = (
        (d > 6)
        & (bank > 3)
        & (pond > 1.18)
        & (f < 0.2)
        & ((g > 0.15) | ((bank < 22) & (rng.random(len(x)) < 0.35)))
        & (rng.random(len(x)) < np.clip(0.27 + g * 0.74, 0, 0.84))
    )
    for i in np.flatnonzero(accept):
        a, b = x[i], z[i]
        if any(math.hypot(a - p, b - q) < r + 4 for p, q, r in occupied):
            continue
        kind = (
            "pine"
            if g[i] > 0.31 and bank[i] > 65 and rng.random() < 0.53
            else "broadleaf"
        )
        add(
            kind,
            a,
            b,
            rng.uniform(0, 360),
            rng.uniform(0.70, 1.26),
            f"woodland_{int((a + 700) // 200)}_{int((b + 700) // 200)}",
        )
    # Garden shade, broken fruit rows and small hay piles make the lane read as worked ground.
    for k, o in enumerate([v for v in out if v["kind"].startswith("cottage")]):
        for j in range(3 if k % 4 else 2):
            angle = k * 2.39996 + j * 2.12
            dest = None
            for rr in (11, 15, 19, 23):
                a, b = o["x"] + rr * math.cos(angle), o["z"] + rr * math.sin(angle)
                if clearance(a, b) > 4 and all(
                    math.hypot(a - p, b - q) > r + 2.1 for p, q, r in occupied
                ):
                    dest = (a, b)
                    break
            if dest:
                add(
                    "orchard_tree",
                    *dest,
                    rng.uniform(-180, 180),
                    rng.uniform(0.78, 1.14),
                    o["group"],
                    space=2.2,
                )
    for z0 in np.arange(-650, 664, 14.5):
        for side in (-1, 1):
            a = curve(z0) + side * (river_width(z0) + rng.uniform(0.4, 3.8))
            b = z0 + rng.uniform(-5, 5)
            if (
                clearance(a, b) > 9
                and WATER - 0.65 < float(ground(h, a, b)) < WATER + 2.9
            ):
                add(
                    "reeds",
                    a,
                    b,
                    rng.uniform(-180, 180),
                    rng.uniform(0.78, 1.25),
                    "river_reeds",
                )
    for i in range(0, len(x), 5):
        a, b = x[i], z[i]
        if not (2 < bank[i] < 23 and d[i] > 3 and pond[i] > 1.2) or any(
            math.hypot(a - p, b - q) < r + 2 for p, q, r in occupied
        ):
            continue
        add("brush", a, b, rng.uniform(0, 360), rng.uniform(0.7, 1.35), "river_meadow")
    return out
