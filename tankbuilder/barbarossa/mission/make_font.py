"""Optional developer utility: derive the redistributable TrueType glyph subset from Noto Sans CJK SC."""

import base64, io, textwrap
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen


def make(ttc, dst):
    src = TTFont(ttc, fontNumber=2)
    cmap = src.getBestCmap()
    g = src.getGlyphSet()
    from . import SIDES

    side_text = "".join(s.label + s.opening + s.objective for s in SIDES)
    chars = sorted(
        set(range(32, 127))
        | set(
            map(
                ord,
                "额外战役巴罗萨行动炼狱之门驾驶与友军一同夺取村口阵地返回标题。·Ⅰ，"
                + side_text.replace("\n", ""),
            )
        )
    )
    mapped = {c: "uni%04X" % c for c in chars}
    pairs = [(".notdef", ".notdef")] + [(mapped[c], cmap[c]) for c in chars]
    fb = FontBuilder(src["head"].unitsPerEm, isTTF=True)
    fb.setupGlyphOrder([n for n, _ in pairs])
    fb.setupCharacterMap(mapped)
    glyphs = {}
    metrics = {}
    for n, k in pairs:
        pen = TTGlyphPen(None)
        g[k].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyphs[n] = pen.glyph()
        metrics[n] = src["hmtx"][k]
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=src["hhea"].ascent, descent=src["hhea"].descent)
    fb.setupNameTable(
        {
            "familyName": "Hatch Campaign Sans",
            "styleName": "Regular",
            "fullName": "Hatch Campaign Sans Regular",
            "psName": "HatchCampaignSans-Regular",
            "uniqueFontIdentifier": "HatchCampaignSans-Regular-1",
            "copyright": src["name"].getDebugName(0) or "Copyright Google and Adobe.",
            "licenseDescription": "SIL Open Font License 1.1; derived from Noto Sans CJK SC.",
        }
    )
    fb.setupOS2(
        sTypoAscender=src["hhea"].ascent,
        sTypoDescender=src["hhea"].descent,
        usWinAscent=src["hhea"].ascent,
        usWinDescent=-src["hhea"].descent,
    )
    fb.setupPost()
    fb.setupMaxp()
    fb.font["head"].created = fb.font["head"].modified = 3660681600
    fb.font.recalcTimestamp = False
    sink = io.BytesIO()
    fb.save(sink)
    dst.write_text(
        "\n".join(textwrap.wrap(base64.b64encode(sink.getvalue()).decode(), 100)) + "\n"
    )


if __name__ == "__main__":
    import sys

    make(sys.argv[1], Path(__file__).with_name("campaign-sans.ttf.b64"))
