"""UGUI onClick actions and the stock battle briefing. No custom runtime or selection dialog."""

import struct
from ...extra_campaign import Scene, SLOT, EMPTY, PAGE_NAME, map_tree
from ...campaign_ugui import (
    PTR,
    OBJECT_TYPE,
    string,
    button_event,
    clone_component,
    text_value,
    write_calls,
    require,
)
from ...serialization import parse_complete, assert_roundtrip, encode_complete
from ...unity_assets import pp
from . import TITLE, GERMAN, SOVIET
from .codec import Linker, update, part, kids, cname


def event(target, cls, method, mode=1, integer=0, number=0.0, label="", flag=False):
    return (
        PTR.pack(0, target)
        + string(cls)
        + string(method)
        + struct.pack("<i", mode)
        + PTR.pack(0, 0)
        + string(OBJECT_TYPE)
        + struct.pack("<if", integer, number)
        + string(label)
        + struct.pack("<ii", int(flag), 2)
    )


SCENES = "UnityEngine.SceneManagement.SceneManager, UnityEngine.CoreModule"
TIME = "UnityEngine.Time, UnityEngine.CoreModule"
PARAM = "GameParamManager, Assembly-CSharp"


def start(side):
    return event(0, SCENES, "LoadScene", 3, side.index)


def events(rows):
    return struct.pack("<i", len(rows)) + b"".join(rows)


def click(o, rows):
    raw = o.get_raw_data()
    at = button_event(raw)[1]
    b = raw[:at] + events(rows)
    button_event(b)
    o.set_raw_data(b)


def navigate(o, *, left=0, right=0, up=0, down=0):
    raw = bytearray(o.data or o.get_raw_data())
    struct.pack_into("<ii", raw, 32, 4, 0)  # Navigation.Explicit; no wrap
    for pos, pid in ((40, up), (52, down), (64, left), (76, right)):
        PTR.pack_into(raw, pos, 0, pid)
    o.set_raw_data(bytes(raw))


def menu(sf, stage, names, fonts, raw_image, texture):
    """Present the two play actions on the same native mission selection page."""
    home = Scene(sf, names)
    stock = Scene(stage, names)
    lk = Linker(sf, names)
    page = next(g for g, v in home.go.items() if v["m_Name"] == PAGE_NAME)
    _, _, slots, back = home.children(page)
    (slot,) = home.children(slots)
    (txt,) = home.children(slot)
    tx = sf.objects[home.part[txt]["Text"]]
    original_text = tx.get_raw_data()
    require(
        text_value(original_text) == EMPTY and "Button" not in home.part[slot],
        "Unexpected source mission row",
    )
    stock_button = stage.objects[stock.part[SLOT]["Button"]]
    base_rect = home.rect[slots]
    btns = {}
    sibling_rects = []
    # Use the original on-page row as a noninteractive title, and duplicate its native
    # image, label, outline and hierarchy for two independently focusable hit areas.
    for side, x in ((GERMAN, -117.0), (SOVIET, 117.0)):
        all_ids = [p for g in (slot, txt) for p in (g, *home.part[g].values())]
        ids = {p: lk.alloc() for p in all_ids}

        def local(f, p):
            if f or p in (0, base_rect):
                return f, p
            require(p in ids, "Foreign local UI dependency")
            return 0, ids[p]

        for g in (slot, txt):
            go = sf.objects[g]
            gt = map_tree(assert_roundtrip(go), local)
            gt["m_Name"] = (
                ("Gates of Hell - " + side.code) if g == slot else "Faction label"
            )
            lk.add(go, ids[g], encode_complete(go, gt))
            for kind, p in home.part[g].items():
                o = sf.objects[p]
                if o.type.name == "MonoBehaviour":
                    b = bytearray(
                        clone_component(kind, o.get_raw_data(), local, label=side.label)
                    )
                    if kind == "Image":
                        b[44:60] = stage.objects[
                            stock.part[SLOT]["Image"]
                        ].get_raw_data()[44:60]
                        b[60] = 1
                    if kind == "Text":
                        b[60] = 0
                        struct.pack_into("<i", b, 100, 25)
                    raw = bytes(b)
                else:
                    val = map_tree(assert_roundtrip(o), local)
                    if g == slot and kind == "RectTransform":
                        val.update(
                            m_AnchoredPosition={"x": x, "y": -25.0},
                            m_SizeDelta={"x": 218.0, "y": 80.0},
                        )
                    raw = encode_complete(o, val)
                lk.add(o, ids[p], raw)

        def donor_ref(f, p):
            if not p:
                return 0, 0
            if not f:
                return 0, {
                    SLOT: ids[slot],
                    stock.part[SLOT]["Image"]: ids[home.part[slot]["Image"]],
                }[p]
            e = stage.externals[f - 1]
            return lk.external(e.path, e), p

        bi = lk.alloc()
        button = lk.add(
            stock_button,
            bi,
            clone_component(
                "Button", stock_button.get_raw_data(), donor_ref, clicks=[]
            ),
        )
        target_go = ids[slot]
        gv = parse_complete(sf.objects[target_go])
        gv["m_Component"].append({"component": pp(bi)})
        update(sf, target_go, **gv)
        # A marker requests a typed handoff on UnityMain. Enum property setters are
        # not Int32 UnityEvent receivers and the scene copy of the singleton can be stale.
        marker, marker_tr = lk.alloc(), lk.alloc()
        gv = assert_roundtrip(sf.objects[slot])
        gv.update(
            m_Name="Hatch Start " + side.code,
            m_IsActive=False,
            m_Component=[{"component": pp(marker_tr)}],
        )
        lk.add(sf.objects[slot], marker, encode_complete(sf.objects[slot], gv))
        mr = sf.objects[home.rect[slot]]
        rv = assert_roundtrip(mr)
        rv.update(
            m_GameObject=pp(marker), m_Father=pp(ids[home.rect[slot]]), m_Children=[]
        )
        lk.add(mr, marker_tr, encode_complete(mr, rv))
        rt_id = ids[home.rect[slot]]
        rtree = parse_complete(sf.objects[rt_id])
        update(sf, rt_id, m_Children=[*rtree["m_Children"], pp(marker_tr)])
        click(
            button,
            [
                event(
                    marker,
                    "UnityEngine.GameObject, UnityEngine.CoreModule",
                    "SetActive",
                    6,
                    flag=True,
                )
            ],
        )
        btns[side.code] = bi
        sibling_rects.append(pp(ids[home.rect[slot]]))
    update(sf, base_rect, m_Children=[pp(home.rect[slot]), *sibling_rects])
    update(sf, slot, m_Name="Barbarossa 01 - Gates of Hell")
    im = sf.objects[home.part[slot]["Image"]]
    ir = bytearray(im.get_raw_data())
    ir[60] = 0
    im.set_raw_data(bytes(ir))
    title_text = bytearray(original_text[:144] + string(TITLE))
    title_text[60] = 0
    tx.set_raw_data(bytes(title_text))
    back_button = home.part[back]["Button"]
    navigate(sf.objects[btns["SO"]], left=btns["GE"], down=back_button)
    navigate(sf.objects[btns["GE"]], right=btns["SO"], down=back_button)
    navigate(sf.objects[back_button], up=btns["SO"])
    entry = next(g for g, v in home.go.items() if v["m_Name"] == "Hatch Extra Campaign")
    ob = sf.objects[home.part[entry]["Button"]]
    raw = ob.get_raw_data()
    _, at, old = button_event(raw)
    require(
        [v[2] for v in old] == ["SetActive", "SetActive", "SetActive", "Select"],
        "Unexpected page navigation",
    )
    ob.set_raw_data(
        raw[:at]
        + write_calls([(v[0][1], bool(v[9])) for v in old[:-1]] + [(btns["SO"], None)])
    )
    from .font import bind

    from .lettering import install as lettering

    labels = {"额外战役", "巴巴罗萨行动", TITLE, GERMAN.label, SOVIET.label}
    bind(lk, fonts, labels)
    lettering(lk, raw_image, texture, labels)
    return sf.save(), (home, txt, original_text)


def battle_ui(link, home, txt, original_text, side):
    sf = link.sf
    src = home.sf
    # Draw the caption above the original play panel. Fade Scene remains the last overlay.
    g = link.alloc()
    r = link.alloc()
    rend = link.alloc()
    tx = link.alloc()
    timer = link.alloc()
    rt = sf.objects[part(sf, 4037, "RectTransform")]
    source_text = src.objects[home.part[txt]["Text"]]
    font = PTR.unpack_from(original_text, 88)
    gt = parse_complete(src.objects[txt])
    gt.update(
        m_Name="Barbarossa 01 opening",
        m_IsActive=False,
        m_Component=[{"component": pp(i)} for i in (r, rend, tx, timer)],
    )
    link.add(src.objects[txt], g, encode_complete(src.objects[txt], gt))
    sr = src.objects[home.rect[txt]]
    v = assert_roundtrip(sr)
    v.update(
        m_GameObject=pp(g),
        m_Father=pp(rt.path_id),
        m_Children=[],
        m_AnchorMin={"x": 0.5, "y": 0.78},
        m_AnchorMax={"x": 0.5, "y": 0.78},
        m_AnchoredPosition={"x": 0.0, "y": 0.0},
        m_Pivot={"x": 0.5, "y": 0.5},
        m_SizeDelta={"x": 680.0, "y": 86.0},
    )
    link.add(sr, r, encode_complete(sr, v))
    v = assert_roundtrip(rt)
    v["m_Children"].insert(-1, pp(r))
    update(sf, rt.path_id, **v)
    cr = src.objects[home.part[txt]["CanvasRenderer"]]
    v = assert_roundtrip(cr)
    v["m_GameObject"] = pp(g)
    link.add(cr, rend, encode_complete(cr, v))

    def ref(f, p):
        if not p:
            return 0, 0
        if f:
            e = src.externals[f - 1]
            return link.external(e.path, e), p
        require(p == txt, "Foreign title reference")
        return 0, g

    b = bytearray(
        clone_component(
            "Text",
            original_text,
            ref,
            label=side.opening,
            font=font,
        )
    )
    b[60] = 0
    struct.pack_into("<i", b, 100, 24)
    link.add(source_text, tx, bytes(b))
    tim = src.objects[2382]
    require(cname(tim, link.names) == "TimedEvent", "No stock TimedEvent")
    b = bytearray(tim.get_raw_data()[:32])
    PTR.pack_into(b, 0, 0, g)
    f, p = PTR.unpack_from(b, 16)
    e = src.externals[f - 1]
    PTR.pack_into(b, 16, link.external(e.path, e), p)
    # duration, play on enable, UnityEvent.
    b += struct.pack("<fi", 6.0, 1) + write_calls([(g, False)])
    link.add(tim, timer, bytes(b))
    for o in list(sf.objects.values()):
        if o.type.name != "MonoBehaviour" or cname(o, link.names) != "Button":
            continue
        raw = o.get_raw_data()
        go = PTR.unpack_from(raw, 0)[1]
        calls = button_event(raw)[2]
        if any(v[2] == "ButtonFunc" and v[3] == 3 and v[6] == 2 for v in calls):
            click(o, [event(0, TIME, "set_timeScale", 4, number=1.0), start(side)])
        if any(v[2] == "ButtonFunc" and v[3] == 3 and v[6] == 3 for v in calls):
            # No second extra mission exists; use the native title-return action on this button.
            require(
                len(calls) == 1 and calls[0][2] == "ButtonFunc", "Unknown next button"
            )
            click(o, [event(calls[0][0][1], calls[0][1], "ButtonFunc", 3, 1)])
            stack = list(kids(sf, go))
            while stack:
                child = stack.pop()
                stack.extend(kids(sf, child))
                gt = parse_complete(sf.objects[child])
                for c in gt["m_Component"]:
                    obj = sf.objects[c["component"]["m_PathID"]]
                    if (
                        obj.type.name == "MonoBehaviour"
                        and cname(obj, link.names) == "Text"
                    ):
                        txtb = obj.get_raw_data()
                        value = text_value(txtb)
                        obj.set_raw_data(
                            txtb[:144]
                            + string("Title" if value == "Next" else "返回标题")
                        )
                    if obj.type.name == "MonoBehaviour" and cname(
                        obj, link.names
                    ).startswith("LeanLocalized"):
                        b = bytearray(obj.get_raw_data())
                        b[12] = 0
                        obj.set_raw_data(bytes(b))
    return {"opening": g, "timer": timer}
