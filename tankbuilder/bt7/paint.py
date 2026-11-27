"""Olive paint, rubber, optics and mobile tread textures; no borrowed insignia."""

import io

import numpy as np
from PIL import Image, ImageDraw

RUBBER = (51, 51, 44)


def weather(size, seed, level=1.0):
    w, h = size
    r = np.random.default_rng(seed)
    grain = r.normal(0, 1.7, (h, w))
    for n, amp in [(7, 4.0), (24, 1.9), (68, 1.2)]:
        a = r.integers(20, 231, (n, n), dtype="u1")
        grain += (
            (
                np.asarray(
                    Image.fromarray(a).resize((w, h), Image.Resampling.BICUBIC), float
                )
                - 128
            )
            / 65
            * amp
        )
    return grain[..., None] * level


def finish(arr, seed, amount=1.0, scratches=True):
    h, w, _ = arr.shape
    a = arr + weather((w, h), seed, amount)
    im = Image.fromarray(np.clip(a, 0, 255).astype("u1"))
    if scratches:
        r = np.random.default_rng(seed + 493)
        d = ImageDraw.Draw(im, "RGBA")
        for _ in range(max(5, w * h // 1800)):
            x, y = r.uniform(0, w), r.uniform(0, h)
            d.line(
                (
                    x,
                    y,
                    x + r.uniform(0.3, 2.9) * w / 512,
                    y + r.uniform(-0.7, 1.1) * h / 512,
                ),
                fill=(160, 146, 108, 48),
                width=1,
            )
    return im


def tread():
    w, h = 256, 160
    y, x = np.indices((h, w))
    u = x / w
    v = y / h
    col = np.zeros((h, w, 3)) + [78, 76, 64]
    z = np.minimum(v, 1 - v)
    col += (np.sin(u * 2 * np.pi * 2) * 1.7 + np.cos(v * 2 * np.pi) * 3.3)[:, :, None]
    groove = z < 0.046
    col[groove] = [38, 39, 35]
    # Separate shoes, transverse gripping rib, end pins, regularly worn raised edges.
    rib = np.abs(v - (0.52 + 0.105 * np.abs(u - 0.5) * 2))
    col[rib < 0.10] = [55, 55, 48]
    col[rib < 0.068] = [112, 108, 86]
    col[rib < 0.033] = [136, 129, 103]
    near = (z > 0.065) & (z < 0.10)
    col[near] = [111, 105, 86]
    for cx in (0.09, 0.91):
        f = ((u - cx) / 0.05) ** 2 + ((v - 0.28) / 0.075) ** 2
        col[f < 1.0] = [37, 40, 36]
        col[f < 0.51] = [108, 104, 86]
    return finish(col, 193701, 0.85)


def texture(model, key):
    if key == "tread":
        return tread()
    if key == 39:
        return finish(
            np.broadcast_to([94.0, 105.0, 68.0], (512, 512, 3)), 193739, 0.9
        )  # Original turret atlas has a fictional school shield. Repaint the entire shell.
    if key == "red":
        return finish(np.broadcast_to([174.0, 43.0, 34.0], (128, 128, 3)), 194103, 1.1)
    if key == "rubber":
        return finish(np.broadcast_to(RUBBER, (128, 128, 3)), 194105, 0.65, False)
    if key == "exhaust":
        return finish(np.broadcast_to([85.0, 72.0, 54.0], (128, 128, 3)), 194106, 1.4)
    ma = model.g.materials[key]
    p = ma.pbrMetallicRoughness
    if p.baseColorTexture:
        i = model.g.textures[p.baseColorTexture.index].source
        im = model.g.images[i]
        view = model.g.bufferViews[im.bufferView]
        raw = model.blob[view.byteOffset : view.byteOffset + view.byteLength]
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((512, 512), Image.Resampling.LANCZOS)
        a = np.asarray(im, float)
    else:
        shade = {
            3: (86, 100, 111),
            7: (96, 120, 133),
            24: (81, 82, 74),
            31: (46, 47, 44),
            35: (72, 69, 57),
            40: (81, 81, 74),
        }.get(key, (96, 112, 125))
        a = np.broadcast_to(shade, (128, 128, 3))
    lum = a @ np.array([0.24, 0.56, 0.2])
    mx = a.max(axis=-1)
    mn = a.min(axis=-1)
    tone = np.clip((lum - 111) * 0.43, -24, 14)
    # White paint, snow, markings and flat colour-block details disappear in the new coat.
    tone = np.where(
        (mx - mn < 31) & (lum > 147), np.clip((lum - 190) * 0.05, -4, 2), tone
    )
    base = np.array([96, 108, 70.0])
    if key in (3, 10, 24, 35, 40):
        base = np.array([76, 84, 57.0])
    if key == 31:
        base = np.array([64, 66, 57.0])
    a0 = base + tone[:, :, None]
    is_dark = lum < 65
    if key in (14, 18, 32):
        a0 = np.where(
            is_dark[:, :, None], np.array(RUBBER) + (lum - 39)[:, :, None] * 0.40, a0
        )
    if key in (1, 42):
        a0 = np.where(
            (lum < 77)[:, :, None],
            np.array([44, 48, 37]) + (lum - 44)[:, :, None] * 0.37,
            a0,
        )
    if key in (8, 12, 20, 21, 29, 36):
        a0 = np.where(
            (lum < 62)[:, :, None],
            np.array([48, 57, 50]) + (lum - 40)[:, :, None] * 0.31,
            a0,
        )
    if key == 27:
        a0 = np.where(
            (lum > 160)[:, :, None],
            np.array([189, 184, 145]) + (lum - 190)[:, :, None] * 0.22,
            a0,
        )
        a0 = np.where((lum < 55)[:, :, None], np.array([49, 55, 46]), a0)
    if key == 5:
        a0 = np.where(
            ((a[:, :, 0] > a[:, :, 1] * 1.55) & (a[:, :, 0] > 100))[:, :, None],
            np.array([113, 49, 38]),
            a0,
        )
    return finish(a0, 3520 + key, 0.75 if key in (27, 5, 31) else 1)
