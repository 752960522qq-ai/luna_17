"""Extend the verified BT-7/campaign data without displacing previous Resources paths or Hatch mods."""

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from ..barbarossa.bundle import append_members, metadata
from ..bt7.integrate import check, one_file, reg, reg_object
from ..bt7.prefab import writej
from ..enemy_prefabs import BASE_SHA, one, sha
from ..serialization import parse_complete
from ..unity_assets import Adapter
from .source import ID


def digest(b):
    return hashlib.sha256(b).hexdigest()


def build(
    apk,
    base,
    previous,
    player,
    ai_dir,
    out,
    vehicle=ID,
    previous_id="BT7",
    stem="PanzerII-F.overlay",
):
    out.mkdir(parents=True, exist_ok=True)
    raw = base.read_bytes()
    check(digest(raw) == BASE_SHA, "Unknown stock resources")
    a = Adapter(base)
    idx = json.loads((ai_dir / "Hatch-Enemy-AI-index.json").read_text())
    e = one((x for x in idx["prefabs"] if x["id"] == vehicle), vehicle)
    ai = ai_dir / e["file"]
    check(sha(ai) == e["sha256"], "Enemy asset mismatch")
    with zipfile.ZipFile(previous) as z:
        spec = json.loads(z.read("integration.json"))
        old_delta = z.read(spec.get("overlay_file", "BT7.overlay"))
        old_idx = json.loads(z.read("AI/Hatch-Enemy-AI-index.json"))
        old_catalog = json.loads(z.read("assets/Hatch/catalog.json"))
        old_players = {
            p: z.read(p)
            for p in z.namelist()
            if p.startswith("assets/Hatch/mods/") and p.endswith(".hatch")
        }
        check(
            old_idx["prefabs"] == idx["prefabs"][:-1]
            and old_idx["prefabs"][-1]["id"] == previous_id,
            "Previous AI index was not preserved",
        )
        check(
            spec["base_sha256"] == BASE_SHA
            and digest(old_delta) == spec["overlay_sha256"]
            and spec["menu_merged"]
            and spec["campaign_merged"],
            "Wrong prior integration",
        )
        hd = spec["header_bytes"]
        prior = (
            old_delta[:hd]
            + raw[spec["retain_start"] : spec["retain_end"]]
            + old_delta[hd:]
        )
        check(digest(prior) == spec["result_sha256"], "Previous build corrupted")
    with zipfile.ZipFile(apk) as z:
        check(sha(apk) == idx["source_apk_sha256"], "Wrong Hatch APK")
        stock = json.loads(z.read("assets/Hatch/catalog.json"))
        extra = old_catalog["mods"][len(stock["mods"]) :]
        check(
            old_catalog["mods"][: len(stock["mods"])] == stock["mods"]
            and extra[-1]["id"] == previous_id,
            "Previous player catalog changed",
        )
        paths = {"assets/Hatch/mods/" + v["id"] + ".hatch": v for v in extra}
        check(
            paths.keys() == old_players.keys()
            and all(
                digest(old_players[p]) == v["sha256"]
                and len(old_players[p]) == v["size"]
                for p, v in paths.items()
            ),
            "Player package mismatch",
        )
        luchs = "assets/Hatch/mods/Panzer_II_Ausf_L.hatch"
        import io

        with zipfile.ZipFile(io.BytesIO(z.read(luchs))) as l:
            lm = json.loads(l.read("hatch.json"))
    with zipfile.ZipFile(player) as z:
        h = json.loads(z.read("hatch.json"))
        weapon = json.loads(z.read("weapon.json"))
        check(
            h["id"] == vehicle and h["runtime_sha256"] == e["runtime_sha256"],
            "Player and enemy models differ",
        )
        if vehicle == ID:
            check(
                h["continuous_fire"] is lm["continuous_fire"] is True
                and h["magazine"] == lm["magazine"] == weapon["magazine"],
                "Released Luchs cannon mode differs",
            )
        else:
            check(
                not h.get("continuous_fire")
                and "magazine" not in h
                and not weapon.get("continuousFire")
                and weapon["reload"] == 5.0,
                "Single-shot configuration lost",
            )
        check(e["gameplay"]["weapon"] == weapon, "AI/player weapon mismatch")
    prev = one_file(prior)
    manager = prev.files["globalgamemanagers"]
    original_keys = dict(parse_complete(reg_object(manager))["m_Container"])
    updated, report = reg(a, manager.reader.bytes, ai, e)
    merged = append_members(
        prior,
        [("globalgamemanagers", updated), (ai.name, ai.read_bytes())],
        {ai.name: "resources.assets"},
    )
    pack = one_file(merged)
    new = pack.files["globalgamemanagers"]
    keys = dict(parse_complete(reg_object(new))["m_Container"])
    check(
        {k: keys[k] for k in original_keys} == original_keys,
        "Prior Resources key changed",
    )
    newly_registered = [
        q for q in idx["prefabs"] if q["id"] in {v["id"] for v in extra} | {vehicle}
    ]
    for obj in newly_registered:
        pk = keys[obj["resource_path"]]
        pf = keys[obj["profile_resource_path"]]
        target = pack.files[new.externals[pk["m_FileID"] - 1].path]
        check(
            target.name == obj["file"]
            and parse_complete(target.objects[pk["m_PathID"]])["m_Name"]
            == obj["prefab"],
            "Wrong Resources root",
        )
        check(pf["m_FileID"] == pk["m_FileID"], "Wrong profile file")
        profile = json.loads(parse_complete(target.objects[pf["m_PathID"]])["m_Script"])
        check(
            profile["hatch_id"] == obj["id"]
            and profile["runtime_sha256"] == obj["runtime_sha256"],
            "Wrong profile/model",
        )
        if obj["id"] == vehicle and vehicle != ID:
            check(
                profile["continuous_fire"] is False
                and profile["magazine"] is None
                and profile["gameplay"]["weapon"] == weapon,
                "Single-shot AI profile mismatch",
            )
        if obj["id"] == ID:
            check(
                profile["continuous_fire"] is True
                and profile["magazine"] == lm["magazine"],
                "AI magazine profile mismatch",
            )
    _, s, end, blocks, orig = metadata(raw)
    _, p0, p1, prevblocks, oldmembers = metadata(prior)
    _, s2, _, full, members = metadata(merged)
    check(
        prevblocks == full[: len(prevblocks)]
        and prior[p0:p1] == merged[s2 : s2 + p1 - p0]
        and blocks == full[: len(blocks)]
        and raw[s:end] == merged[s2 : s2 + end - s],
        "Compressed payload changed",
    )
    check(
        members.keys() == oldmembers.keys() | {ai.name}
        and all(
            row == members[n]
            for n, row in oldmembers.items()
            if n != "globalgamemanagers"
        ),
        "An existing native member moved",
    )
    check(
        pack.files[ai.name].reader.bytes == ai.read_bytes(),
        "AI bytes differ after loading",
    )
    for n in ["level0", "level21"] + [
        q["file"] for q in newly_registered if q["id"] != vehicle
    ]:
        check(
            pack.files[n].reader.bytes == prev.files[n].reader.bytes,
            "Existing resource changed: " + n,
        )
    patch = merged[:s2] + merged[s2 + end - s :]
    (out / stem).write_bytes(patch)
    report.update(
        {
            "format": 1,
            "base_sha256": BASE_SHA,
            "result_sha256": digest(merged),
            "overlay_sha256": digest(patch),
            "overlay_file": stem,
            "header_bytes": s2,
            "retain_start": s,
            "retain_end": end,
            "prior_result_sha256": spec["result_sha256"],
            "original_compressed_blocks_preserved": len(blocks),
            "original_unmodified_members": len(
                orig.keys() - {"globalgamemanagers", "level0"}
            ),
            "menu_merged": True,
            "campaign_merged": True,
            "prior_vehicle_verified": previous_id,
            "preserved_player_additions": [e["id"] for e in extra],
            "enemy_registry_count": len(idx["prefabs"]),
            "magazine_matches_released_luchs": any(
                q["id"] == ID for q in newly_registered
            ),
            "single_shot": not h.get("continuous_fire"),
            "android_device_test": False,
        }
    )
    writej(out / "integration.json", report)
    directory = out / "assets/Hatch"
    (directory / "mods").mkdir(parents=True, exist_ok=True)
    check(vehicle not in {x["id"] for x in old_catalog["mods"]}, "Player id collision")
    old_catalog["mods"].append(
        {
            "id": vehicle,
            "name": h["name"],
            "sha256": sha(player),
            "size": player.stat().st_size,
        }
    )
    writej(directory / "catalog.json", old_catalog)
    for name, content in old_players.items():
        (out / name).write_bytes(content)
    shutil.copyfile(player, directory / "mods" / player.name)
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "bt7/apply_overlay.py",
        out / "apply_overlay.py",
    )
    return report


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    for n in ("apk", "base", "previous", "player", "ai-dir", "out"):
        c.add_argument("--" + n, required=True, type=Path)
    print(json.dumps(build(**vars(c.parse_args())), indent=2))
