"""Read the emitted Unity player resources back and check the physical scene and registry."""

import itertools
import math
import struct
from collections import Counter, defaultdict

import numpy as np
import UnityPy

from ..serialization import apply_reviewed_typetrees, parse_complete
from . import layout as L
from .native import SCENE_PATH, check


def single(raw):
    env = UnityPy.load(raw)
    apply_reviewed_typetrees(env)
    return next(iter(env.files.values()))


def pointers(v):
    if isinstance(v, dict):
        if set(v) == {"m_FileID", "m_PathID"}:
            yield v["m_FileID"], v["m_PathID"]
        else:
            for child in v.values():
                yield from pointers(child)
    elif isinstance(v, (tuple, list)) and v and isinstance(v[0], (tuple, list, dict)):
        for child in v:
            yield from pointers(child)


def manager_check(before, after):
    a, c = single(before), single(after)
    check(a.objects.keys() == c.objects.keys(), "Manager object set changed")
    orig = next(o for o in a.objects.values() if o.type.name == "BuildSettings")
    for key, o in a.objects.items():
        if key != orig.path_id:
            check(
                o.get_raw_data() == c.objects[key].get_raw_data(),
                "Unexpected manager change",
            )
    baseline = parse_complete(orig)
    reg = parse_complete(c.objects[orig.path_id])
    check(
        reg == dict(baseline, scenes=baseline["scenes"] + [SCENE_PATH]),
        "Scene registry mismatch",
    )


def road_checks(h, solids, anchors, bridges):
    solid = np.array(solids)
    ox, oz, c, s, hx, hz = solid.T

    def dist(x, z):
        dx = np.asarray(x).reshape(-1, 1) - ox
        dz = np.asarray(z).reshape(-1, 1) - oz
        return np.hypot(
            np.maximum(np.abs(c * dx - s * dz) - hx, 0),
            np.maximum(np.abs(s * dx + c * dz) - hz, 0),
        ).min(axis=1)

    anchor_min = min(float(dist(x, z)[0]) for x, z in anchors.values())
    check(
        anchor_min >= 3.0,
        f"Neutral marker too close to a solid object: {anchor_min:.2f} m",
    )
    results = {}
    samples = 0
    ramps = {}
    for name, (width, line) in L.LINES.items():
        pts = []
        for a, b in itertools.pairwise(line):
            n = max(1, math.ceil(np.linalg.norm(b - a) / 2))
            pts.extend(np.linspace(a, b, n, endpoint=False))
        pts = np.array([*pts, line[-1]])
        dx, dz = np.gradient(pts, axis=0).T
        k = np.hypot(dx, dz)
        x, z = pts.T
        surface = L.ground(h, x, z)
        on = np.zeros(len(x), bool)
        for bx, bz, length, span, deck in bridges.values():
            hit = (abs(x - bx) <= length / 2) & (abs(z - bz) <= span / 2)
            surface[hit] = deck
            on |= hit
        check(float(surface.min()) > L.WATER + 0.55, "Submerged road: " + name)
        pitch = float(
            (abs(np.diff(surface)) / np.linalg.norm(np.diff(pts, axis=0), axis=1)).max()
        )
        check(
            pitch < (0.09 if name == "village_road" else 0.15),
            "Excessive road grade: " + name,
        )
        # Six-metre-wide primary road corridor; 3.2 m on the narrower lanes. Deck rails checked separately.
        half = min(3.0, width * 0.27)
        for off in (-half, 0.0, half):
            for start in range(0, len(x), 200):
                ix = slice(start, start + 200)
                check(
                    float(
                        dist(
                            x[ix] + off * dz[ix] / k[ix], z[ix] - off * dx[ix] / k[ix]
                        ).min()
                    )
                    > 0.2,
                    "Solid obstacle on " + name,
                )
        results[name] = {
            "max_grade_percent": round(pitch * 100, 2),
            "length_m": round(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum()),
            "deck_samples": int(on.sum()),
        }
        samples += len(x)
    for name, (x, z, length, w, deck) in bridges.items():
        ends = [
            abs(float(L.ground(h, x + side * length * 0.5, z + off * w)) - deck)
            for side in (-1, 1)
            for off in (-0.36, 0, 0.36)
        ]
        check(max(ends) < 0.1, "Bridge approach mismatch: " + name)
        check(float(L.ground(h, x, z)) < L.WATER < deck, "Bridge does not span water")
        ramps[name] = {
            "deck_width_m": round(w, 2),
            "deck_length_m": round(length, 2),
            "max_transition_cm": round(max(ends) * 100, 2),
        }
    return {
        "road_center_samples": samples,
        "roads": results,
        "bridges": ramps,
        "min_marker_clearance_m": round(anchor_min, 2),
    }


def validate(b, scene, manager, h, weights, items):
    sf = single(scene)
    manager_check(b.files["globalgamemanagers"].reader.bytes, manager)
    by = defaultdict(dict)
    seen = Counter()
    refs = 0
    basic = 0

    def ref(fid, pid):
        if not pid:
            return
        if not fid:
            check(pid in sf.objects, "Broken local reference " + str(pid))
            return
        check(0 < fid <= len(sf.externals), "Bad external index")
        name = sf.externals[fid - 1].path
        if name.lower() in [
            "library/unity default resources",
            "resources/unity_builtin_extra",
        ]:
            return
        check(name in b.files and pid in b.files[name].objects, f"Missing {name}#{pid}")

    for pid, o in sf.objects.items():
        typ = o.type.name
        seen[typ] += 1
        if typ == "Light":
            raw = o.get_raw_data()
            don = b.files["level11"].objects[148730].get_raw_data()
            check(raw[12:] == don[12:], "Modified light settings")
            fid, g = struct.unpack_from("<iq", raw)
            ref(fid, g)
            d = {"m_GameObject": {"m_FileID": fid, "m_PathID": g}}
        elif typ == "LightmapSettings":
            raw = o.get_raw_data()
            don = next(
                q for q in b.files["level11"].objects.values() if q.type.name == typ
            )
            check(
                raw == don.get_raw_data() and len(raw) == 76, "Modified field lighting"
            )
            fid, p = struct.unpack_from("<iq", raw, 64)
            ref(fid, p)
            check(
                b.files[sf.externals[fid - 1].path].objects[p].type.name
                == "LightingSettings",
                "Wrong lighting settings",
            )
            continue
        else:
            d = parse_complete(o)
        for f, p in pointers(d):
            if p:
                ref(f, p)
                refs += 1
                basic += bool(
                    f and sf.externals[f - 1].path.lower().startswith("library/")
                )
        by[typ][pid] = d
    gos = by["GameObject"]
    trs = by["Transform"]
    named = {x["m_Name"]: p for p, x in gos.items()}
    tf = {tr["m_GameObject"]["m_PathID"]: tr for tr in trs.values()}
    owner = {}
    for gid, g in gos.items():
        check(gid in tf and g["m_IsActive"], "Inactive or transformless node")
        for entry in g["m_Component"]:
            cid = entry["component"]["m_PathID"]
            check(
                cid not in owner
                and by[sf.objects[cid].type.name][cid]["m_GameObject"]["m_PathID"]
                == gid,
                "Component owner mismatch",
            )
            owner[cid] = gid
        tr = tf[gid]
        trid = g["m_Component"][0]["component"]["m_PathID"]
        check(trid in trs, "Transform not first")
        if parent := tr["m_Father"]["m_PathID"]:
            check(
                {"m_FileID": 0, "m_PathID": trid} in trs[parent]["m_Children"],
                "Broken parent link",
            )
        for c in tr["m_Children"]:
            check(
                trs[c["m_PathID"]]["m_Father"]["m_PathID"] == trid, "Broken child link"
            )
    for g, t in tf.items():
        parent = t["m_Father"]["m_PathID"]
        visited = set()
        while parent:
            check(parent not in visited, "Hierarchy cycle")
            visited.add(parent)
            parent = trs[parent]["m_Father"]["m_PathID"]
    for ld in by["LODGroup"].values():
        prev = 1.0
        gid = ld["m_GameObject"]["m_PathID"]
        for level in ld["m_LODs"]:
            threshold = level["screenRelativeHeight"]
            check(0 < threshold < prev, "Unordered LOD thresholds")
            prev = threshold
            for rr in level["renderers"]:
                rid = rr["renderer"]["m_PathID"]
                check(
                    rid in by["MeshRenderer"]
                    and trs[tf[owner[rid]]["m_Father"]["m_PathID"]]["m_GameObject"][
                        "m_PathID"
                    ]
                    == gid,
                    "LOD renderer outside group",
                )
    check(
        len(by["Terrain"]) == len(by["TerrainCollider"]) == len(by["TerrainData"]) == 1,
        "Terrain object count",
    )
    tr = next(iter(by["Terrain"].values()))
    co = next(iter(by["TerrainCollider"].values()))
    check(
        tr["m_Enabled"]
        and co["m_Enabled"]
        and tr["m_TerrainData"] == co["m_TerrainData"]
        and tr["m_GameObject"] == co["m_GameObject"],
        "Terrain collider binding",
    )
    td = by["TerrainData"][tr["m_TerrainData"]["m_PathID"]]
    hm = td["m_Heightmap"]
    sh = hm["m_Resolution"]
    hh = np.array(hm["m_Heights"], dtype="<u2").reshape(sh, sh)
    check(np.array_equal(hh, h), "Terrain height readback mismatch")
    scale = hm["m_Scale"]
    check(
        (sh - 1) * scale["x"] == L.SIZE
        and scale["z"] == scale["x"]
        and scale["y"] == 64,
        "Wrong dimensions",
    )
    sp = td["m_SplatDatabase"]
    tx = by["Texture2D"][sp["m_AlphaTextures"][0]["m_PathID"]]
    w = np.frombuffer(
        tx["image data"], dtype=np.uint8, count=tx["m_Width"] * tx["m_Height"] * 4
    ).reshape(tx["m_Height"], tx["m_Width"], 4)
    check(
        len(sp["m_TerrainLayers"]) == 4
        and np.array_equal(w, weights)
        and np.all(w.sum(axis=2) == 255),
        "Invalid terrain painting",
    )
    previous = w
    cursor = w.nbytes
    for _ in range(1, tx["m_MipCount"]):
        height, width, _channels = previous.shape
        mip = np.frombuffer(
            tx["image data"], offset=cursor, dtype=np.uint8, count=height * width
        ).reshape(height // 2, width // 2, 4)
        exact = (
            previous.astype(np.int32)
            .reshape(height // 2, 2, width // 2, 2, 4)
            .mean(axis=(1, 3))
        )
        check(
            np.all(mip.sum(axis=2) == 255) and np.all(np.abs(mip - exact) < 1),
            "Invalid distant terrain paint",
        )
        cursor += mip.nbytes
        previous = mip
    check(
        previous.shape == (1, 1, 4) and cursor == len(tx["image data"]),
        "Incomplete terrain texture mip chain",
    )
    solids = []
    bridges = {}
    wall_count = 0
    for o in by["BoxCollider"].values():
        check(o["m_Enabled"] and not o["m_IsTrigger"], "Non-solid collider")
        gid = o["m_GameObject"]["m_PathID"]
        g = gos[gid]
        t = tf[gid]
        p = t["m_LocalPosition"]
        r = t["m_LocalRotation"]
        sc = t["m_LocalScale"]["x"]
        cen = o["m_Center"]
        size = o["m_Size"]
        layer = g["m_Layer"]
        name = g["m_Name"]
        c = 1 - 2 * r["y"] ** 2
        s = 2 * r["y"] * r["w"]
        if layer == 20:
            wall_count += 1
            continue
        if layer == 8 and size["z"] > 2 and "bridge_" in name:
            bridges[name.rsplit("_", 1)[0]] = (
                p["x"],
                p["z"],
                size["x"],
                size["z"],
                p["y"] + cen["y"] + size["y"] / 2,
            )
            continue
        if layer != 17:
            continue
        solids.append(
            (
                p["x"] + sc * (c * cen["x"] + s * cen["z"]),
                p["z"] + sc * (-s * cen["x"] + c * cen["z"]),
                c,
                s,
                size["x"] * sc / 2,
                size["z"] * sc / 2,
            )
        )
    check(
        wall_count == 4 and set(bridges) == {row[0] for row in L.BRIDGES},
        "Walls or decks missing",
    )
    at = tf[named["Mission Anchors"]]
    anchor = {}
    for entry in at["m_Children"]:
        t = trs[entry["m_PathID"]]
        n = gos[t["m_GameObject"]["m_PathID"]]["m_Name"]
        p = t["m_LocalPosition"]
        anchor[n] = (p["x"], p["z"])
        expected = bridges[n][-1] if n in bridges else L.ground(hh, p["x"], p["z"])
        check(abs(float(expected) - p["y"]) < 0.002, "Incorrect anchor height")
    check(anchor == L.ANCHORS, "Anchor registry mismatch")
    check(
        len(items) == len(by["LODGroup"])
        and all(f"{v['kind']}_{i:04}" in named for i, v in enumerate(items)),
        "Scenery placement mismatch",
    )
    check(
        not by["MonoBehaviour"] and seen["Camera"] == 1,
        "Unexpected gameplay controller or camera",
    )
    return dict(
        unity_version=sf.unity_version,
        scene_index=21,
        unchanged_existing_scene_indices=21,
        scene_objects=len(sf.objects),
        resolved_nonnull_references=refs,
        builtin_engine_references=basic,
        scenery_instances=len(items),
        lod_groups=len(by["LODGroup"]),
        solid_boxes=len(by["BoxCollider"]),
        height_samples=sh,
        control_texture=[tx["m_Width"], tx["m_Height"]],
        terrain_layers=4,
        verified_weight_mips=tx["m_MipCount"],
        mission_anchors=len(anchor),
        **road_checks(hh, solids, anchor, bridges),
    )
