from PIL import Image
from ..cartography import cartography
from .. import layout
from ...campaign_ugui import PTR, require
from ...serialization import assert_roundtrip, encode_complete
from ...unity_assets import pp


def install(link, sf_stock, h, props):
    # The game draws live unit symbols as children over this Image. Retain its existing rect, button and UVs.
    img = link.sf.objects[155293]
    raw = bytearray(img.get_raw_data())
    f, p = PTR.unpack_from(raw, 88)
    require(
        link.sf.externals[f - 1].path == "sharedassets1.assets" and p == 265,
        "Unexpected minimap sprite",
    )
    sprite = sf_stock.objects[p]
    sp = assert_roundtrip(sprite)
    texture = sf_stock.objects[sp["m_RD"]["texture"]["m_PathID"]]
    ts = assert_roundtrip(texture)
    resolution = (ts["m_Width"], ts["m_Height"])
    require(resolution == (256, 256), "Stock tactical-map geometry changed")
    im = (
        cartography(h, layout.splat(props), props, 1040)
        .resize(resolution, Image.Resampling.LANCZOS)
        .convert("RGBA")
    )
    buf = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
    ti, si = link.alloc(), link.alloc()
    ts.update(
        m_Name="Minimap_Polesie",
        m_TextureFormat=4,
        m_CompleteImageSize=len(buf),
        m_MipCount=1,
        m_MipsStripped=0,
        m_IsPreProcessed=False,
        m_StreamingMipmaps=False,
        m_PlatformBlob=b"",
        m_StreamData={"offset": 0, "size": 0, "path": ""},
    )
    ts["image data"] = buf
    link.add(texture, ti, encode_complete(texture, ts))
    sp["m_Name"] = "Minimap_Barbarossa_01"
    sp["m_RD"]["texture"] = pp(ti)
    link.add(sprite, si, encode_complete(sprite, sp))
    PTR.pack_into(raw, 88, 0, si)
    img.set_raw_data(bytes(raw))
    return {"image": 155293, "sprite": si, "texture": ti}
