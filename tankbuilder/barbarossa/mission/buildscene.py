import struct
from ...enemy_assets import refs, subtree
from ...campaign_ugui import PTR, require
from ...serialization import parse_complete, assert_roundtrip, encode_complete
from ...unity_assets import pp, xyz
from ..native import quat
from .codec import Linker, part, kids, cname, update
from .interface import battle_ui


def erase(sf, g):
    # Unit and scenery graphs consist only of Transform (the HUD is preserved).
    for gid, parts, _ in list(subtree(sf, g)):
        for i in (gid, *parts):
            del sf.objects[i]


def cut(sf, g, keep=()):
    old = kids(sf, g)
    t = part(sf, g, "Transform")
    survive = [part(sf, x, "Transform") for x in old if x in keep]
    update(sf, t, m_Children=[pp(i) for i in survive])
    for x in old:
        if x not in keep:
            erase(sf, x)


def attach(link, s, fn, g, grp, row):
    nodes = list(subtree(s, g))
    ids = {p: link.alloc() for gid, ps, _ in nodes for p in (gid, *ps)}
    remap = link.mapper(s, fn, ids)
    tr0 = nodes[0][2]
    ctl = {}
    sf = link.sf
    for old, new in ids.items():
        o = s.objects[old]
        if o.type.name == "MonoBehaviour":
            c = cname(o, link.names)
            raw = link.behaviour(o, remap, row["team"], row["route"])
            if c in (
                "PlayerControl",
                "AIControl",
                "UnitStatus",
                "Launcher",
                "BodyMove",
            ):
                ctl[c] = new
        else:
            v = refs(assert_roundtrip(o), remap)
            if old == g:
                v.update(
                    m_Name=(
                        row["tank"] + "_Player"
                        if row["team"] == "player"
                        else row["tank"] + "_AI_" + row["id"].rsplit("_", 1)[1]
                    ),
                    m_IsActive=True,
                )
            if old == tr0:
                v.update(
                    m_Father=pp(grp),
                    m_LocalPosition=xyz(row["pos"]),
                    m_LocalRotation=quat(row["yaw"]),
                )
            raw = encode_complete(o, v)
        link.add(o, new, raw)
    xf = assert_roundtrip(sf.objects[grp])
    xf["m_Children"].append(pp(ids[tr0]))
    update(sf, grp, **xf)
    require(
        ("PlayerControl" in ctl) == (row["team"] == "player")
        and ("AIControl" in ctl) == (row["team"] != "player"),
        "Wrong controller",
    )
    row.update(
        root=ids[g], transform=ids[tr0], source=fn, source_root=g, controllers=ctl
    )


def merge_map(link, m):
    sf = link.sf
    source = "level21"
    camera = next(
        p
        for p, o in m.objects.items()
        if o.type.name == "GameObject"
        and parse_complete(o)["m_Name"] == "Map Preview Camera"
    )
    skip = {p for g, ps, t in subtree(m, camera) for p in (g, *ps)}
    globals_ = {"RenderSettings", "NavMeshSettings", "LightmapSettings"}
    ids = {
        p: link.alloc()
        for p, o in m.objects.items()
        if p not in skip and o.type.name not in globals_
    }
    for p, o in m.objects.items():
        if o.type.name in globals_:
            ids[p] = next(
                i for i, x in sf.objects.items() if x.type.name == o.type.name
            )
    mapper = link.mapper(m, source, ids)
    sun = None
    root = None
    for p, i in ids.items():
        o = m.objects[p]
        k = o.type.name
        if k == "LightmapSettings":
            continue  # Both donors use an unbaked scene; retain this field's own external indexes.
        if k == "Light":
            raw = bytearray(o.get_raw_data())
            f, g = PTR.unpack_from(raw)
            require(f == 0, "Map sun owner")
            PTR.pack_into(raw, 0, 0, ids[g])
            sun = i
        else:
            v = refs(parse_complete(o), mapper)
            raw = bytearray(encode_complete(o, v))
            if k == "Terrain":
                raw[195] = o.get_raw_data()[195]
            if k == "GameObject" and v["m_Name"] == "Barbarossa_Polesie_Summer":
                root = i
        link.add(o, i, bytes(raw))
    require(root and sun, "Barbarossa native scenery missing")
    return root, sun


def make(sf, m, models, rows, names, home, txt, objective, gui, fonts, h, props):
    l = Linker(sf, names)
    # Keep the original Soviet mission slot and result trigger. No inactive stock army is shipped in this scene.
    for scenario in kids(sf, 5328):
        if scenario != 8832:
            cut(sf, scenario)
            update(sf, scenario, m_IsActive=False)
    groups = {"player": 451, "friend": 7063, "enemy": 1940}
    for g in groups.values():
        cut(sf, g)
    # The game's duel references must still point to containers, but it must have no fallback spawns.
    for g in kids(sf, 3424)[:2]:
        cut(sf, g)
    update(sf, 3424, m_IsActive=False)
    # The old field contains the old daylight referenced by GameControl, replaced below.
    erase(sf, 7347)
    erase(sf, 18637)
    maproot, sun = merge_map(l, m)
    gc = sf.objects[155115]
    r = bytearray(gc.get_raw_data())
    require(
        PTR.unpack_from(r, 124) == (0, 5328) and PTR.unpack_from(r, 164) == (0, 146058),
        "Wrong stock battle controller",
    )
    PTR.pack_into(r, 164, 0, sun)
    struct.pack_into("<i", r, 120, 1)
    gc.set_raw_data(bytes(r))
    update(sf, 5328, m_IsActive=True)
    update(sf, 8832, m_IsActive=True)
    update(sf, part(sf, 5494, "Transform"), m_LocalPosition=xyz(objective))
    for row in rows:
        fn, s, g = models[(row["tank"], row["team"] == "player")]
        attach(l, s, fn, g, part(sf, groups[row["team"]], "Transform"), row)
    # The first Soviet T34-76 is the stock type-2 fallback also used by TankGenManager.
    # This is a scene-local reference: any fallback for the preselected slot also produces a controllable T26.
    gen = sf.objects[155556]
    raw = bytearray(gen.get_raw_data())
    oldf, oldp = PTR.unpack_from(raw, 96)
    require(
        sf.externals[oldf - 1].path == "resources.assets" and oldp == 3455,
        "Unknown default player slot",
    )
    name, pref, g = models["T26", True]
    tf = l.external(name)
    # The hero is fixed for this scenario. Even if the stock generator reads an earlier garage selection,
    # every valid Soviet player slot in this scene resolves to the same real T26_Player.
    nn = struct.unpack_from("<i", raw, 44)[0]
    require(5 <= nn <= 64, "Unexpected Soviet player catalogue")
    for at in range(48, 48 + 12 * nn, 12):
        fid, target = PTR.unpack_from(raw, at)
        if target:
            require(
                sf.externals[fid - 1].path == "resources.assets",
                "Unexpected Soviet fallback donor",
            )
            PTR.pack_into(raw, at, tf, g)
    gen.set_raw_data(bytes(raw))
    ui = battle_ui(l, home, txt)
    from .minimap import install

    ui["minimap"] = install(l, gui, h, props)
    # A localized placeholder from the original battle mockup must not ask to select a different vehicle.
    from ...campaign_ugui import text_value, string

    placeholder = sf.objects[155469]
    src = placeholder.get_raw_data()
    require(text_value(src) == "Choose your tank!", "Unknown HUD placeholder")
    placeholder.set_raw_data(src[:144] + string("驾驶 T26，与友军一同夺取村口阵地。"))
    for cmp in parse_complete(sf.objects[4030])["m_Component"]:
        loc = sf.objects[cmp["component"]["m_PathID"]]
        if (
            loc.type.name == "MonoBehaviour"
            and cname(loc, names) == "LeanLocalizedText"
        ):
            rr = bytearray(loc.get_raw_data())
            rr[12] = 0
            loc.set_raw_data(bytes(rr))
    from .font import bind

    ui["font"] = bind(
        l,
        fonts,
        {
            "炼狱之门  ·  巴巴罗萨行动 Ⅰ\n驾驶 T26，与友军一同夺取村口阵地。",
            "驾驶 T26，与友军一同夺取村口阵地。",
            "返回标题",
        },
    )
    return ui, sf.save()
