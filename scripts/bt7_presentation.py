"""Produce the BT-7 model sheet and six-second rig playback from the rendered GLB frames."""

import argparse
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

PAPER = "#efece2"
INK = "#28352b"
OLIVE = "#53634e"
QUIET = "#647066"
RED = "#a83e2e"
LINE = "#bcc5ae"


def font(n, b=False):
    return ImageFont.truetype(
        "/usr/share/fonts/opentype/noto/NotoSansCJK-"
        + ("Bold" if b else "Regular")
        + ".ttc",
        n,
        index=2,
    )


def txt(d, pos, s, n, color=INK, b=False):
    d.text(pos, s, font=font(n, b), fill=color, anchor="lt")


def star(d, x, y, r):
    d.polygon(
        [
            (
                x + math.sin(i * math.pi / 5) * r * (1 if i % 2 == 0 else 0.382),
                y - math.cos(i * math.pi / 5) * r * (1 if i % 2 == 0 else 0.382),
            )
            for i in range(10)
        ],
        fill=RED,
    )


def sheet(src, out):
    bg = Image.new("RGB", (1440, 882), PAPER)
    d = ImageDraw.Draw(bg)
    d.rectangle((0, 0, 1440, 142), fill=INK)
    d.rectangle((0, 0, 10, 142), fill=RED)
    star(d, 55, 47, 15)
    txt(d, (83, 34), "苏联装甲车辆  /  1937", 19, "#dce7cd")
    txt(d, (37, 72), "BT-7  快速坦克", 47, "#faf9ed", True)
    txt(d, (900, 42), "LUNA 17   /   车辆档案", 22, "#eff2e6", True)
    txt(d, (900, 83), "锥形炮塔型   ·   模型实渲", 20, "#bdcbb4")

    def panel(name, bounds, label):
        x, y, w, h = bounds
        im = ImageOps.fit(
            Image.open(src / (name + ".png")).convert("RGB"),
            (w, h),
            centering=(0.5, 0.55),
            method=Image.Resampling.LANCZOS,
        )
        bg.paste(im, (x, y))
        size = d.textbbox((0, 0), label, font=font(17))[2]
        d.rectangle((x + 12, y + h - 40, x + 34 + size, y + h - 11), fill=INK)
        txt(d, (x + 23, y + h - 35), label, 17, "#f4f3e8")

    panel("Front", (36, 164, 855, 521), "01  /  前侧")
    panel("Running-gear", (908, 164, 495, 252), "02  /  红星与行走机构")
    panel("Rear", (908, 433, 495, 252), "03  /  后侧")
    d.line((37, 710, 1402, 710), fill=LINE, width=2)
    stats = [
        ("乘员", "3 人"),
        ("战斗全重", "13.8 吨"),
        ("发动机", "450 马力"),
        ("履带公路极速", "52 公里/小时"),
    ]
    for i, (label, val) in enumerate(stats):
        x = 40 + i * 350
        txt(d, (x, 737), label, 21, QUIET)
        txt(d, (x, 775), val, 37, INK, True)
        if i:
            d.line((x - 19, 741, x - 19, 823), fill=LINE, width=2)
    txt(d, (40, 845), "模型改编自 Sankocho_DePoligonos  /  CC BY 4.0", 15, QUIET)
    bg.save(out / "BT7-1937-Preview.png", optimize=True)


def movie(src, out):
    frames = sorted((src / "frames").glob("*.png"))
    if len(frames) != 108:
        raise ValueError("Expected all 108 model playback frames")
    names = [
        ("前进", "两侧履带同向"),
        ("倒车", "两侧履带反向回转"),
        ("原地转向", "左右履带相向转动"),
    ]
    bars = []
    for i, (head, sub) in enumerate(names):
        bar = Image.new("RGB", (768, 68), INK)
        d = ImageDraw.Draw(bar)
        d.rectangle((0, 0, 7, 68), fill=RED)
        txt(d, (17, 12), "BT-7", 24, "#f6f5eb", True)
        txt(d, (110, 12), head, 24, "#f6f5eb", True)
        txt(d, (18, 45), "1937   /   三维绑定预览", 13, "#c0ceba")
        txt(d, (465, 20), sub, 19, "#e2ead7")
        txt(d, (692, 24), "0" + str(i + 1) + " / 03", 12, "#c0ceba")
        bars.append(bar)
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            "768x500",
            "-r",
            "18",
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "3",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(out / "BT7-Rig-Preview.mp4"),
        ],
        stdin=subprocess.PIPE,
    )
    for i, p in enumerate(frames):
        f = Image.new("RGB", (768, 500))
        f.paste(Image.open(p).convert("RGB"))
        f.paste(bars[i // 36], (0, 432))
        ImageDraw.Draw(f).rectangle(
            (0, 430, round(768 * (i + 1) / 108), 432), fill="#a3b386"
        )
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError("Video encoding failed")


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    c.add_argument("--render", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    a = c.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sheet(a.render, a.out)
    movie(a.render, a.out)
