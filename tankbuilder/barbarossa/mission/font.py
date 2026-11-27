import base64, struct
from pathlib import Path
from ...campaign_ugui import PTR, text_value, require
from ...enemy_assets import refs
from ...serialization import assert_roundtrip, encode_complete
from ...unity_assets import pp
from .codec import cname


def bind(link, stock, labels):
    """Give only the new Chinese text its own dynamic font, private atlas and private material."""
    src = stock.objects[161]
    v = assert_roundtrip(src)
    ma = v["m_DefaultMaterial"]["m_PathID"]
    tx = v["m_Texture"]["m_PathID"]
    f, m, t = link.alloc(), link.alloc(), link.alloc()
    mapper = link.mapper(stock, "sharedassets0.assets", {161: f, ma: m, tx: t})
    for old, new in [(ma, m), (tx, t), (161, f)]:
        o = stock.objects[old]
        tr = refs(assert_roundtrip(o), mapper)
        if old == 161:
            tr.update(
                m_Name="Hatch Campaign Sans",
                m_FontNames=["Hatch Campaign Sans", "Noto Sans CJK SC", "sans-serif"],
                m_FallbackFonts=[pp(161, link.external("sharedassets0.assets"))],
                m_FontData=base64.b64decode(
                    Path(__file__).with_name("campaign-sans.ttf.b64").read_bytes()
                ),
            )
        else:
            tr["m_Name"] = "Hatch Campaign Font " + (
                "Material" if old == ma else "Atlas"
            )
        link.add(o, new, encode_complete(o, tr))
    changed = []
    for o in link.sf.objects.values():
        if o.type.name != "MonoBehaviour" or cname(o, link.names) != "Text":
            continue
        raw = o.data or o.get_raw_data()
        if text_value(raw) in labels:
            b = bytearray(raw)
            PTR.pack_into(b, 88, 0, f)
            o.set_raw_data(bytes(b))
            changed.append(o.path_id)
    require(changed, "Native campaign text missing")
    return f


def covers(data, label):
    # Read the embedded BMP cmap, so verification also works with the stock builder dependencies.
    data = bytes(data)
    nt = struct.unpack_from(">H", data, 4)[0]
    tables = {
        data[12 + 16 * i : 16 + 16 * i]: struct.unpack_from(">I", data, 20 + 16 * i)[0]
        for i in range(nt)
    }
    start = tables[b"cmap"]
    n = struct.unpack_from(">H", data, start + 2)[0]
    u16 = lambda p: struct.unpack_from(">H", data, p)[0]
    for i in range(n):
        at = start + 4 + i * 8
        plat, enc, off = struct.unpack_from(">HHI", data, at)
        p = start + off
        if plat not in (0, 3) or u16(p) != 4:
            continue
        ns = u16(p + 6) // 2
        e = p + 14
        s = e + 2 * ns + 2
        d = s + 2 * ns
        r = d + 2 * ns

        def glyph(v):
            for j in range(ns):
                if u16(s + 2 * j) <= v <= u16(e + 2 * j):
                    shift = u16(d + 2 * j)
                    roff = u16(r + 2 * j)
                    if roff == 0:
                        return (v + shift) & 65535
                    g = u16(r + 2 * j + roff + 2 * (v - u16(s + 2 * j)))
                    return ((g + shift) & 65535) if g else 0
            return 0

        return all(glyph(ord(ch)) for ch in label if not ch.isspace())
    return False
