"""North-up map derived from the serialized terrain samples and actual scenery positions."""

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import layout as L


def cartography(h, w, items, n=1024):
    v = (np.arange(n) + 0.5) * L.SIZE / n - L.HALF
    x, z = np.meshgrid(v, v[::-1])
    e = L.ground(h, x, z)
    p = np.stack(
        [
            np.asarray(
                Image.fromarray(w[:, :, i][::-1]).resize(
                    (n, n), Image.Resampling.BILINEAR
                ),
                dtype=np.float32,
            )
            / 255
            for i in range(4)
        ],
        axis=-1,
    )
    palette = np.array(
        [[120, 123, 83], [191, 172, 126], [163, 153, 92], [135, 118, 82]]
    )
    base = p @ palette
    dy, dx = np.gradient(e, L.SIZE / n)
    shade = np.clip(-dx * 0.7 + dy * 0.8, -0.35, 0.35) * 53
    # Subtle relief; field borders and wet meadows are visible without covering the roads.
    contours = np.maximum(0, 1 - np.abs((e + 0.0) % 4 - 2) / 0.09) * 0.7
    wet = np.clip((11.7 - e) / 3.7, 0, 1) * (1 - p[:, :, 1])
    base = (
        base * (1 - wet[:, :, None] * 0.3)
        + np.array([112, 139, 100]) * wet[:, :, None] * 0.3
    )
    texture = np.random.default_rng(402).normal(0, 1.3, (n, n))
    base += (shade - contours + texture)[:, :, None]
    water = e < L.WATER
    base[water] = np.array([95, 130, 126]) + np.minimum(
        e[water, None] - L.WATER, 0
    ) * np.array([3.0, 2.5, 1.8])
    img = Image.fromarray(base.clip(0, 255).astype("u1"))
    d = ImageDraw.Draw(img)
    unit = n / L.SIZE

    def px(x, z):
        return ((x + L.HALF) * unit, (L.HALF - z) * unit)

    def footprint(o, ax, bz, fill):
        ang = math.radians(o["yaw"])
        s, c = math.sin(ang), math.cos(ang)
        ax *= o["scale"] * 0.5
        bz *= o["scale"] * 0.5
        poly = [
            px(o["x"] + c * a + s * b, o["z"] - s * a + c * b)
            for a, b in [(-ax, -bz), (ax, -bz), (ax, bz), (-ax, bz)]
        ]
        d.polygon(poly, fill=fill, outline=(91, 83, 60) if ax > 2 else None)

    for o in sorted(items, key=lambda q: q["z"], reverse=True):
        k = o["kind"]
        cx, cz = px(o["x"], o["z"])
        rr = (3.4 if k == "pine" else 4.3) * unit * o["scale"]
        if k in ("pine", "broadleaf", "orchard_tree", "brush"):
            if k == "orchard_tree":
                rr *= 0.65
            if k == "brush":
                rr *= 0.38
            d.ellipse(
                (
                    cx - rr + 0.8 * unit,
                    cz - rr + 1.9 * unit,
                    cx + rr + 0.8 * unit,
                    cz + rr + 1.9 * unit,
                ),
                fill=(80, 86, 61),
            )
            d.ellipse(
                (cx - rr, cz - rr, cx + rr, cz + rr),
                fill=(81, 100, 70) if k == "pine" else (92, 110, 75),
            )
            d.arc((cx - rr, cz - rr, cx + rr, cz + rr), 175, 285, fill=(120, 133, 85))
        elif k.startswith("cottage"):
            footprint(o, 6.3, 10.8, (185, 164, 123))
        elif k in ["shed", "barn", "windmill", "well", "fence", "haystack"]:
            a, b, col = {
                "shed": (4.8, 6.5, (148, 131, 103)),
                "barn": (8, 13.5, (153, 139, 111)),
                "windmill": (7, 7, (179, 160, 121)),
                "well": (2, 2, (183, 170, 129)),
                "fence": (7.8, 0.5, (114, 105, 81)),
                "haystack": (3.9, 4, (176, 156, 101)),
            }[k]
            footprint(o, a, b, col)
    for _, cx, cz, m, span in L.BRIDGES:
        a, b = px(cx - m / 2, cz + span / 2)
        c, e = px(cx + m / 2, cz - span / 2)
        d.rectangle(
            (a, b, c, e),
            fill=(188, 164, 115),
            outline=(95, 82, 60),
            width=max(1, round(unit)),
        )
        for xx in np.arange(cx - m / 2 + 3, cx + m / 2, 5):
            a, b = px(xx, cz + span * 0.42)
            c, e = px(xx, cz - span * 0.42)
            d.line((a, b, c, e), fill=(152, 136, 98), width=1)
    return img


POINTS = [
    ("村庄主街", "木屋沿路，院后留菜圃。", -216, -63),
    ("村口木桥", "主路在这里跨过河湾。", 150, -30),
    ("北侧农桥", "经河漫滩绕回村北。", 142, 337),
    ("东岸磨坊", "石基木磨坊与谷仓相邻。", 330, -278),
    ("南侧池塘", "农庄下方的低洼积水地。", -103, -342),
    ("村北果园", "窄路连接果园和北侧农道。", -110, 84),
]


def overview(img, path):
    regular = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
    bold = regular.with_name("NotoSansCJK-Bold.ttc")
    if not regular.exists() or not bold.exists():
        raise ValueError(
            "CJK Noto fonts required only for the optional labeled overview"
        )

    def font(n, b=False):
        return ImageFont.truetype(str(bold if b else regular), n, index=2)

    sheet = Image.new("RGB", (1580, 1395), "#efeadc")
    d = ImageDraw.Draw(sheet)
    ink = "#303b32"
    mut = "#606958"
    line = "#b7b59d"
    accent = "#865639"
    x0, y0, side = 69, 225, 1036
    side_x = 1156
    d.text((66, 38), "HATCH     /     额外战役地图库", font=font(22, True), fill=mut)
    d.text((63, 75), "巴巴罗萨行动", font=font(73, True), fill=ink)
    d.text((69, 174), "西波列西亚乡野   /   1941 · 初夏", font=font(27), fill=accent)
    d.text((1498, 104), "地图  01", font=font(27, True), anchor="ra", fill=mut)
    d.text((1498, 148), "1.4 × 1.4 公里", font=font(24), anchor="ra", fill=mut)
    d.line((68, 210, 1509, 210), fill=line, width=2)
    sheet.paste(img.resize((side, side), Image.Resampling.LANCZOS), (x0, y0))
    d.rectangle((x0, y0, x0 + side, y0 + side), outline=ink, width=2)
    for i, (name, desc, x, z) in enumerate(POINTS, 1):
        a = x0 + (x + 700) / 1400 * side
        b = y0 + (700 - z) / 1400 * side
        d.ellipse(
            (a - 17, b - 17, a + 17, b + 17), fill="#34463c", outline="#fff3d4", width=3
        )
        d.text((a, b - 1), str(i), font=font(18, True), anchor="mm", fill="#fff6dc")
    # North and scale are outside the map's coordinate field.
    d.text((x0, y0 + side + 13), "N ↑   北", font=font(22, True), fill=ink)
    length = side * 200 / 1400
    ax = x0 + side - length
    ay = y0 + side + 31
    d.line((ax, ay, ax + length, ay), fill=ink, width=5)
    d.line((ax, ay - 7, ax, ay + 6), fill=ink, width=3)
    d.line((ax + length, ay - 7, ax + length, ay + 6), fill=ink, width=3)
    d.text((ax - 12, ay), "200 米", font=font(19), anchor="rm", fill=mut)
    d.text((side_x, 234), "地图索引", font=font(40, True), fill=ink)
    for i, (name, desc, x, z) in enumerate(POINTS, 1):
        top = 325 + (i - 1) * 114
        d.text((side_x, top + 3), f"{i:02}", font=font(22, True), fill=accent)
        d.text((side_x + 50, top - 5), name, font=font(29, True), fill=ink)
        d.text((side_x, top + 41), desc, font=font(22), fill=mut)
        d.line((side_x, top + 83, 1504, top + 83), fill=line)
    d.text((side_x, 1049), "地表", font=font(27, True), fill=ink)
    for i, (label, c) in enumerate(
        [
            ("草甸", "#787b53"),
            ("耕地", "#a3995c"),
            ("林地", "#53664a"),
            ("水域", "#5d807d"),
        ]
    ):
        xx = side_x + (i % 2) * 162
        yy = 1117 + (i // 2) * 54
        d.rectangle((xx, yy, xx + 24, yy + 21), fill=c)
        d.text((xx + 38, yy - 9), label, font=font(23), fill=ink)
    d.line((68, 1333, 1509, 1333), fill=line, width=2)
    d.text((68, 1343), "历史地貌参考 · 虚构村落与路线", font=font(21), fill=mut)
    d.text(
        (1507, 1343), "以场景地形和物件坐标绘制", font=font(21), anchor="ra", fill=mut
    )
    sheet.save(path, optimize=True)
