"""UGUI onClick actions and the stock battle briefing. No custom runtime or selection dialog."""

import struct
from ...extra_campaign import Scene, SLOT, EMPTY, PAGE_NAME
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
from . import INDEX, TITLE
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


def start():
    return event(0, SCENES, "LoadScene", 3, INDEX)


def events(rows):
    return struct.pack("<i", len(rows)) + b"".join(rows)


def click(o, rows):
    raw = o.get_raw_data()
    at = button_event(raw)[1]
    b = raw[:at] + events(rows)
    button_event(b)
    o.set_raw_data(b)


def menu(sf, stage, names, fonts):
    home = Scene(sf, names)
    stock = Scene(stage, names)
    page = next(g for g, v in home.go.items() if v["m_Name"] == PAGE_NAME)
    slots = home.children(page)[2]
    slot = home.children(slots)[0]
    txt = home.children(slot)[0]
    tx = sf.objects[home.part[txt]["Text"]]
    require(text_value(tx.get_raw_data()) == EMPTY, "Mission slot occupied")
    tx.set_raw_data(tx.get_raw_data()[:144] + string(TITLE))
    # This label also works with the original game's Chinese legacy font outside its stock text tables.
    update(sf, slot, m_Name="Barbarossa 01 - Gates of Hell")
    src = stage.objects[stock.part[SLOT]["Button"]]
    lk = Linker(sf, names)
    bi = lk.alloc()
    image = home.part[slot]["Image"]
    mi = stock.part[SLOT]["Image"]

    def ref(f, p):
        if not p:
            return 0, 0
        if not f:
            return 0, {SLOT: slot, mi: image}[p]
        e = stage.externals[f - 1]
        return lk.external(e.path, e), p

    im = sf.objects[image]
    ir = bytearray(im.get_raw_data())
    ir[44:60] = stage.objects[mi].get_raw_data()[44:60]
    ir[60] = 1
    im.set_raw_data(bytes(ir))
    raw = clone_component("Button", src.get_raw_data(), ref, clicks=[])
    button = lk.add(src, bi, raw)
    g = parse_complete(sf.objects[slot])
    g["m_Component"].append({"component": pp(bi)})
    update(sf, slot, **g)
    gp = next(
        p["GameParamManager"] for p in home.part.values() if "GameParamManager" in p
    )
    click(
        button,
        [
            event(gp, PARAM, "set_GameMode", 3, 0),
            event(gp, PARAM, "set_PlayerNation", 3, 0),
            event(gp, PARAM, "set_EnemyNation", 3, 1),
            event(gp, PARAM, "set_PlayerUnitIndex", 3, 2),
            event(gp, PARAM, "set_CurrentStageNum", 3, 1),
            event(0, TIME, "set_timeScale", 4, number=1.0),
            start(),
        ],
    )
    e = next(g for g, v in home.go.items() if v["m_Name"] == "Hatch Extra Campaign")
    ob = sf.objects[home.part[e]["Button"]]
    raw = ob.get_raw_data()
    _, at, old = button_event(raw)
    require(
        [v[2] for v in old] == ["SetActive", "SetActive", "SetActive", "Select"],
        "Unexpected page navigation",
    )
    ob.set_raw_data(
        raw[:at] + write_calls([(v[0][1], bool(v[9])) for v in old[:-1]] + [(bi, None)])
    )
    from .font import bind

    bind(lk, fonts, {"额外战役", "巴巴罗萨行动", TITLE})
    return sf.save(), (home, txt)


def battle_ui(link, home, txt):
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
    font = PTR.unpack_from(source_text.get_raw_data(), 88)
    gt = parse_complete(src.objects[txt])
    gt.update(
        m_Name="Barbarossa 01 opening",
        m_IsActive=True,
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
            source_text.get_raw_data(),
            ref,
            label=TITLE + "  ·  巴巴罗萨行动 Ⅰ\n驾驶 T26，与友军一同夺取村口阵地。",
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
            click(o, [event(0, TIME, "set_timeScale", 4, number=1.0), start()])
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
