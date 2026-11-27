"""Register the player in Hatch and enemy in Unity Resources. Build an additive data overlay; no signed app is modified."""

import argparse
import copy
import hashlib
import json
import shutil
import struct
import zipfile
from pathlib import Path

import UnityPy

from ..barbarossa.bundle import append_members, metadata
from ..enemy_assets import script_class
from ..enemy_prefabs import BASE_SHA, one, sha
from ..serialization import (
    apply_reviewed_typetrees,
    assert_roundtrip,
    encode_complete,
    parse_complete,
)
from ..unity_assets import SCHEMA, Adapter, pp, read_mb
from .prefab import writej


def check(test, why):
    if not test:
        raise ValueError(why)


def pointers(t):
    if isinstance(t, dict):
        if t.keys() == {"m_FileID", "m_PathID"}:
            if t["m_PathID"]:
                yield t["m_FileID"], t["m_PathID"]
        else:
            for v in t.values():
                yield from pointers(v)
    elif isinstance(t, (tuple, list)) and t and not isinstance(t[0], (int, float)):
        for v in t:
            yield from pointers(v)


def reg_object(sf):
    return one(
        (o for o in sf.objects.values() if o.type.name == "ResourceManager"),
        "ResourceManager",
    )


def one_file(raw):
    return next(iter(UnityPy.load(raw).files.values()))


def reg(a, manager, asset, entry):
    mg = one_file(manager)
    obj = reg_object(mg)
    tree = assert_roundtrip(obj)
    env = UnityPy.load(str(asset))
    apply_reviewed_typetrees(env)
    sf = next(iter(env.files.values()))
    k = entry["resource_path"]
    pk = entry["profile_resource_path"]
    root = entry["root_path_id"]
    oldkeys = dict(tree["m_Container"])
    check(not {k, pk}.intersection(oldkeys), "Resource key collision")
    names = {e.path: i for i, e in enumerate(mg.externals, 1)}
    stock = names["resources.assets"]
    check(asset.name not in names, "File ID collision")
    tpl = copy.copy(mg.externals[stock - 1])
    tpl.path = asset.name
    mg.externals.append(tpl)
    me = len(mg.externals)
    names[asset.name] = me

    def native_file(e):
        if e.path not in names:
            mg.externals.append(copy.copy(e))
            names[e.path] = len(mg.externals)
        return names[e.path]

    def resolved(f, p):
        return (native_file(sf.externals[f - 1]) if f else me, p)

    donor = {
        r["m_Object"]["m_PathID"]: r["m_Dependencies"]
        for r in tree["m_DependentAssets"]
        if r["m_Object"]["m_FileID"] == stock
    }
    before = len(tree["m_DependentAssets"])
    edges = 0
    for pid, o in sorted(sf.objects.items()):
        deps = set()
        if o.type.name == "MonoBehaviour":
            raw = o.get_raw_data()
            cls = script_class(a, o)
            for off in (0, 16):
                f, p = struct.unpack_from("<iq", raw, off)
                if p:
                    deps.add(resolved(f, p))
            if cls in SCHEMA:
                deps.update(resolved(f, p) for f, p in pointers(read_mb(cls, raw)))
            else:
                # The cloned script keeps native serialized data. Adopt only its real stock dependency entries.
                # Remap owned objects to this prefab, leave shared scripts/sounds/effects with their original files.
                for d in donor.get(pid, []):
                    f, p = d["m_FileID"], d["m_PathID"]
                    deps.add((me if f == stock and p in sf.objects else f, p))
        else:
            deps.update(resolved(f, p) for f, p in pointers(parse_complete(o)))
        deps.discard((me, pid))
        check(
            all(p in sf.objects for f, p in deps if f == me),
            "Dangling registered dependency",
        )
        edges += len(deps)
        if deps:
            tree["m_DependentAssets"].append(
                {
                    "m_Object": pp(pid, me),
                    "m_Dependencies": [pp(p, f) for f, p in sorted(deps)],
                }
            )
    # Test the manager's dependency list, separately from native PPtrs inside the prefab:
    # e.g. material textures sit inside (string, TexEnv) pairs.
    graph = {
        r["m_Object"]["m_PathID"]: [
            d["m_PathID"] for d in r["m_Dependencies"] if d["m_FileID"] == me
        ]
        for r in tree["m_DependentAssets"][before:]
    }
    reachable = set()
    todo = [root]
    while todo:
        cur = todo.pop()
        if cur not in reachable:
            reachable.add(cur)
            todo.extend(graph.get(cur, []))
    original_max = max(a.sf.objects)
    art = {
        p
        for p, o in sf.objects.items()
        if p > original_max
        and o.type.name in ("Material", "Mesh", "MeshRenderer", "Texture2D")
    }
    check(art <= reachable, "BT-7 art omitted from root preload closure")
    roots = {k: pp(root, me), pk: pp(entry["profile_path_id"], me)}
    tree["m_Container"] = sorted(
        [*tree["m_Container"], *roots.items()], key=lambda x: x[0]
    )
    obj.set_raw_data(encode_complete(obj, tree))
    binary = mg.save()
    again = one_file(binary)
    rt = parse_complete(reg_object(again))
    check(
        dict(rt["m_Container"]) == oldkeys | roots
        and rt["m_DependentAssets"] == tree["m_DependentAssets"],
        "Registry write/read mismatch",
    )
    check(
        all(
            again.objects[i].get_raw_data() == o.get_raw_data()
            for i, o in mg.objects.items()
            if i != obj.path_id
        ),
        "Unrelated manager changed",
    )
    return binary, {
        "registered": roots,
        "registered_dependency_records": len(rt["m_DependentAssets"]) - before,
        "registered_dependency_edges": edges,
        "model_assets_reachable_from_root": len(art),
        "original_resource_keys_preserved": len(oldkeys),
    }


def build(apk, data, hatch, ai_dir, out, campaign=None, menu=None):
    out.mkdir(parents=True, exist_ok=True)
    check(sha(data) == BASE_SHA, "Unrecognized stock UnityFS")
    raw = data.read_bytes()
    a = Adapter(data)
    index = json.loads((ai_dir / "Hatch-Enemy-AI-index.json").read_text())
    e = one((x for x in index["prefabs"] if x["id"] == "BT7"), "BT7 prefab")
    asset = ai_dir / e["file"]
    check(sha(asset) == e["sha256"], "Mismatched prefab file")
    check(index["source_apk_sha256"] == sha(apk), "Use the matching Hatch APK catalog")
    check(not menu or campaign, "The extra menu requires its scene")
    changes = []
    new = {}
    manager = a.files["globalgamemanagers"].reader.bytes
    if campaign:
        from ..barbarossa.native import SCENE_PATH

        manager = (campaign / "globalgamemanagers").read_bytes()
        before = one_file(a.files["globalgamemanagers"].reader.bytes)
        after = one_file(manager)
        objs = {
            i
            for i, o in before.objects.items()
            if o.get_raw_data() != after.objects[i].get_raw_data()
        }
        check(len(objs) == 1, "Campaign changed unrelated managers")
        id = objs.pop()
        check(
            before.objects[id].type.name == "BuildSettings"
            and parse_complete(after.objects[id])["scenes"]
            == [*parse_complete(before.objects[id])["scenes"], SCENE_PATH],
            "Campaign scene list no longer matches",
        )
        changes.append(("level21", (campaign / "level21").read_bytes()))
        new["level21"] = "level20"
    if menu:
        changes.append(("level0", menu.read_bytes()))
    manager, r = reg(a, manager, asset, e)
    changes.extend([("globalgamemanagers", manager), (asset.name, asset.read_bytes())])
    new[asset.name] = "resources.assets"
    merged = append_members(raw, changes, new)
    _, start, end, blocks, old = metadata(raw)
    _, beg, _, now, after = metadata(merged)
    check(
        blocks == now[: len(blocks)]
        and raw[start:end] == merged[beg : beg + end - start],
        "Original payload modified",
    )
    changed = {n for n, _ in changes}
    check(
        set(after) == set(old) | set(new)
        and all(after[k] == v for k, v in old.items() if k not in changed),
        "Original directory changed",
    )
    bundle = one_file(merged)
    check(
        all(bundle.files[k].reader.bytes == v for k, v in changes),
        "UnityFS member readback mismatch",
    )
    source = reg_object(bundle.files["globalgamemanagers"])
    container = dict(parse_complete(source)["m_Container"])
    pr = container[e["resource_path"]]
    prof = container[e["profile_resource_path"]]
    native = bundle.files[
        bundle.files["globalgamemanagers"].externals[pr["m_FileID"] - 1].path
    ]
    check(
        native.name == asset.name
        and parse_complete(native.objects[pr["m_PathID"]])["m_Name"] == "BT7_AI",
        "Resources root does not resolve",
    )
    check(
        json.loads(parse_complete(native.objects[prof["m_PathID"]])["m_Script"])[
            "hatch_id"
        ]
        == "BT7",
        "Resources profile does not resolve",
    )
    # Binary delta holds only the new header and suffix around the byte-identical compressed stock payload.
    head = merged[:beg]
    tail = merged[beg + end - start :]
    (out / "BT7.overlay").write_bytes(head + tail)
    r.update(
        {
            "format": 1,
            "base_sha256": BASE_SHA,
            "result_sha256": hashlib.sha256(merged).hexdigest(),
            "retain_start": start,
            "retain_end": end,
            "header_bytes": len(head),
            "overlay_sha256": sha(out / "BT7.overlay"),
            "original_compressed_blocks_preserved": len(blocks),
            "original_unmodified_members": len(set(old) - changed),
            "read_back": list(changed),
            "campaign_merged": bool(campaign),
            "menu_merged": bool(menu),
            "android_device_test": False,
        }
    )
    r["read_back"].sort()
    writej(out / "integration.json", r)
    with zipfile.ZipFile(apk) as z:
        catalog = json.loads(z.read("assets/Hatch/catalog.json"))
        before = catalog["mods"][:]
        check(not any(x["id"] == "BT7" for x in before), "Player ID collision")
        for item in before:
            # Catalog folders for system modules use their own original file names; identify them by checksum/size.
            paths = [
                f
                for f in z.namelist()
                if f.startswith("assets/Hatch/mods/")
                and f.endswith(".hatch")
                and z.getinfo(f).file_size == item["size"]
            ]
            check(
                any(
                    hashlib.sha256(z.read(f)).hexdigest() == item["sha256"]
                    for f in paths
                ),
                "Existing vehicle or system mod missing: " + item["id"],
            )
    with zipfile.ZipFile(hatch) as z:
        h = json.loads(z.read("hatch.json"))
        check(
            h["runtime_sha256"] == e["runtime_sha256"] and h["id"] == "BT7",
            "Player/AI visual profile mismatch",
        )
    catalog["mods"] = [
        *before,
        {
            "id": "BT7",
            "name": h["name"],
            "sha256": sha(hatch),
            "size": hatch.stat().st_size,
        },
    ]
    d = out / "assets/Hatch"
    (d / "mods").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(hatch, d / "mods/BT7.hatch")
    writej(d / "catalog.json", catalog)
    shutil.copyfile(
        Path(__file__).with_name("apply_overlay.py"), out / "apply_overlay.py"
    )
    return r


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    for n in ("apk", "data", "hatch", "ai-dir", "out", "campaign", "menu"):
        c.add_argument("--" + n, type=Path, required=n not in ("menu", "campaign"))
    a = c.parse_args()
    print(json.dumps(build(**vars(a)), indent=2))
