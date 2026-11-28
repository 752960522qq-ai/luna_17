"""Present the actual game vehicle renders as a Chinese contact sheet and motion reel."""
import argparse
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

FONTS = Path('/usr/share/fonts')
def font(size,which='sans'):
    m = {
        'sans': 'opentype/noto/NotoSansCJK-Regular.ttc',
        'bold': 'opentype/noto/NotoSansCJK-Bold.ttc',
        'serif': 'opentype/noto/NotoSerifCJK-Bold.ttc',
        'mono': 'truetype/dejavu/DejaVuSansMono.ttf',
        'latin': 'truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
    }
    return ImageFont.truetype(str(FONTS / m[which]), size, index=2 if which in ('sans', 'bold', 'serif') else 0)
INK = '#252d2e'
SUB = '#526061'
PAPER = '#f0eee6'
GOLD = '#ad8152'
RULE = '#c3c4b9'
DRK = '#26302f'
def text(d,pos,s,sz=24,fill=INK,f='sans',anchor='lt'):
    d.text(pos, s, font=font(sz, f), fill=fill, anchor=anchor)
def pic(path):
    im = Image.open(path).convert('RGB')
    return Image.blend(im, im.filter(ImageFilter.MedianFilter(3)), 0.5)
def tobox(im,photo,box):
    x, y, w, h = box
    im.paste(ImageOps.fit(photo, (w, h), method=Image.Resampling.LANCZOS), (x, y))
def sheet(render,out,t28=False):
    im = Image.new('RGB', (1680, 1080), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1680, 15), fill=DRK)
    text(d, (56, 40), 'LUNA 17   /   VEHICLE STUDIES', 19, SUB, 'mono')
    text(d, (1624, 40), ('SOVIET ARMOUR  /  28' if t28 else 'FAHRZEUG  ·  03/F'), 19, SUB, 'mono', 'rt')
    text(d, (50, 77), ('T-28' if t28 else '三号 F 型'), 78, INK, 'serif')
    text(d, (464, 118), ('三炮塔中型坦克  /  1934' if t28 else 'PANZERKAMPFWAGEN  III  AUSF. F'), 39, INK, 'bold' if t28 else 'latin')
    d.line((56, 190, 1624, 190), fill=INK, width=2)
    text(d, (56, 207), ('苏联绿    /    圆柱形主炮塔 · KT-28 短身炮 · 双前机枪塔' if t28 else '德国中型坦克    /    外置炮盾 · 短身 50 毫米炮'), 25, SUB)
    text(d, (1624, 211), 'MODEL PREVIEW   /   01', 20, SUB, 'mono', 'rt')
    # Main plate and two actual alternate camera views, all at the same rest pose.
    x, y, w, h = (56, 267, 1020, 578)
    tobox(im, pic(render / 'Front.png'), (x, y, w, h))
    d.rectangle((x + 15, y + 15, x + 68, y + 44), fill=DRK)
    text(d, (x + 27, y + 18), '01', 18, '#f1efe4', 'mono')
    for name,yy,hh,nn,lab in [('Running-gear.png',267,250,'02','侧面 · 行走机构'),('Turrets.png' if t28 else 'Rear.png',567,250,'03','俯视 · 三座炮塔' if t28 else '后视 · 发动机舱')]:
        source = pic(render / name)
        if nn=='02':
            source = source.crop((20, 105, 1135, 650))
        else:
            source = source.crop((15, 68, 1140, 645))
        tobox(im, source, (1100, yy, 524, hh))
        d.rectangle((1111, yy + 10, 1156, yy + 35), fill=DRK)
        text(d, (1120, yy + 13), nn, 15, '#f1efe4', 'mono')
        text(d, (1100, yy + hh + 8), lab, 20, SUB)
    text(d, (56, 859), '01   /   左前视图', 18, SUB)
    d.line((56, 909, 1624, 909), fill=RULE, width=2)
    data=[('行走机构','12 对负重轮'),('战斗全重','28 吨'),('最高公路速度','37 km/h'),('车体长 × 车宽 × 车高','7.44 × 2.87 × 2.82 m')] if t28 else [('行走机构','6 对负重轮'),('涂装','德国灰  /  RAL 7021'),('最高公路速度','40 km/h'),('车体长 × 车宽 × 车高','5.38 × 2.91 × 2.44 m')]
    for i,(a,b) in enumerate(data):
        x = [56, 405, 803, 1150][i]
        text(d, (x, 931), a, 18, SUB)
        text(d, (x, 963), b, 31, INK, 'bold')
        if i:
            d.line((x - 23, 933, x - 23, 1004), fill=RULE, width=1)
    d.line((56, 1023, 1624, 1023), fill=RULE, width=1)
    text(d, (56, 1041), ('SOURCE MODEL   /   MAMONT NIKITA    ·    CC BY 4.0' if t28 else 'SOURCE MODEL   /   TIGERACE1945'), 16, SUB, 'mono')
    text(d, (1624, 1037), '游戏模型渲染   ·   玩家车辆与 AI 共用外观', 18, SUB, 'sans', 'rt')
    im.save(out / ('T28-Preview.jpg' if t28 else 'PanzerIII-F-Preview.jpg'), quality=95, subsampling=0, optimize=True)

def reel(render,out,t28=False):
    frames = sorted((render / 'frames').glob('*.png'))
    assert len(frames) == 108, len(frames)
    W, H = (1200, 664)
    dest = out / ('T28-Motion.mp4' if t28 else 'PanzerIII-F-Motion.mp4')
    cmd = [
        'ffmpeg',
        '-y',
        '-loglevel',
        'error',
        '-f',
        'rawvideo',
        '-pixel_format',
        'rgb24',
        '-video_size',
        f'{W}x{H}',
        '-framerate',
        '18',
        '-i',
        '-',
        '-vf',
        'hqdn3d=2.2:1.4:2.4:1.5',
        '-c:v',
        'libx264',
        '-threads',
        '3',
        '-crf',
        '17',
        '-preset',
        'fast',
        '-pix_fmt',
        'yuv420p',
        '-movflags',
        '+faststart',
        str(dest)
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    phases = ['两侧履带同向前进', '两侧履带同步倒车', '左右履带反向转动']
    base = Image.new('RGB', (W, H), PAPER)
    d = ImageDraw.Draw(base)
    d.rectangle((0, 0, W, 5), fill=DRK)
    text(d, (27, 18), ('T-28' if t28 else '三号 F 型'), 34, INK, 'serif')
    text(d, (232, 30), ('1934  /  苏联中型坦克' if t28 else 'PANZER III AUSF. F'), 21, SUB, 'bold' if t28 else 'latin')
    text(d, (1172, 27), '行走机构与炮塔  /  动作预览', 20, SUB, 'sans', 'rt')
    for j,f in enumerate(frames):
        im = base.copy()
        d = ImageDraw.Draw(im)
        src = Image.open(f).convert('RGB')
        ix = min(2, j // 36)
        t = j / 18
        full = src.resize((882, 496), Image.Resampling.LANCZOS)
        im.paste(full, (27, 83))
        # Zoom from the same frame, never a synthetic substitute for the running gear.
        cr = src.crop((166,130,402,273) if t28 and ix==1 else (255,237,496,383))
        tobox(im, cr, (929, 83, 244, 160))
        text(d, (929, 255), ('主炮塔与前机枪塔' if t28 and ix==1 else '负重轮与履带局部'), 17, SUB)
        d.line((929, 301, 1173, 301), fill=RULE, width=2)
        text(d, (929, 327), f'0{ix + 1}  /  03', 22, GOLD, 'mono')
        text(d, (929, 375), phases[ix], 22, INK, 'bold')
        for ii,label in enumerate(['前进','倒车','差速转向']):
            yy = 431 + ii * 34
            d.ellipse((931, yy + 5, 940, yy + 14), fill=GOLD if ix == ii else RULE)
            text(d, (953, yy), label, 16, INK if ix == ii else SUB)
        d.line((27, 600, 1173, 600), fill=RULE, width=2)
        d.line((27, 600, 27 + int(1146 * (j + 1) / 108), 600), fill=GOLD, width=3)
        text(d, (27, 617), ('独立履带  /  24 个负重轮  /  主炮塔与前机枪塔各绕自身轴心转动' if t28 else '独立履带  /  扭杆悬挂  /  炮塔回转与炮管俯仰'), 19, SUB)
        text(d, (1172, 621), f'{t:04.1f}  /  06.0 s', 17, SUB, 'mono', 'rt')
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError('Could not encode the rig reel')

if __name__=='__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('render', type=Path)
    cli.add_argument('out', type=Path)
    cli.add_argument('--motion', action='store_true')
    cli.add_argument('--thumbnail', type=Path, help='Optional thumbnail.png path in the game project')
    cli.add_argument('--t28',action='store_true')
    a = cli.parse_args()
    a.out.mkdir(exist_ok=True, parents=True)
    sheet(a.render, a.out, a.t28)
    if a.thumbnail:
        thumb = Image.open(a.render / 'Front.png').convert('RGB')
        thumb.thumbnail((512, 320), Image.Resampling.LANCZOS)
        thumb.save(a.thumbnail, optimize=True)
    if a.motion:
        reel(a.render, a.out, a.t28)
