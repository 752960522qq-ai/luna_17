import struct
import math
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


def attach(link, s, fn, g, grp, row, *, factory=False):
    nodes = list(subtree(s, g))
    ids = {p: link.alloc() for gid, ps, _ in nodes for p in (gid, *ps)}
    if row["tank"] == "T26":
        # The physical solver writes vertices through sharedMesh. Scene instances
        # must not animate the same buffer as another vehicle or the generator prefab.
        for gid, _, _ in nodes:
            if parse_complete(s.objects[gid])["m_Name"] not in (
                "T26_Belt_L80",
                "T26_Belt_R80",
            ):
                continue
            (child,) = kids(s, gid)
            mesh = parse_complete(s.objects[part(s, child, "MeshFilter")])["m_Mesh"]
            require(
                mesh["m_FileID"] == 0 and mesh["m_PathID"] not in ids,
                "Invalid physical belt mesh",
            )
            ids[mesh["m_PathID"]] = link.alloc()
    if factory:
        # The stock generator deactivates the first player child before Instantiate.
        # Keep its real source in this same scene, with its render assets, on a separate
        # inactive parent. activeSelf must be true for the unparented spawned clone.
        for p, o in s.objects.items():
            if o.type.name in ("Mesh", "Material", "Texture2D") and p not in ids:
                ids[p] = link.alloc()
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
    # Native Launcher.Init discovers the main gun from its empty name slot.
    # Keep the actual weapon title on UnitStatus, as ordinary field spawns do.
    from .scope_flight import IMPORTED, primary
    if row["tank"] in IMPORTED:
        primary(link, row, row["tank"])


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


def make(sf, m, models, rows, names, ui_source, objective, gui, fonts, h, props, side):
    l = Linker(sf, names)
    from .objectives import bind as bind_objective

    bind_objective(sf, side)
    pgroup, fgroup, egroup, base = kids(sf, side.scenario)
    require(
        [
            parse_complete(sf.objects[g])["m_Name"]
            for g in (pgroup, fgroup, egroup, base)
        ]
        == ["Units (Player)", "Units (Friend)", "Units (Enemy)", "Base"],
        "Unrecognized stock side hierarchy",
    )
    from . import waves

    air = waves.move_air(sf, side, egroup)
    # Preserve the selected nation's first slot; omit the armies from every other scenario.
    for scenario in kids(sf, 5328):
        if scenario != side.scenario:
            cut(sf, scenario)
            update(sf, scenario, m_IsActive=False)
    groups = {"player": pgroup, "friend": fgroup, "enemy": egroup}
    for g in groups.values():
        cut(sf, g, keep=(air,) if g == egroup else ())
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
    # Stock GameControl.Start activates the campaign, selects the country's stage, then
    # TankGenManager replaces its first player child. Do not wake the placeholder early.
    update(sf, 5328, m_IsActive=False)
    update(sf, side.scenario, m_IsActive=False)
    update(sf, part(sf, base, "Transform"), m_LocalPosition=xyz(objective))
    for row in rows:
        fn, s, g = models[(row["tank"], row["team"] == "player")]
        attach(l, s, fn, g, part(sf, groups[row["team"]], "Transform"), row)
    # The very first visible frame is already behind the selected tank. The original
    # CameraControl remains unparented and takes over through the native turret binding.
    from .. import layout

    hero_row = next(row for row in rows if row["team"] == "player")
    x, y, z = hero_row["pos"]
    a = math.radians(hero_row["yaw"])
    cx, cz = x - 9 * math.sin(a), z - 9 * math.cos(a)
    cy = max(y + 3.5, float(layout.ground(h, cx, cz)) + 2.5)
    half_pitch = math.atan2(cy - y - 1.45, 9) / 2
    sy, wy = math.sin(a / 2), math.cos(a / 2)
    sp, wp = math.sin(half_pitch), math.cos(half_pitch)
    update(
        sf,
        part(sf, 791, "Transform"),
        m_LocalPosition=xyz((cx, cy, cz)),
        m_LocalRotation=dict(x=wy * sp, y=sy * wp, z=-sy * sp, w=wy * wp),
    )
    # Use a real player prefab also on all valid stock fallback slots for the selected
    # nation, including the German exchange table. Leave the other nation's entries alone.
    gen = sf.objects[155556]
    raw = bytearray(gen.get_raw_data())
    at = 44
    fn, template, donor = models[side.vehicle, True]

    def fixture(name, active, par):
        go, trid = l.alloc(), l.alloc()
        src = sf.objects[pgroup]
        gv = parse_complete(src)
        gv.update(m_Name=name, m_IsActive=active, m_Component=[{"component": pp(trid)}])
        l.add(src, go, encode_complete(src, gv))
        st = sf.objects[part(sf, pgroup, "Transform")]
        rv = parse_complete(st)
        rv.update(m_GameObject=pp(go), m_Father=pp(par), m_Children=[])
        l.add(st, trid, encode_complete(st, rv))
        rv = parse_complete(sf.objects[par])
        update(sf, par, m_Children=rv["m_Children"] + [pp(trid)])
        return go, trid

    world = part(sf, maproot, "Transform")
    fixture("Hatch Battle " + side.code, True, world)
    garage, gt = fixture("Hatch Factory " + side.code, False, world)
    factory = dict(hero_row, pos=[0.0, 0.0, 0.0], yaw=0.0)
    attach(l, template, fn, donor, gt, factory, factory=True)
    hero = factory["root"]
    for table in range(3):
        n = struct.unpack_from("<i", raw, at)[0]
        require(5 <= n <= 64, "Unknown player catalogue layout")
        if table == side.nation:
            f, p = PTR.unpack_from(raw, at + 4 + 4 * 12)
            require(
                sf.externals[f - 1].path == "resources.assets" and p == donor,
                "Wrong native donor in tank slot 4",
            )
        if table == side.nation or (side.code == "GE" and table == 2):
            for pos in range(at + 4, at + 4 + 12 * n, 12):
                fid, pid = PTR.unpack_from(raw, pos)
                if pid:
                    require(
                        sf.externals[fid - 1].path == "resources.assets",
                        "Unknown player resource",
                    )
                    PTR.pack_into(raw, pos, 0, hero)
        at += 4 + 12 * n
    gen.set_raw_data(bytes(raw))
    schedule = waves.install(
        l, side.scenario, rows, base, side, air, ui_source[0].sf.objects[2382]
    )
    ui = battle_ui(l, *ui_source, side)
    from .minimap import install

    ui["minimap"] = install(l, gui, h, props)
    # The stock Field 1 HUD has reusable localized orders for a hill and a timed defence.
    # Replace source orders only. 155469 is GameUiManager's live message output;
    # it must keep its original font and remain available for hit/kill/repair/radio text.
    from ...campaign_ugui import text_value, string

    for p, expected in (
        (158649, "Coordinate with friendly forces and capture the hill!"),
        (161599, "Coordinate with friendly forces and capture the hill!"),
        (158934, "Defend your position until reinforcements arrive!"),
        (167788, "Defend your position until reinforcements arrive!"),
    ):
        text = sf.objects[p]
        src = text.get_raw_data()
        require(text_value(src) == expected, "Unknown native mission hint")
        text.set_raw_data(src[:144] + string(side.briefing))
        owner = PTR.unpack_from(src, 0)[1]
        for cmp in parse_complete(sf.objects[owner])["m_Component"]:
            loc = sf.objects[cmp["component"]["m_PathID"]]
            if (
                loc.type.name == "MonoBehaviour"
                and cname(loc, names) == "LeanLocalizedText"
            ):
                rr = bytearray(loc.get_raw_data())
                rr[12] = 0
                loc.set_raw_data(bytes(rr))
    from .font import bind

    ui["font"] = bind(l, fonts, {side.opening, side.briefing, "返回标题"})
    from .lettering import install as lettering

    lettering(l, sf.objects[159011], gui.objects[121], {side.opening})
    return dict(
        groups=groups,
        scenario=side.scenario,
        base=base,
        objective_control=side.objective_control,
        ui=ui,
        schedule=schedule,
        factory={"garage": garage, "root": hero, "controllers": factory["controllers"]},
    ), sf.save()
