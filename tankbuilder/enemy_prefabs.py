"""Prepare loose enemy GameObject prefabs for Hatch / Attack on Tank 5.1.0."""

import argparse
import hashlib
import io
import json
import shutil
import struct
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path

import numpy as np

from .enemy_assets import Stage, subtree
from .enemy_visuals import Visuals, local_point, read_model
from .unity_assets import NATIONS, Adapter, pp, xyz

BASE_SHA = "6fa19cbaf5a9daad6c8270ae6b77d0a6a0675ad59c84c15061b5a2b2c8a7a6dd"
DONORS = {
    "Grille": "Brummbar_AI",
    "Matilda_III": "Valentine_AI",
    "Panzer_II_Ausf_L": "Panzer_38t_AI",
    "SU_152": "ISU_122_AI",
    "T26": "T34_76_AI",
    "T30": "T29_AI",
    "T44_100": "T44_AI",
    "T54_1949": "T44_AI",
}
EXTENSION_DONORS = {"BT7": "T34_76_AI", "Panzer_II_Ausf_F": DONORS["Panzer_II_Ausf_L"]}
ALL_DONORS = {**DONORS, **EXTENSION_DONORS}
# HE pool in the stock Soviet KV-2 (152 mm) or US howitzer (105 mm) respectively.
HE_DONOR = {"SU_152": 130334, "T30": 130334, "T44_100": 129981, "T54_1949": 129981}
IDENTITY = (0, 0, 0, 0, 0, 0, 1, 1, 1, 1)


def sha(path):
    with Path(path).open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def one(items, label):
    v = list(items)
    if len(v) != 1:
        raise ValueError(f"Expected exactly one {label} (got {len(v)})")
    return v[0]


def attach_visuals(s, ident, nodes, images, h, rig):
    tm = s.mb(s.parts["TurretMove"][0], "TurretMove")
    yaw = tm["thisTrf"]["m_PathID"]
    # T29 also declares an auxiliary gun pivot. Follow the actual main launcher's ancestry.
    eligible = {ref["m_PathID"] for ref in tm["gunTrfs"] if ref["m_FileID"] == 0}
    pitch = s.fire
    while pitch and pitch not in eligible:
        pitch = s.get(pitch)["m_Father"]["m_PathID"]
    if not pitch:
        raise ValueError("Main weapon has no matching gun pivot")
    tm["gunTrfs"] = [pp(pitch)]
    s.set_mb(s.parts["TurretMove"][0], "TurretMove", tm)
    # Reuse the stock yaw/pitch Transform identities. AIControl, damage and TurretMove keep per-instance refs.
    protected = set()
    b = s.mb(s.parts["BodyMove"][0], "BodyMove")
    protected_go = [s.go(s.fire)] + [
        b[k]["m_PathID"] for k in ("explosionEffectGo", "destroyEffGo") if b[k]["m_PathID"] in s.owned
    ]
    for i in s.parts["MachineGun"]:
        g = struct.unpack_from("<iq", s.sf.objects[i].get_raw_data())[1]
        protected_go.append(s.go(s.get(s.tr(g))["m_Father"]["m_PathID"]))
    for gid in protected_go:
        protected.update(g for g, _, _ in subtree(s.base, gid))
    visibility = []
    for g, parts, _ in s.nodes:
        if g in protected:
            continue
        for p in parts:
            typ = s.sf.objects[p].type.name
            if typ in ("MeshRenderer", "SkinnedMeshRenderer", "LODGroup"):
                t = s.get(p)
                t["m_Enabled"] = False
                if typ == "LODGroup":
                    t["m_LODs"] = []
                if typ == "SkinnedMeshRenderer":
                    t["m_Mesh"] = pp()
                s.put(p, t)
            elif typ == "MeshFilter":
                t = s.get(p)
                t["m_Mesh"] = pp()
                s.put(p, t)
            elif p in s.parts["UnitVisible"] and "LOD0" in s.get(g)["m_Name"]:
                visibility.append((g, p))
    tr = []
    go = []
    root_tr = s.tr(s.root)
    layer = s.get(s.root)["m_Layer"]
    for n in nodes:
        if n.flags & 6:
            nt = yaw if n.flags & 2 else pitch
            ng = s.go(nt)
        else:
            ng, nt = s.node(n.name, layer)
        go.append(ng)
        tr.append(nt)
    for i, n in enumerate(nodes):
        s.attach(tr[i], root_tr if n.parent == -1 else tr[n.parent], n.trs)
    controls = [
        one((i for i, n in enumerate(nodes) if n.flags & flag), f"control {flag}")
        for flag in (1, 2, 4, 8)
    ]
    tracks = [
        one((i for i, n in enumerate(nodes) if n.name == track and n.flags & 64), track)
        for track in rig["tracks"]
    ]
    if len(tracks) != 2:
        raise ValueError("Expected left and right track")
    vis = Visuals(s, images, ident, h)
    rendered = {}
    consumed = set()
    tracks_r = []
    total_tri = 0
    for side, track in enumerate(tracks):
        children = [i for i, n in enumerate(nodes) if n.parent == track and len(n.indices)]
        if not children:
            raise ValueError("Track has no surfaces")
        first = nodes[children[0]]
        if any(
            tuple(nodes[j].trs) != IDENTITY
            or (nodes[j].images, nodes[j].tint) != (first.images, first.tint)
            for j in children
        ):
            raise ValueError("Track submesh needs separate transforms/materials")
        offset = 0
        idx = []
        for j in children:
            idx.append(nodes[j].indices + offset)
            offset += len(nodes[j].vertices)
        mesh = replace(
            first,
            vertices=np.concatenate([nodes[j].vertices for j in children]),
            indices=np.concatenate(idx),
        )
        rr = vis.render(mesh, track, go[track], side)
        tracks_r.append(rr)
        rendered[track] = rr
        consumed.update(children)
        total_tri += len(mesh.indices) // 3
    for i, n in enumerate(nodes):
        if i in consumed or not len(n.indices):
            continue
        rendered[i] = vis.render(n, i, go[i], None)
        total_tri += len(n.indices) // 3
    if total_tri != sum(len(n.indices) // 3 for n in nodes):
        raise ValueError("Lost model geometry")
    # UnitVisible receives renderer callbacks. Move the stock LOD0 observer to a visible hull surface.
    if visibility:

        def hull_surface(i):
            p = i
            while p >= 0:
                if nodes[p].flags & (2 | 16 | 32 | 64 | 512):
                    return False
                if p == controls[0]:
                    return True
                p = nodes[p].parent
            return False

        biggest = max((i for i in rendered if hull_surface(i)), key=lambda i: len(nodes[i].indices))
        newgo = go[biggest]
        oldgo, comp = visibility[0]
        old = s.get(oldgo)
        old["m_Component"] = [p for p in old["m_Component"] if p["component"] != pp(comp)]
        s.put(oldgo, old)
        new = s.get(newgo)
        new["m_Component"].append({"component": pp(comp)})
        s.put(newgo, new)
        raw = bytearray(s.sf.objects[comp].get_raw_data())
        struct.pack_into("<iq", raw, 0, 0, newgo)
        s.sf.objects[comp].set_raw_data(bytes(raw))
    wheels = sorted((w for w in rig["wheels"] if w["roadWheel"]), key=lambda w: w["side"] != "left")
    small = sorted((w for w in rig["wheels"] if not w["roadWheel"]), key=lambda w: w["side"] != "left")
    anchors = []
    for w in wheels:
        i = w["node"]
        n = nodes[i]
        parent = n.parent
        declared = w["suspensionNode"]
        if not n.flags & 16 or not n.flags & (128 if w["side"] == "left" else 256):
            raise ValueError("Wheel side/role mismatch")
        if declared == i and n.flags & 32:
            # Some released models use one transform for travel and wheel rotation.
            # Give the AI suspension its own vertical pivot without changing the rest pose.
            _, anchor = s.node(n.name + "_suspension", layer)
            s.attach(anchor, tr[parent], n.trs[:3] + IDENTITY[3:])
            s.attach(tr[i], anchor, IDENTITY[:3] + n.trs[3:])
        elif parent == declared and nodes[parent].flags & 32:
            anchor = tr[parent]
        else:
            raise ValueError("Suspension and wheel binding disagree")
        anchors.append(anchor)
    b.update(
        partsTransforms=[],
        scrollLodRends=[pp(r) for r in tracks_r],
        largeWheelLodTrfs=[pp(tr[w["node"]]) for w in wheels],
        susWheelTrfs=[pp(i) for i in anchors],
        smallWheelLodTrfs=[pp(tr[w["node"]]) for w in small],
        susMaxAmp=rig["suspension"]["restCompression"],
        gearRatio=1.0,
        CircumferenceRatio=1,
        trackNum=len(wheels) // 2,
        _currentTrack=1,
    )
    s.set_mb(s.parts["BodyMove"][0], "BodyMove", b)
    return tr, controls, tracks_r, len(wheels), len(rendered), total_tri


def create(a, stock, mod, out):
    doc = {
        k: json.loads(mod.read(k + ".json"))
        for k in ("hatch", "manifest", "tank", "armor", "weapon", "rig")
    }
    h, m, t, w, r = (doc[k] for k in ("hatch", "manifest", "tank", "weapon", "rig"))
    ident = h["id"]
    name = ident + "_AI"
    kind = h.get("vehicle_kind", "tank")
    cfg, nodes, images = read_model(mod.read("runtime.bin"), h)
    for i, k in enumerate(("AP", "HEAT", "APCR", "WP", "HE")):
        shell = w["shells"].get(k, {})
        if (cfg[4 + 19 + i], cfg[4 + 25 + i], h["shell_filling_grams"].get(k)) != (
            w["ammo"].get(k, 0),
            shell.get("penetrationMm", 0),
            shell.get("explosiveMassGrams"),
        ):
            raise ValueError(f"{ident}: inconsistent {k} ammunition data")
    s = Stage(
        a, stock[ALL_DONORS[ident]], name + ".assets", HE_DONOR.get(ident) if w["ammo"].get("HE") else None
    )
    g = s.get(s.root)
    g["m_Name"] = name
    s.put(s.root, g)
    tr, cs, tracks, roads, renders, triangles = attach_visuals(s, ident, nodes, images, h, r)
    ap = w["ammo"].get("AP", 0)
    prim = "AP" if ap else "HE"
    shell_index = 0 if ap else 1
    if not w["ammo"].get(prim):
        raise ValueError("No primary stock AI ammunition")
    status = s.parts["UnitStatus"][0]
    st = s.mb(status, "UnitStatus")
    st.update(
        iFFNum=2,
        has2ndGun=False,
        unitName=ident,
        unitNation=NATIONS.index(m["country"]),
        mainGunName=w["name"],
        angleOfElevation=round(t["gunElevation"]),
        angleOfDip=round(abs(t["gunDepression"])),
        weight=t["weightTonnes"],
        usingShell=shell_index,
        loadedShell=shell_index,
        rTrackMoves=[],
        sTrackMeshes=[],
        sTrackMeshFilters=[],
    )
    if kind != "tank":
        st["angleOfRightAndLeft"] = int(t["gunTraverseHalfAngle"])
    s.set_mb(status, "UnitStatus", st)
    launch = s.mb(s.launch, "Launcher")
    launch.update(
        weaponName=w["name"],
        calibre=w["caliber"],
        attackPower=w["shells"][prim]["penetrationMm"],
        initSpeed=w["muzzleVelocity"],
        barrelTrf=pp(tr[cs[3]]),
    )
    s.set_mb(s.launch, "Launcher", launch)
    if w["ammo"].get("HE") and not launch["shellHeGos"]:
        raise ValueError("Missing HE pool")
    muzzle = local_point(nodes, cs[2], r["muzzle"]["position"])
    muzzle[2] += 0.15
    s.attach(s.fire, tr[cs[2]], tuple(muzzle) + IDENTITY[3:])
    for i in s.parts["MachineGun"]:
        g = struct.unpack_from("<iq", s.sf.objects[i].get_raw_data())[1]
        mount = s.get(s.tr(g))["m_Father"]["m_PathID"]
        s.attach(
            mount, tr[cs[2]], tuple(local_point(nodes, cs[2], r["coaxMuzzle"]["position"])) + IDENTITY[3:]
        )
    rb = one(
        (p for p in s.parts["Rigidbody"] if s.get(p)["m_GameObject"] == pp(s.root)), "hull rigidbody"
    )
    b = s.get(rb)
    b["m_Mass"] = t["weightTonnes"] * 1000
    s.put(rb, b)
    for label, g in [
        ("hull", s.root),
        ("turret", s.go(tr[cs[1]])),
        ("unit", struct.unpack_from("<iq", s.sf.objects[status].get_raw_data())[1]),
    ]:
        p = one(
            (p for p in s.parts["BoxCollider"] if s.get(p)["m_GameObject"] == pp(g)), label + " collider"
        )
        b = s.get(p)
        b.update(m_Size=xyz(r["colliders"][label]["size"]), m_Center=xyz(r["colliders"][label]["center"]))
        s.put(p, b)
    gameplay = {k: doc[k] for k in ("tank", "armor", "weapon")}
    profile = {
        "format": 1,
        "role": "enemy",
        "hatch_id": ident,
        "gameplay": gameplay,
        "suspension": r["suspension"],
        "track_uv_period_m": r.get("trackLoopMeters"),
        "runtime_sha256": h["runtime_sha256"],
        "continuous_fire": h.get("continuous_fire", False),
        "magazine": h.get("magazine"),
    }
    profile_id = s.make(
        "TextAsset",
        {
            "m_Name": ident + "_EnemyProfile",
            "m_Script": json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        },
    )
    file = out / (name + ".assets")
    file.write_bytes(s.sf.save())
    return {
        "id": ident,
        "name": h["name"],
        "prefab": name,
        "file": file.name,
        "root_path_id": s.root,
        "stock_ai": ALL_DONORS[ident],
        "country": m["country"],
        "vehicle_kind": kind,
        "primary_shell": prim,
        "road_wheels": roads,
        "track_renderers": tracks,
        "visual_renderers": renders,
        "model_triangles": triangles,
        "runtime_sha256": h["runtime_sha256"],
        "sha256": sha(file),
        "size_bytes": file.stat().st_size,
        "profile_path_id": profile_id,
        "gameplay": gameplay,
        "uv_period_m": r.get("trackLoopMeters"),
        "suspension": r["suspension"],
        "model_control_path_ids": dict(zip(("hull", "yaw", "pitch", "recoil"), (tr[i] for i in cs))),
    }


def prepare(apk, output):
    from .enemy_verify import verify

    with tempfile.TemporaryDirectory(dir=output.parent) as tmp, zipfile.ZipFile(apk) as z:
        work = Path(tmp)
        src = work / "data.unity3d"
        with z.open("assets/bin/Data/data.unity3d") as f, src.open("wb") as dst:
            shutil.copyfileobj(f, dst)
        if sha(src) != BASE_SHA:
            raise ValueError("Base assets differ from reviewed Hatch release")
        a = Adapter(src)
        names = {
            o.read_typetree(check_read=False)["m_Name"]: o.path_id
            for o in a.sf.objects.values()
            if o.type.name == "GameObject"
            and o.read_typetree(check_read=False)["m_Name"] in ALL_DONORS.values()
        }
        entries = []
        seen = set()
        for n in sorted(z.namelist()):
            if not (n.startswith("assets/Hatch/mods/") and n.endswith(".hatch")):
                continue
            with zipfile.ZipFile(io.BytesIO(z.read(n))) as mod:
                h = json.loads(mod.read("hatch.json"))
                if h.get("type") != "tank":
                    continue
                if h["id"] not in ALL_DONORS or h["id"] in seen:
                    raise ValueError("Unknown/duplicate vehicle: " + h["id"])
                seen.add(h["id"])
                print("Preparing", h["id"], flush=True)
                entry = create(a, names, mod, work)
                _, nodes, images = read_model(mod.read("runtime.bin"), h)
                entry["validation"] = verify(a, work / entry["file"], entry, (nodes, images, h))
                entries.append(entry)
        if not set(DONORS) <= seen:
            raise ValueError("Incomplete vehicle catalog")
        index = {
            "format": 1,
            "unity": "6000.3.19f1",
            "game": "Attack on Tank 5.1.0",
            "source_apk_sha256": sha(apk),
            "stock_data_sha256": BASE_SHA,
            "use": "Loose serialized AI GameObject roots. Load with the stock dependencies; use (file,root_path_id) together. No scene/catalog registration or APK assembly.",
            "prefabs": entries,
        }
        (work / "Hatch-Enemy-AI-index.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False) + "\n"
        )
        output.mkdir(parents=True, exist_ok=True)
        for n in [e["file"] for e in entries] + ["Hatch-Enemy-AI-index.json"]:
            (work / n).replace(output / n)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apk", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    prepare(args.apk, args.output)
