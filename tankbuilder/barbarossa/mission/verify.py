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
from . import TITLE, SIDES, SOVIET, GERMAN
from .font import covers
from .objectives import decode as decode_rules
from .codec import part, kids, cname, extra_offsets
from .interface import SCENES, PARAM
from .lanes import Lanes

PHYSICAL = {
    ("SO", "T26"): 5,
    ("SO", "BT7"): 3,
    ("SO", "T34_76"): 2,
    ("GE", "Panzer_IV_Ausf_C"): 2,
    ("GE", "Panzer_II_Ausf_F"): 3,
    ("GE", "Panzer_III_J"): 3,
    ("GE", "Panzer_38t"): 3,
}


def expect_roster(side):
    out = {
        ("friend" if n == side.code else "enemy", tank): qty
        for (n, tank), qty in PHYSICAL.items()
    }
    out["friend", side.vehicle] -= 1
    out["player", side.vehicle] = 1
    return out


def verify_picker(title, registered):
    page = next(i for i, g in title.go.items() if g["m_Name"] == PAGE_NAME)
    _, _, slots, back = title.children(page)
    header, *choices = title.children(slots)
    require(
        "Button" not in title.part[header] and len(choices) == 2,
        "Mission row can still start the wrong side",
    )

    def label(g):
        (t,) = title.children(g)
        o = title.sf.objects[title.part[t]["Text"]]
        r = o.get_raw_data()
        s = text_value(r)
        fid, font = PTR.unpack_from(r, 88)
        require(
            not fid and covers(parse_complete(title.sf.objects[font])["m_FontData"], s),
            "Missing picker glyphs",
        )
        return s

    require(
        label(header) == TITLE
        and title.sf.objects[title.part[header]["Image"]].get_raw_data()[60] == 0,
        "Wrong mission header",
    )
    byname = {label(g): g for g in choices}
    require(set(byname) == {s.label for s in SIDES}, "Missing faction button")
    picks = {}
    rects = {}
    gp = next(
        parts["GameParamManager"]
        for parts in title.part.values()
        if "GameParamManager" in parts
    )
    for side in SIDES:
        g = byname[side.label]
        p = title.part[g]["Button"]
        b = title.sf.objects[p].get_raw_data()
        t, _, actions = button_event(b)
        im = title.part[g]["Image"]
        require(
            PTR.unpack_from(b, t) == (0, im)
            and title.sf.objects[im].get_raw_data()[60] == 1,
            "Missing touch surface",
        )
        pre, clock, load = actions[:-2], actions[-2], actions[-1]
        require(
            [(a[2], a[6]) for a in pre]
            == [
                ("set_GameMode", 0),
                ("set_PlayerNation", side.nation),
                ("set_EnemyNation", 1 - side.nation),
                ("set_PlayerUnitIndex", 4),
                ("set_CurrentStageNum", 1),
            ]
            and all(a[0] == (0, gp) and a[1] == PARAM and a[3] == 3 for a in pre),
            "Picker nation or real vehicle slot is wrong",
        )
        require(
            clock[2] == "set_timeScale"
            and clock[7] == 1
            and load[1:4] == (SCENES, "LoadScene", 3)
            and registered[load[6]] == side.scene
            and load[6] == side.index
            and all(a[-1] == 2 for a in actions),
            "Faction does not start directly",
        )
        require(
            PTR.unpack_from(b, 52) == (0, title.part[back]["Button"]),
            "Picker has no return navigation",
        )
        picks[side.code] = p
        rt = title.transform(g)
        v, w = rt["m_AnchoredPosition"], rt["m_SizeDelta"]
        require(w["x"] >= 190 and w["y"] >= 64, "Faction touch area too small")
        rects[side.code] = (
            v["x"] - w["x"] / 2,
            v["x"] + w["x"] / 2,
            v["y"] + w["y"] / 2,
        )
    require(
        rects["GE"][1] < rects["SO"][0] and max(r[2] for r in rects.values()) < 37.5,
        "Overlapping faction choices",
    )
    for code, other, off in (("SO", "GE", 64), ("GE", "SO", 76)):
        require(
            PTR.unpack_from(title.sf.objects[picks[code]].get_raw_data(), off)
            == (0, picks[other]),
            "Cross-faction focus broken",
        )
    ent = next(i for i, g in title.go.items() if g["m_Name"] == "Hatch Extra Campaign")
    open_calls = button_event(
        title.sf.objects[title.part[ent]["Button"]].get_raw_data()
    )[2]
    require(
        open_calls[-1][0] == (0, picks["SO"]) and open_calls[-1][2] == "Select",
        "Opening the picker focuses a missing row",
    )
    prim = title.sf.objects[title.part[426]["Button"]].get_raw_data()
    require(
        [(a[2], a[6]) for a in button_event(prim)[2]] == [("ButtonGameMode", 0)],
        "Original campaign menu was changed",
    )


def outcome(
    flags, *, allied_entry=False, hostile_entry=False, hostiles=11, friendly_ai=9
):
    # Exercise the inputs to the stock trigger using the switches actually serialized in the scene.
    _, win, _, lose, _ = flags
    if (hostile_entry and lose[1]) or (friendly_ai == 0 and lose[0]):
        return "loss"
    if (allied_entry and win[1]) or (hostiles == 0 and win[0]):
        return "win"
    return "playing"


def verify(raw, prior, spec, names):
    from .release import Members

    b, old = Members(raw), Members(prior)
    sfmgr = file(b.read("globalgamemanagers"))
    oldmgr = file(old.read("globalgamemanagers"))
    scene_list = lambda s: parse_complete(
        next(o for o in s.objects.values() if o.type.name == "BuildSettings")
    )["scenes"]
    installed, baseline = scene_list(sfmgr), scene_list(oldmgr)
    require(
        installed[:22] == baseline[:22]
        and len(installed) == 24
        and [installed[s.index] for s in SIDES] == [s.scene for s in SIDES],
        "Wrong scene registration",
    )
    for n, t in old.members.items():
        if n not in ("level0", "globalgamemanagers", "level22"):
            require(b.members[n] == t, "Existing resources were overwritten: " + n)
    require(b.read("level21") == old.read("level21"), "Common map was changed")
    verify_picker(Scene(file(b.read("level0")), names), installed)
    report = {}
    seen = {}
    srcs = {}
    h = layout.heightgrid()
    props = layout.placements(h)
    lanes = Lanes(h, props)
    for side in SIDES:
        sf = file(b.read(side.member))
        cfg = spec["sides"][side.code]
        require(
            cfg["index"] == side.index
            and cfg["scene"] == side.scene
            and cfg["objective"] == side.objective,
            "Wrong faction manifest",
        )
        report[side.code] = verify_side(
            b, sf, cfg, names, side, spec["objective_position"], h, lanes, srcs
        )
        signature = {}
        for r in cfg["units"]:
            p = parse_complete(sf.objects[r["transform"]])
            g = p["m_LocalPosition"]
            q = p["m_LocalRotation"]
            signature[r["id"]] = (r["nation"], r["tank"], g, q, list(r["route"]))
        seen[side.code] = signature
    require(seen["SO"].keys() == seen["GE"].keys(), "A chassis has been added or lost")
    for code, r in seen["SO"].items():
        other = seen["GE"][code]
        require(r[:4] == other[:4], "Different deployments for the same battle")
        if code not in (SOVIET.player_id, GERMAN.player_id):
            require(r[4] == other[4], "AI changed sides geographically")
    return {
        "status": "passed",
        "two_direct_entry_buttons": True,
        "same_physical_deployment": True,
        "reopened_native_scenes": report,
        "prior_unmodified_members": sum(
            b.members.get(n) == v for n, v in old.members.items()
        ),
        "android_device_test": False,
    }


def verify_side(b, sf, spec, names, side, objective, h, lanes, srcs):
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
        not ff
        and fp == spec["ui"]["font"]
        and label == side.opening
        and covers(parse_complete(sf.objects[fp])["m_FontData"], label),
        "Wrong faction briefing or font",
    )
    for hint in (155469, 158649, 161599, 158934, 167788):
        require(
            text_value(sf.objects[hint].get_raw_data()) == side.briefing,
            "Wrong starting/radio objective",
        )
        for c in parse_complete(
            sf.objects[PTR.unpack_from(sf.objects[hint].get_raw_data(), 0)[1]]
        )["m_Component"]:
            loc = sf.objects[c["component"]["m_PathID"]]
            if (
                loc.type.name == "MonoBehaviour"
                and cname(loc, names) == "LeanLocalizedText"
            ):
                require(
                    loc.get_raw_data()[12] == 0,
                    "Stock localization overwrites the faction's objective",
                )
    groups = spec["groups"]
    counts = Counter()
    teamroots = {t: kids(sf, g) for t, g in groups.items()}
    friendly, enemies = (9, 11) if side.code == "SO" else (10, 10)
    require(
        [len(teamroots[t]) for t in ("player", "friend", "enemy")]
        == [1, friendly, enemies],
        "Incorrect live spawn group sizes",
    )
    require(
        kids(sf, side.scenario)
        == [groups["player"], groups["friend"], groups["enemy"], spec["base"]],
        "Wrong stock objective structure",
    )
    require(
        len(kids(sf, 5328)) == 10
        and [g for g in kids(sf, 5328) if parse_complete(sf.objects[g])["m_IsActive"]]
        == [side.scenario],
        "Extra stock armies possible",
    )
    pcs = []
    ais = []
    route_segments = 0
    used = set()
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
            and st["unitNation"] == int(r["nation"] == "GE")
            and (r["nation"] == side.code) == (team != "enemy"),
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
            if side.code == "GE":
                import json

                pr = next(
                    parse_complete(o)
                    for o in src.objects.values()
                    if o.type.name == "TextAsset"
                    and parse_complete(o)["m_Name"] == kind + "_PlayerProfile"
                )
                doc = json.loads(pr["m_Script"])
                require(
                    doc["role"] == "player"
                    and doc["hatch_id"] == kind
                    and doc["continuous_fire"]
                    and doc["magazine"]
                    == {"capacity": 10, "shotInterval": 0.4, "reloadTime": 4.85},
                    "Wrong German player cannon profile",
                )
            pc = r["controllers"]["PlayerControl"]
            pcs.append(pc)
            pv = read_mb("PlayerControl", sf.objects[pc].get_raw_data())
            la = read_mb(
                "Launcher", sf.objects[r["controllers"]["Launcher"]].get_raw_data()
            )
            require(
                pv["thisTrf"] == pp(shape[0][2])
                and pv["launchers"] == [pp(r["controllers"]["Launcher"])]
                and kind == side.vehicle
                and r["id"] == side.player_id
                and la["calibre"] == (45 if side.code == "SO" else 20),
                "Selected player and gun disconnected",
            )
            require(
                pv["uStatus"] == pp(r["controllers"]["UnitStatus"])
                and pv["bMove"] == pp(r["controllers"]["BodyMove"]),
                "Player controls resolve to another unit",
            )
    require(
        dict(counts) == expect_roster(side) and len(used) == 21, "Wrong order of battle"
    )
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
    rawfield = file(b.read("level8"))
    gen = sf.objects[155556].get_raw_data()
    basegen = rawfield.objects[155556].get_raw_data()
    at = 44
    hero_source = next(u for u in spec["units"] if u["team"] == "player")
    for table in range(3):
        n = struct.unpack_from("<i", gen, at)[0]
        require(
            n == struct.unpack_from("<i", basegen, at)[0], "Generator counts changed"
        )
        for j in range(n):
            addr = at + 4 + j * 12
            f, p = PTR.unpack_from(gen, addr)
            of, op = PTR.unpack_from(basegen, addr)
            if op and (table == side.nation or table == 2 and side.code == "GE"):
                require(
                    sf.externals[f - 1].path == hero_source["source"]
                    and p == hero_source["source_root"],
                    "Incorrect fallback player",
                )
            else:
                require((of, op) == (f, p), "Unrelated nation or unused slot changed")
        at += 4 + 12 * n
    for at in (*range(2884, 2944, 12), *range(2948, 3008, 12)):
        require(
            PTR.unpack_from(gen, at)[1] in sf.objects, "Tank generator marker removed"
        )
    for p in (157017, 164841):
        ac = button_event(sf.objects[p].get_raw_data())[2]
        require(
            ac[-1][2] == "LoadScene" and ac[-1][6] == side.index, "Retry switched sides"
        )
    for p in (157146, 161903, 161932):
        ac = button_event(sf.objects[p].get_raw_data())[2]
        require(
            ac[0][2] == "ButtonFunc" and ac[0][6] == 1,
            "Unreleased next stage accessible",
        )
    ctrl = sf.objects[spec["objective_control"]].get_raw_data()
    require(
        PTR.unpack_from(ctrl, 0) == (0, spec["base"])
        and PTR.unpack_from(ctrl, 32) == (0, 155115)
        and PTR.unpack_from(ctrl, 44) == (0, 155487),
        "Wrong objective owner",
    )
    col = parse_complete(sf.objects[part(sf, spec["base"], "SphereCollider")])
    require(
        col["m_Enabled"] and col["m_IsTrigger"] and col["m_Radius"] == 15.0,
        "Missing capture volume",
    )
    center = parse_complete(sf.objects[part(sf, spec["base"], "Transform")])[
        "m_LocalPosition"
    ]
    ox, oy, oz = objective
    require(
        max(abs(center[k] - v) for k, v in zip("xyz", objective)) < 0.001,
        "Wrong objective position",
    )

    def inside(x, z):
        return math.hypot(x - ox, z - oz) < col["m_Radius"]

    require(
        not any(
            inside(u["pos"][0], u["pos"][2])
            for u in spec["units"]
            if u["nation"] == "GE"
        ),
        "Automatic capture on frame zero",
    )
    arrivals = sum(
        inside(u["route"][-1][0], u["route"][-1][2])
        for u in spec["units"]
        if u["nation"] == "GE" and u["team"] != "player"
    )
    require(arrivals >= 3, "German AI cannot take the position")
    near = min(
        math.hypot(u["pos"][0] - ox, u["pos"][2] - oz)
        for u in spec["units"]
        if u["nation"] == "SO"
    )
    require(near < 50, "Defenders are absent from village at the start")
    require(
        ctrl[56:] == rawfield.objects[side.template_control].get_raw_data()[56:],
        "Native end rules were not carried over",
    )
    rules = decode_rules(ctrl)
    cases = {
        k: outcome(rules, **v)
        for k, v in {
            "start": {},
            "friendly_enters": {"allied_entry": True},
            "hostile_enters": {"hostile_entry": True},
            "wave_destroyed": {"hostiles": 0},
        }.items()
    }
    expected = (
        {
            "start": "playing",
            "friendly_enters": "playing",
            "hostile_enters": "loss",
            "wave_destroyed": "win",
        }
        if side.code == "SO"
        else {
            "start": "playing",
            "friendly_enters": "win",
            "hostile_enters": "playing",
            "wave_destroyed": "playing",
        }
    )
    require(cases == expected, "Victory/defeat switches are reversed")
    return {
        "player": side.vehicle,
        "player_count": len(pcs),
        "friendly_ai": friendly,
        "enemy_ai": enemies,
        "chassis": len(used),
        "verified_unit_references": unitrefs,
        "verified_transforms": len(transform),
        "checked_driving_segments": route_segments,
        "german_ai_routes_into_capture_volume": arrivals,
        "objective_radius_m": col["m_Radius"],
        "native_rule_input_checks": cases,
        "retry_scene_index": side.index,
        "scene_sha256": hashlib.sha256(b.read(side.member)).hexdigest(),
    }
