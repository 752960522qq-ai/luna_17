"""Read the emitted SerializedFile again, independently of the writer's object cache."""

import io
import json
import struct
from collections import defaultdict

import numpy as np
import UnityPy
from PIL import Image

from .enemy_assets import refs, script_class, subtree
from .serialization import apply_reviewed_typetrees, parse_complete
from .unity_assets import SCHEMA, pp, read_mb


def verify(a, file, entry, model=None):
    env = UnityPy.load(str(file))
    apply_reviewed_typetrees(env)
    sf = next(iter(env.files.values()))
    root = entry["root_path_id"]
    ids = sf.objects
    oldmax = max(a.sf.objects)

    def require(cond, message):
        if not cond:
            raise ValueError(f"{file.name}: {message}")

    def tree(pid):
        return parse_complete(ids[pid])

    def mb(pid, kind):
        return read_mb(kind, ids[pid].get_raw_data())

    def single(xs):
        xs = list(xs)
        require(len(xs) == 1, "expected one reference")
        return xs[0]

    def components(go):
        return [r["component"]["m_PathID"] for r in tree(go)["m_Component"]]

    def transform(go):
        return single(p for p in components(go) if ids[p].type.name == "Transform")

    def parent(tr):
        return tree(tr)["m_Father"]["m_PathID"]

    require(sf.unity_version == "6000.3.19f1" and tree(root)["m_Name"] == entry["prefab"], "root/version")
    require(
        tree(root)["m_IsActive"] and tree(transform(root))["m_Father"] == pp(),
        "root is not an instantiable template",
    )
    cls = defaultdict(list)
    reachable = set()
    owned_nodes = list(subtree(sf, root))
    local = external = engine = 0
    for go, ps, tr in owned_nodes:
        reachable.update([go, *ps])
        require(len(ps) == len(set(ps)), "component listed twice")
        for p in ps:
            o = ids[p]
            if o.type.name == "MonoBehaviour":
                require(struct.unpack_from("<iq", o.get_raw_data()) == (0, go), "script owner")
                cls[script_class(a, o)].append(p)
            else:
                require(tree(p)["m_GameObject"] == pp(go), "native component owner")
        for ref in tree(tr)["m_Children"]:
            require(tree(ref["m_PathID"])["m_Father"] == pp(tr), "parent/child mismatch")
    for c in (
        "AIControl",
        "DriverControl",
        "UnitStatus",
        "UnitMove",
        "BodyMove",
        "TurretMove",
        "Launcher",
    ):
        single(cls[c])
    require(not cls["PlayerControl"], "unexpected player controller")
    for c in ("AIControl", "DriverControl"):
        p = cls[c][0]
        require(ids[p].get_raw_data() == a.sf.objects[p].get_raw_data(), c + " template bytes changed")

    def check(p):
        nonlocal local, external, engine
        i = p["m_PathID"]
        f = p["m_FileID"]
        if not i:
            return p
        if not f:
            require(i in ids, f"dangling local reference {i}")
            local += 1
        else:
            require(0 < f <= len(sf.externals), "invalid external file ID")
            target = sf.externals[f - 1].path
            if target in a.files:
                require(i in a.files[target].objects, f"missing stock dependency {target}:{i}")
                external += 1
            else:
                require(
                    target in ("Resources/unity_builtin_extra", "Library/unity default resources"),
                    "unknown engine dependency " + target,
                )
                engine += 1
        return p

    for p, o in ids.items():
        if o.type.name == "MonoBehaviour":
            c = script_class(a, o)
            raw = o.get_raw_data()
            for offset in (0, 16):
                f, i = struct.unpack_from("<iq", raw, offset)
                check(pp(i, f))
            if c in SCHEMA:
                refs(mb(p, c), check)
            else:
                # Original path IDs live unchanged inside each file. Check every possible stock PPtr in opaque fields.
                for off in range(32, len(raw) - 11, 4):
                    f, i = struct.unpack_from("<iq", raw, off)
                    if f == 0 and i and i in a.sf.objects:
                        require(i in ids, "unresolved opaque local reference")
        else:
            refs(tree(p), check)
    for ref in sf.script_types:
        check(pp(ref.local_identifier_in_file, ref.local_serialized_file_index))
    st = mb(cls["UnitStatus"][0], "UnitStatus")
    l = mb(cls["Launcher"][0], "Launcher")
    b = mb(cls["BodyMove"][0], "BodyMove")
    tm = mb(cls["TurretMove"][0], "TurretMove")
    ctrl = entry["model_control_path_ids"]
    primary = entry["primary_shell"]
    weapon = entry["gameplay"]["weapon"]
    ammo = weapon["ammo"]
    shell = 0 if primary == "AP" else 1
    from .unity_assets import NATIONS

    require(
        st["iFFNum"] == 2
        and st["unitName"] == entry["id"]
        and st["unitNation"] == NATIONS.index(entry["country"]),
        "enemy identity",
    )
    require(
        st["usingShell"] == st["loadedShell"] == shell
        and l["calibre"] == weapon["caliber"]
        and l["initSpeed"] == weapon["muzzleVelocity"]
        and l["attackPower"] == weapon["shells"][primary]["penetrationMm"],
        "primary ammunition",
    )
    if entry["vehicle_kind"] != "tank":
        require(
            st["angleOfRightAndLeft"] == entry["gameplay"]["tank"]["gunTraverseHalfAngle"],
            "limited traverse",
        )
    alltr = {tr for _, _, tr in owned_nodes}

    def ancestor(tr, target):
        while tr and tr != target:
            tr = parent(tr)
        return tr == target

    require(
        all(x in alltr for x in ctrl.values())
        and ancestor(ctrl["yaw"], ctrl["hull"])
        and ancestor(ctrl["pitch"], ctrl["yaw"])
        and ancestor(ctrl["recoil"], ctrl["pitch"]),
        "model pivots",
    )
    require(
        tm["thisTrf"] == pp(ctrl["yaw"])
        and tm["gunTrfs"] == [pp(ctrl["pitch"])]
        and l["barrelTrf"] == pp(ctrl["recoil"]),
        "turret/gun/recoil control",
    )
    fire = l["thisTrf"]["m_PathID"]
    require(parent(fire) == ctrl["pitch"], "shot follows recoil / wrong mount")
    require(l["uStatus"] == pp(cls["UnitStatus"][0]), "launcher ownership")
    hull_or_turret_boxes = {
        p
        for g in (root, tree(ctrl["yaw"])["m_GameObject"]["m_PathID"])
        for p in components(g)
        if ids[p].type.name == "BoxCollider"
    }
    stock_exclusions = set()
    for shot in l["shellApGos"]:
        g = shot["m_PathID"]
        sm = single(
            p
            for p in components(g)
            if ids[p].type.name == "MonoBehaviour" and script_class(a, ids[p]) == "ShellMove"
        )
        stock_exclusions.add(struct.unpack_from("<iq", a.sf.objects[sm].get_raw_data(), 92))
    for kind, field in [("AP", "shellApGos"), ("HE", "shellHeGos")]:
        if ammo.get(kind):
            require(bool(l[field]), kind + " pool empty")
        for shot in l[field]:
            g = shot["m_PathID"]
            require(g in reachable, "shared projectile instead of local pool")
            sm = single(
                p
                for p in components(g)
                if ids[p].type.name == "MonoBehaviour" and script_class(a, ids[p]) == "ShellMove"
            )
            raw = ids[sm].get_raw_data()
            require(
                struct.unpack_from("<iq", raw, 44) == (0, fire)
                and struct.unpack_from("<iq", raw, 92) in stock_exclusions
                and struct.unpack_from("<iq", raw, 92)[1] in hull_or_turret_boxes,
                "projectile mount/owner collider",
            )
    require(
        len(b["largeWheelLodTrfs"]) == len(b["susWheelTrfs"]) == entry["road_wheels"], "suspension count"
    )
    for wh, sp in zip(b["largeWheelLodTrfs"], b["susWheelTrfs"]):
        require(parent(wh["m_PathID"]) == sp["m_PathID"] and wh["m_PathID"] in alltr, "unbound wheel")
    tracks = [r["m_PathID"] for r in b["scrollLodRends"]]
    require(len(tracks) == len(set(tracks)) == 2, "missing or shared track renderer")
    require(
        len({tree(r)["m_Materials"][0]["m_PathID"] for r in tracks}) == 2,
        "track sides share scroll material",
    )
    tris = meshes = textures = 0
    meta = tree(entry["profile_path_id"])
    profile = json.loads(meta["m_Script"])
    require(
        meta["m_Name"] == entry["id"] + "_EnemyProfile"
        and profile["hatch_id"] == entry["id"]
        and profile["role"] == "enemy"
        and profile["gameplay"] == entry["gameplay"],
        "embedded vehicle profile",
    )
    for p, o in ids.items():
        if p <= oldmax:
            continue
        if o.type.name == "Mesh":
            t = tree(p)
            v = t["m_VertexData"]
            n = v["m_VertexCount"]
            ix = np.frombuffer(bytes(t["m_IndexBuffer"]), "<u4" if t["m_IndexFormat"] else "<u2")
            verts = np.frombuffer(bytes(v["m_DataSize"]), "<f4").reshape(-1, 8)
            require(
                len(verts) == n and len(ix) % 3 == 0 and int(ix.max()) < n and np.isfinite(verts).all(),
                "invalid geometry",
            )
            tris += len(ix) // 3
            meshes += 1
            if model:
                ns, _images, h = model
                i = int(t["m_Name"][len(entry["id"]) + 1 :].split("_")[0])
                srcs = (
                    [j for j, s in enumerate(ns) if s.parent == i and len(s.indices)]
                    if ns[i].flags & 64
                    else [i]
                )
                off = 0
                at = 0
                for j in srcs:
                    sn = ns[j]
                    vs = verts[off : off + len(sn.vertices)]
                    require(
                        np.array_equal(vs[:, :7], sn.vertices[:, :7])
                        and np.array_equal(
                            vs[:, 7],
                            sn.vertices[:, 7]
                            if h.get("texture_uv_convention", "").lower().startswith("unity")
                            else 1.0 - sn.vertices[:, 7],
                        ),
                        "model or UV changed",
                    )
                    require(
                        np.array_equal(ix[at : at + len(sn.indices)], sn.indices + off),
                        "source triangles changed",
                    )
                    off += len(vs)
                    at += len(sn.indices)
                require(off == n and at == len(ix), "extra geometry")
        elif o.type.name == "Texture2D":
            t = tree(p)
            raw = bytes(t["image data"])
            textures += 1
            require(
                len(raw) == t["m_Width"] * t["m_Height"] * 4 and not t["m_StreamData"]["size"],
                "texture storage",
            )
            if model:
                i = int(t["m_Name"].split("_tex")[-1].split("_")[0])
                with Image.open(io.BytesIO(model[1][i])) as im:
                    require(
                        raw == im.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes(),
                        "source texture pixels changed",
                    )
        elif o.type.name == "MeshRenderer":
            rt = tree(p)
            require(p in reachable and rt["m_Enabled"], "lost model renderer")
            if model:
                go = rt["m_GameObject"]["m_PathID"]
                mf = single(c for c in components(go) if ids[c].type.name == "MeshFilter")
                mesh = tree(tree(mf)["m_Mesh"]["m_PathID"])
                i = int(mesh["m_Name"][len(entry["id"]) + 1 :].split("_")[0])
                sn = model[0][i]
                if sn.flags & 64:
                    sn = next(n for n in model[0] if n.parent == i and len(n.indices))
                mat = tree(single(rt["m_Materials"])["m_PathID"])
                props = mat["m_SavedProperties"]
                envs = dict(props["m_TexEnvs"])
                tint = dict(props["m_Colors"])["_Color"]
                require(tuple(tint[k] for k in "rgba") == sn.tint, "wrong material tint")
                for key, idx, suffix in [
                    ("_MainTex", sn.images[0], ""),
                    ("_BumpMap", sn.images[1], "_n"),
                ]:
                    ref = envs[key]["m_Texture"]
                    require(
                        ref["m_FileID"] == 0
                        and (
                            ref["m_PathID"] == 0
                            if idx < 0
                            else tree(ref["m_PathID"])["m_Name"] == f"{entry['id']}_tex{idx}{suffix}"
                        ),
                        "wrong texture on " + mesh["m_Name"],
                    )
    require(
        meshes == entry["visual_renderers"] and tris == entry["model_triangles"] and textures > 0,
        "incomplete model",
    )
    return {
        "checked": "reopened serialized file",
        "game_objects": len(owned_nodes),
        "ai_control": 1,
        "player_control": 0,
        "triangles": tris,
        "textures": textures,
        "he_pool": len(l["shellHeGos"]),
        "ap_pool": len(l["shellApGos"]),
        "local_references": local,
        "stock_references": external,
        "builtin_references": engine,
        "device_test": False,
    }
