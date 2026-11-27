"""Preview the actual Ausf.C mesh and articulated wheels in a game-independent inspection reel."""

import argparse
from pathlib import Path

from bt7_presentation import movie, txt
from PIL import Image, ImageDraw, ImageOps


def panel(im, d, src, x, y, w, h, label):
    shot = ImageOps.fit(
        Image.open(src).convert("RGB"),
        (w, h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.52),
    )
    im.paste(shot, (x, y))
    d.rectangle(
        (x + 13, y + h - 35, x + 42 + len(label) * 17, y + h - 10), fill="#2d3435"
    )
    txt(d, (x + 22, y + h - 30), label, 15, "#f6f1e8")


def sheet(src, out):
    bg = Image.new("RGB", (1440, 888), "#eeece6")
    d = ImageDraw.Draw(bg)
    d.rectangle((0, 0, 1440, 140), fill="#303639")
    d.rectangle((0, 0, 9, 140), fill="#bcac84")
    txt(d, (40, 25), "德国装甲车辆    /    1938–39", 18, "#ddd6c5")
    txt(d, (38, 63), "四号 C 型中型坦克", 48, "#f6f3ec", True)
    txt(d, (935, 36), "PANZER IV AUSF. C", 26, "#f0e8d7", True)
    txt(d, (935, 86), "LUNA 17      /      车辆档案", 17, "#c9c2ad")
    panel(bg, d, src / "Front.png", 34, 162, 840, 523, "01   前侧")
    panel(bg, d, src / "Running-gear.png", 892, 162, 512, 251, "02   侧面与轮系")
    panel(bg, d, src / "Rear.png", 892, 431, 512, 254, "03   后侧")
    d.line((34, 712, 1405, 712), fill="#b6b5a6", width=2)
    for i, (a, b) in enumerate(
        [
            ("乘员", "5 人"),
            ("战斗全重", "18.5 吨"),
            ("发动机", "300 马力"),
            ("公路极速", "42 公里/小时"),
        ]
    ):
        x = 40 + i * 350
        txt(d, (x, 737), a, 20, "#646b65")
        txt(d, (x, 779), b, 35, "#303639", True)
    txt(
        d,
        (40, 849),
        "原始模型：patoburro（CC BY 4.0）     ·     最终游戏模型离线渲染",
        15,
        "#62675f",
    )
    bg.save(out / "PanzerIV-C-Preview.png", optimize=True)


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    c.add_argument("--render", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    a = c.parse_args()
    a.out.mkdir(exist_ok=True, parents=True)
    sheet(a.render, a.out)
    movie(
        a.render,
        a.out,
        "四号 C 型",
        "1938–39   /   三维绑定预览",
        "PanzerIV-C-Rig.mp4",
        175,
    )
