"""Reopen the shipped Unity files; do not trust generator counts or intended binding names."""

import math, struct, hashlib
from collections import Counter
from ...extra_campaign import file, Scene, PAGE_NAME
from ...enemy_assets import subtree
from ...campaign_ugui import button_event, text_value, PTR, require
from ...serialization import parse_complete
from ...unity_assets import read_mb, pp, SCHEMA
from ...bt7.integrate import pointers
from .. import layout
from . import INDEX, SCENE, TITLE
from .codec import part, kids, cname, extra_offsets
from .interface import SCENES, PARAM
from .lanes import Lanes

EXPECTED = {
    ("player", "T26"): 1,
    ("friend", "T26"): 4,
    ("friend", "BT7"): 3,
    ("friend", "T34_76"): 2,
    ("enemy", "Panzer_IV_Ausf_C"): 2,
    ("enemy", "Panzer_II_Ausf_F"): 3,
    ("enemy", "Panzer_III_J"): 3,
    ("enemy", "Panzer_38t"): 3,
}


def verify(raw, prior, spec, names):
    from .release import Members

    b, old = Members(raw), Members(prior)
    sf = file(b.read("level22"))
    mg = file(b.read("globalgamemanagers"))
    title = Scene(file(b.read("level0")), names)
    bs = next(o for o in mg.objects.values() if o.type.name == "BuildSettings")
    scene_list = parse_complete(bs)["scenes"]
    require(
        scene_list[INDEX] == SCENE and len(scene_list) == INDEX + 1,
        "Battle not registered",
    )
    ob = file(old.read("globalgamemanagers"))
    bm = next(o for o in ob.objects.values() if o.type.name == "BuildSettings")
    require(
        parse_complete(bm)["scenes"] == scene_list[:-1], "Vanilla scene slots shifted"
    )
    for n, t in old.members.items():
        if n not in ("level0", "globalgamemanagers"):
            require(b.members[n] == t, "Prior resource overwritten: " + n)
    require(b.read("level21") == old.read("level21"), "Reusable map was replaced")
    p = next(i for i, g in title.go.items() if g["m_Name"] == PAGE_NAME)
    row = title.children(title.children(p)[2])[0]
    tx = title.children(row)[0]
    txt = title.sf.objects[title.part[tx]["Text"]]
    require(text_value(txt.get_raw_data()) == TITLE, "Wrong mission row")
    ff, fp = PTR.unpack_from(txt.get_raw_data(), 88)
    require(
        ff == 0
        and parse_complete(title.sf.objects[fp])["m_Name"] == "Hatch Campaign Sans",
        "Missing Chinese title font",
    )
    from .font import covers

    require(
        covers(
            parse_complete(title.sf.objects[fp])["m_FontData"],
            TITLE + "巴巴罗萨行动额外战役",
        ),
        "Missing Chinese title glyphs",
    )
    bt = next(
        o
        for o in sf.objects.values()
        if o.type.name == "MonoBehaviour"
        and cname(o, names) == "Text"
        and PTR.unpack_from(o.get_raw_data(), 0) == (0, spec["ui"]["opening"])
    )
    label = text_value(bt.get_raw_data())
    ff, fp = PTR.unpack_from(bt.get_raw_data(), 88)
    require(
        ff == 0
        and fp == spec["ui"]["font"]
        and TITLE in label
        and covers(parse_complete(sf.objects[fp])["m_FontData"], label),
        "Unreadable opening message",
    )
    btn = title.part[row]["Button"]
    br = title.sf.objects[btn].get_raw_data()
    target, _, calls = button_event(br)
    require(
        PTR.unpack_from(br, target) == (0, title.part[row]["Image"]),
        "Row has no click surface",
    )
    require(
        [(x[2], x[6]) for x in calls if x[1] == PARAM]
        == [
            ("set_GameMode", 0),
            ("set_PlayerNation", 0),
            ("set_EnemyNation", 1),
            ("set_PlayerUnitIndex", 2),
            ("set_CurrentStageNum", 1),
        ],
        "Stale game state can reach mission",
    )
    require(
        calls[-1][1:4] == (SCENES, "LoadScene", 3)
        and calls[-1][6] == INDEX
        and all(x[-1] == 2 for x in calls),
        "Route does not load mission directly",
    )
    prim = title.sf.objects[title.part[426]["Button"]].get_raw_data()
    require(
        [(x[2], x[6]) for x in button_event(prim)[2]] == [("ButtonGameMode", 0)],
        "Original campaign button changed",
    )
    groups = spec["groups"]
    counts = Counter()
    teamroots = {t: kids(sf, g) for t, g in groups.items()}
    h = layout.heightgrid()
    props = layout.placements(h)
    lanes = Lanes(h, props)
    require(
        [len(teamroots[t]) for t in ("player", "friend", "enemy")] == [1, 9, 11],
        "Incorrect live spawn group sizes",
    )
    require(
        kids(sf, 8832) == [451, 7063, 1940, 5494], "Wrong stock objective structure"
    )
    require(
        len(kids(sf, 5328)) == 10
        and [g for g in kids(sf, 5328) if parse_complete(sf.objects[g])["m_IsActive"]]
        == [8832],
        "Extra stock armies possible",
    )
    pcs = []
    ais = []
    route_segments = 0
    used = set()
    srcs = {}
    xy = []
    unitrefs = 0
    for r in spec["units"]:
        g = r["root"]
        kind = r["tank"]
        team = r["team"]
        counts[team, kind] += 1
        require(g in teamroots[team] and g not in used, "Duplicate/wrong-side unit")
        used.add(g)
        shape = list(subtree(sf, g))
        owned = {i for x, ps, t in shape for i in (x, *ps)}
        gt = parse_complete(sf.objects[g])
        require(
            gt["m_IsActive"] and gt["m_Name"].startswith(kind + "_"),
            "Hidden or wrong vehicle",
        )
        tr = parse_complete(sf.objects[shape[0][2]])
        pos = tr["m_LocalPosition"]
        x, y, z = (pos[k] for k in "xyz")
        xy.append((x, z))
        require(
            tr["m_Father"] == pp(part(sf, groups[team], "Transform"))
            and max(abs(a - k) for a, k in zip((x, y, z), r["pos"])) < 0.001,
            "Wrong deploy transform",
        )
        require(
            abs(float(layout.ground(h, x, z)) + 0.35 - y) < 0.001
            and lanes.clear((x, z), (x, z)),
            "Spawn intersects terrain or scenery",
        )
        cpts = Counter()
        materials = set()
        for i in owned:
            o = sf.objects[i]
            if o.type.name == "MonoBehaviour":
                c = cname(o, names)
                cpts[c] += 1
                rr = o.get_raw_data()
                refs = (
                    list(pointers(read_mb(c, rr)))
                    if c in SCHEMA
                    else [PTR.unpack_from(rr, j) for j in extra_offsets(c, rr)]
                )
                refs += [PTR.unpack_from(rr, 0), PTR.unpack_from(rr, 16)]
                for f, pid in refs:
                    if not pid:
                        continue
                    if f == 0:
                        require(pid in owned, f"{kind} crosses instance at {c}:{pid}")
                    else:
                        require(0 < f <= len(sf.externals), "Unknown unit external")
                    unitrefs += 1
            elif o.type.name == "MeshRenderer":
                rr = parse_complete(o)
                if rr["m_Enabled"]:
                    materials.update(
                        (m["m_FileID"], m["m_PathID"]) for m in rr["m_Materials"]
                    )
        require(
            cpts["PlayerControl"] == (team == "player")
            and cpts["AIControl"] == (team != "player")
            and cpts["UnitStatus"] == 1,
            "Wrong playable controller",
        )
        fname = r["source"]
        src = srcs.get(fname)
        if src is None:
            src = srcs[fname] = file(b.read(fname))
        pg = parse_complete(src.objects[r["source_root"]])
        require(
            pg["m_Name"] == kind + ("_Player" if team == "player" else "_AI"),
            "Wrong source vehicle",
        )
        st = read_mb(
            "UnitStatus", sf.objects[r["controllers"]["UnitStatus"]].get_raw_data()
        )
        require(
            st["iFFNum"] == {"player": 0, "friend": 1, "enemy": 2}[team]
            and st["unitNation"] == int(team == "enemy"),
            "IFF / nation mismatch",
        )
        if kind in ("T26", "BT7", "Panzer_IV_Ausf_C", "Panzer_II_Ausf_F"):
            require(
                st["unitName"] == kind and len(materials) > 0,
                "Mod model/config missing",
            )
        if kind == "T34_76":
            ma = {
                p
                for f, p in materials
                if f and sf.externals[f - 1].path == "resources.assets"
            }
            require(
                {161, 162, 163} <= ma and not ma.intersection({164, 165, 166}),
                "1943 material or missing dark-green paint",
            )
        if team != "player":
            ai = r["controllers"]["AIControl"]
            ais.append(ai)
            br = sf.objects[ai].get_raw_data()
            n = struct.unpack_from("<i", br, 200)[0]
            route = [
                list(struct.unpack_from("<3f", br, 204 + i * 12)) for i in range(n)
            ]
            require(route == r["route"] and n > 0, "Lost AI path")
            prev = x, z
            for xx, _, zz in route:
                require(lanes.clear(prev, (xx, zz)), "Blocked AI segment")
                prev = xx, zz
                route_segments += 1
        else:
            pc = r["controllers"]["PlayerControl"]
            pcs.append(pc)
            pv = read_mb("PlayerControl", sf.objects[pc].get_raw_data())
            la = read_mb(
                "Launcher", sf.objects[r["controllers"]["Launcher"]].get_raw_data()
            )
            require(
                pv["thisTrf"] == pp(shape[0][2])
                and pv["launchers"] == [pp(r["controllers"]["Launcher"])]
                and la["calibre"] == 45,
                "T26 player input/gun disconnected",
            )
            require(
                pv["uStatus"] == pp(r["controllers"]["UnitStatus"])
                and pv["bMove"] == pp(r["controllers"]["BodyMove"]),
                "Player controls resolve to another unit",
            )
    require(dict(counts) == EXPECTED and len(used) == 21, "Wrong order of battle")
    require(
        min(math.dist(a, q) for i, a in enumerate(xy) for q in xy[i + 1 :]) >= 14,
        "Overlapping spawn footprints",
    )
    allscripts = Counter(
        cname(o, names) for o in sf.objects.values() if o.type.name == "MonoBehaviour"
    )
    require(
        allscripts["PlayerControl"] == 1
        and allscripts["AIControl"] == 20
        and allscripts["GameControl"] == 1
        and allscripts["GameUiManager"] == 1,
        "Stock scene includes extra units or no HUD",
    )
    # Every retained hierarchy edge is now bidirectional, even on inactive objects.
    transform = {}
    for p, o in sf.objects.items():
        if o.type.name not in ("Transform", "RectTransform"):
            continue
        v = parse_complete(o)
        transform[p] = (
            v["m_Father"]["m_PathID"],
            tuple(x["m_PathID"] for x in v["m_Children"]),
        )
    for p, (father, children) in transform.items():
        require(
            (not father or father in transform and p in transform[father][1])
            and all(c in transform and transform[c][0] == p for c in children)
            and len(children) == len(set(children)),
            f"Dangling hierarchy: {p}",
        )
    mgos = {
        parse_complete(o)["m_Name"]: p
        for p, o in sf.objects.items()
        if o.type.name == "GameObject"
    }
    require(
        "Barbarossa_Polesie_Summer" in mgos
        and "Field_01" not in mgos
        and "Map Preview Camera" not in mgos,
        "Incorrect play environment",
    )
    for k in (
        "Main Camera",
        "Canvas Mission",
        "EventSystem",
        "External Input Controller",
    ):
        require(k in mgos, "Missing stock battle system " + k)
    m = spec["ui"]["minimap"]
    require(
        PTR.unpack_from(sf.objects[m["image"]].get_raw_data(), 88) == (0, m["sprite"])
        and parse_complete(sf.objects[m["sprite"]])["m_RD"]["texture"]
        == pp(m["texture"]),
        "Wrong minimap connections",
    )
    require(
        parse_complete(sf.objects[m["texture"]])["m_Name"] == "Minimap_Polesie",
        "Stock minimap leaked",
    )
    gen = sf.objects[155556].get_raw_data()
    n = struct.unpack_from("<i", gen, 44)[0]
    so = [PTR.unpack_from(gen, 48 + 12 * i) for i in range(n)]
    require(
        all(
            not p or sf.externals[f - 1].path == "T26_Player.assets" and p == 3455
            for f, p in so
        ),
        "Stock fallback can choose a different vehicle",
    )
    for at in (*range(2884, 2944, 12), *range(2948, 3008, 12)):
        require(
            PTR.unpack_from(gen, at)[1] in sf.objects, "Tank generator marker removed"
        )
    for p in (157017, 164841):
        ac = button_event(sf.objects[p].get_raw_data())[2]
        require(ac[-1][2] == "LoadScene" and ac[-1][6] == INDEX, "Retry leaves mission")
    for p in (157146, 161903, 161932):
        ac = button_event(sf.objects[p].get_raw_data())[2]
        require(
            ac[0][2] == "ButtonFunc" and ac[0][6] == 1,
            "Unreleased next stage accessible",
        )
    base = sf.objects[155866].get_raw_data()
    coll = parse_complete(sf.objects[part(sf, 5494, "SphereCollider")])
    require(
        PTR.unpack_from(base, 32) == (0, 155115)
        and coll["m_IsTrigger"]
        and coll["m_Radius"] == 15,
        "Capture objective not connected",
    )
    ox, _, oz = spec["objective_position"]
    require(
        any(
            math.hypot(u["route"][-1][0] - ox, u["route"][-1][2] - oz) < 15
            for u in spec["units"]
            if u["team"] == "friend"
        ),
        "No friendly AI can reach objective",
    )
    return {
        "status": "passed",
        "method": "reopened shipped UnityFS and native scene; no Android playtest",
        "player": "T26",
        "player_count": len(pcs),
        "friendly_ai": 9,
        "hostile_ai": len(ais) - 9,
        "unit_count": len(used),
        "order_of_battle": {f"{a}:{t}": n for (a, t), n in counts.items()},
        "verified_unit_component_references": unitrefs,
        "verified_scene_transforms": len(transform),
        "checked_driving_segments": route_segments,
        "title_button_direct_to_index": INDEX,
        "retry_index": INDEX,
        "minimap": "Minimap_Polesie",
        "preserved_prior_members": len(old.members) - 2,
        "scene_sha256": hashlib.sha256(b.read("level22")).hexdigest(),
        "android_device_test": False,
    }
