"""Fixed mission lettering drawn by the game's native UGUI RawImage, independent of OS fonts."""

import base64
import io
import math
import struct
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ...campaign_ugui import PTR, require, text_value
from ...serialization import assert_roundtrip, encode_complete, parse_complete
from ...unity_assets import pp
from .codec import cname, kids, part, update
from .font import covers

SCALE = 2


@lru_cache(maxsize=32)
def pixels(label, size):
    font_data = base64.b64decode(
        Path(__file__).with_name("campaign-sans.ttf.b64").read_bytes()
    )
    require(covers(font_data, label), "Missing glyph in fixed caption: " + label)
    font = ImageFont.truetype(io.BytesIO(font_data), size=size * SCALE)
    lines = label.splitlines()
    bounds = [font.getbbox(s, anchor="ls") for s in lines]
    pad = 3
    width = max(r - l for l, t, r, b in bounds) + 2 * pad
    leading = round(size * SCALE * 1.18)
    top = min(t + i * leading for i, (_, t, _, _) in enumerate(bounds))
    bottom = max(b + i * leading for i, (_, _, _, b) in enumerate(bounds))
    im = Image.new("RGBA", (width, bottom - top + 2 * pad))
    draw = ImageDraw.Draw(im)
    for i, (s, (left, _, right, _)) in enumerate(zip(lines, bounds)):
        draw.text(
            ((width - right - left) // 2, pad - top + i * leading),
            s,
            font=font,
            fill="white",
            stroke_width=1,
            stroke_fill=(48, 44, 40, 245),
            anchor="ls",
        )
    return im


def install(link, raw_donor, texture_donor, labels):
    sf = link.sf
    textures = {}
    found = []
    for text in list(sf.objects.values()):
        if text.type.name != "MonoBehaviour" or cname(text, link.names) != "Text":
            continue
        raw = bytearray(text.data or text.get_raw_data())
        label = text_value(raw)
        if label not in labels:
            continue
        parent = PTR.unpack_from(raw)[1]
        size = struct.unpack_from("<i", raw, 100)[0]
        align = struct.unpack_from("<i", raw, 120)[0]
        require(align in (3, 4), "Unreviewed fixed caption alignment")
        x = 0.0 if align == 3 else 0.5
        im = pixels(label, size)
        if (label, size) not in textures:
            buf = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
            tex = assert_roundtrip(texture_donor)
            tex.update(
                m_Name="Hatch Type / " + label.replace("\n", " / "),
                m_TextureFormat=4,
                m_Width=im.width,
                m_Height=im.height,
                m_CompleteImageSize=len(buf),
                m_MipCount=1,
                m_MipsStripped=0,
                m_IsPreProcessed=False,
                m_StreamingMipmaps=False,
                m_IsReadable=False,
                m_ColorSpace=1,
                m_PlatformBlob=b"",
                m_StreamData={"offset": 0, "size": 0, "path": ""},
            )
            tex["m_TextureSettings"].update(m_FilterMode=1, m_WrapU=1, m_WrapV=1)
            tex["image data"] = buf
            texture = link.alloc()
            link.add(texture_donor, texture, encode_complete(texture_donor, tex))
            textures[label, size] = texture
        go, rect, renderer, image = [link.alloc() for _ in range(4)]
        src = sf.objects[parent]
        gv = parse_complete(src)
        gv.update(
            m_Name="Fixed lettering",
            m_IsActive=True,
            m_Tag=0,
            m_Component=[{"component": pp(p)} for p in (rect, renderer, image)],
        )
        link.add(src, go, encode_complete(src, gv))
        rt = sf.objects[part(sf, parent, "RectTransform")]
        rv = assert_roundtrip(rt)
        pt = rt.path_id
        update(sf, pt, m_Children=[*rv["m_Children"], pp(rect)])
        rv.update(
            m_GameObject=pp(go),
            m_Father=pp(pt),
            m_Children=[],
            m_LocalPosition=dict(x=0.0, y=0.0, z=0.0),
            m_LocalRotation=dict(x=0.0, y=0.0, z=0.0, w=1.0),
            m_LocalScale=dict(x=1.0, y=1.0, z=1.0),
            m_AnchorMin=dict(x=x, y=0.5),
            m_AnchorMax=dict(x=x, y=0.5),
            m_Pivot=dict(x=x, y=0.5),
            m_AnchoredPosition=dict(x=0.0, y=0.0),
            m_SizeDelta=dict(x=im.width / SCALE, y=im.height / SCALE),
        )
        link.add(rt, rect, encode_complete(rt, rv))
        cr = sf.objects[part(sf, parent, "CanvasRenderer")]
        cv = assert_roundtrip(cr)
        cv["m_GameObject"] = pp(go)
        link.add(cr, renderer, encode_complete(cr, cv))
        rb = bytearray(raw_donor.get_raw_data())
        require(
            len(rb) == 116 and cname(raw_donor, link.names) == "RawImage",
            "Unrecognized UGUI RawImage",
        )
        f, p = PTR.unpack_from(rb, 16)
        ext = raw_donor.assets_file.externals[f - 1]
        PTR.pack_into(rb, 16, link.external(ext.path, ext), p)
        PTR.pack_into(rb, 0, 0, go)
        PTR.pack_into(rb, 32, 0, 0)
        rb[12], rb[60] = 1, 0
        rb[44:60] = raw[44:60]
        PTR.pack_into(rb, 88, 0, textures[label, size])
        struct.pack_into("<4f", rb, 100, 0.0, 0.0, 1.0, 1.0)
        link.add(raw_donor, image, bytes(rb))
        # Retain the original text value for navigation / localization metadata.
        raw[12] = 0
        text.set_raw_data(bytes(raw))
        found.append(label)
    require(set(found) == set(labels), "Missing fixed caption")
    return found


def check(sf, names, text):
    raw = text.get_raw_data()
    label = text_value(raw)
    owner = PTR.unpack_from(raw)[1]
    (g,) = [
        g
        for g in kids(sf, owner)
        if parse_complete(sf.objects[g])["m_Name"] == "Fixed lettering"
    ]
    go = parse_complete(sf.objects[g])
    (image,) = [
        o
        for c in go["m_Component"]
        if (o := sf.objects[c["component"]["m_PathID"]]).type.name == "MonoBehaviour"
        and cname(o, names) == "RawImage"
    ]
    r = image.get_raw_data()
    f, p = PTR.unpack_from(r, 88)
    require(
        go["m_IsActive"]
        and r[12] == 1
        and r[60] == 0
        and not raw[12]
        and not f
        and r[44:60] == raw[44:60]
        and struct.unpack_from("<4f", r, 100) == (0.0, 0.0, 1.0, 1.0),
        "Inactive, conflicting or obstructive caption: " + label,
    )
    part(sf, g, "CanvasRenderer")
    tex = parse_complete(sf.objects[p])
    w, h = tex["m_Width"], tex["m_Height"]
    require(
        tex["m_TextureFormat"] == 4
        and tex["m_StreamData"]["size"] == 0
        and len(tex["image data"]) == w * h * 4,
        "Caption is not an embedded RGBA texture",
    )
    im = Image.frombytes("RGBA", (w, h), bytes(tex["image data"])).transpose(
        Image.Transpose.FLIP_TOP_BOTTOM
    )
    size = struct.unpack_from("<i", raw, 100)[0]
    require(
        im.tobytes() == pixels(label, size).tobytes()
        and im.getchannel("A").getextrema() == (0, 255),
        "Wrong, upside-down or empty caption artwork: " + label,
    )
    rt = parse_complete(sf.objects[part(sf, g, "RectTransform")])
    require(
        math.isclose(rt["m_SizeDelta"]["x"] * SCALE, w)
        and math.isclose(rt["m_SizeDelta"]["y"] * SCALE, h)
        and rt["m_Father"] == pp(part(sf, owner, "RectTransform")),
        "Incorrect caption rectangle",
    )
    return im
