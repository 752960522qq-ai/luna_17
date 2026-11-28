"""Show before and after from the same orthographic camera, at the same scale."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
from panzer3f_preview import DRK, GOLD, INK, PAPER, RULE, SUB, pic, text


def compare(old, new, out):
    imgs = [pic(path) for path in (old, new)]
    if imgs[0].size != imgs[1].size or imgs[0].size != (1152, 720):
        raise ValueError('Expected matching full side renders, 1152 x 720.')
    frame = Image.new('RGB', (1480, 636), PAPER)
    d = ImageDraw.Draw(frame)
    d.rectangle((0, 0, 1480, 10), fill=DRK)
    text(d, (46, 31), 'LUNA 17  /  VEHICLE STUDIES', 16, SUB, 'mono')
    text(d, (1435, 31), 'PZ.KPFW. III AUSF. F', 16, SUB, 'mono', 'rt')
    text(d, (45, 66), '三号 F 型  /  炮管比例修正', 54, INK, 'serif')
    d.line((46, 147, 1434, 147), fill=INK, width=2)
    for j, (im, label, detail) in enumerate(zip(imgs, ('修改前', '修改后'), ('原模型', '收细后的游戏模型'))):
        x = 46 + j * 706
        text(d, (x, 175), label, 26, INK, 'bold')
        text(d, (x+122, 183), detail, 18, SUB)
        rect = im.crop((60, 98, 690, 383)).resize((681, 308), Image.Resampling.LANCZOS)
        frame.paste(rect, (x, 229))
        # The gauge line is outside the object; it never covers the outline of the tube.
        d.line((x, 545, x+681, 545), fill=RULE, width=2)
    text(d, (46, 576), '同一视角、同一比例。只修外形，保留炮管长度、炮口位置与后坐行程。', 24, SUB)
    text(d, (1433, 581), '01  /  01', 17, GOLD, 'mono', 'rt')
    frame.save(out, quality=95, subsampling=0, optimize=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    for k in ('before', 'after', 'out'):
        ap.add_argument(k, type=Path)
    args = ap.parse_args()
    compare(args.before, args.after, args.out)
