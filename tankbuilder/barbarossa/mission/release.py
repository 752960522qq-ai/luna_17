"""Build the mission from the previous cumulative release and the original game using repository tools."""

import argparse, hashlib, io, json, zipfile
from pathlib import Path
from types import SimpleNamespace
import lz4.block
from ...extra_campaign import file, ARCHIVE_PATH, DIGESTS, prepare as prepare_menu_base
from ...enemy_prefabs import create, BASE_SHA
from ...serialization import parse_complete, encode_complete
from ...campaign_ugui import require
from .. import layout
from ..bundle import append_members, metadata
from . import TITLE, SIDES, SOVIET, OBJECTIVE_XZ
from .interface import menu
from .buildscene import make
from .roster import stage, perspective

PRIOR = "ac1a6e542f162212706f838386aa1949b28dbc06b3b4a1efc8ce5ee76e89442e"


PRIOR_ONE_SIDE = "e68e153938c1f0a4aab668c88c1a7bcea335ca837e302c1d0e535c142f6e348f"


PRIOR_TWO_SIDES = "50bf7e99eb744f61d0515fc6e8c8df672e7f7331f112432d7bec79b20ac496fe"


def digest(b):
    return hashlib.sha256(b).hexdigest()


def dumps(o):
    return json.dumps(o, ensure_ascii=False, indent=2).encode()


class Members:
    def __init__(self, raw):
        self.raw = raw
        _, self.start, _, self.blocks, self.members = metadata(raw)

    def read(self, name):
        offset, size, flag = self.members[name]
        a = 0
        b = self.start
        buf = bytearray()
        for n, c, mode in self.blocks:
            if offset < a + n and offset + size > a:
                chunk = self.raw[b : b + c]
                codec=mode & 63
                if codec==0: block=chunk
                elif codec==1:
                    from UnityPy.helpers.CompressionHelper import decompress_lzma
                    block=decompress_lzma(chunk)
                elif codec in (2,3): block=lz4.block.decompress(chunk,uncompressed_size=n)
                else: raise ValueError("Unknown UnityFS block codec")
                require(len(block)==n,"Bad UnityFS decoded size")
                buf.extend(block[max(0, offset - a) : min(n, offset + size - a)])
            if a + n >= offset + size:
                break
            a += n
            b += c
        require(len(buf) == size, "Bad UnityFS member " + name)
        return bytes(buf)


def resource_vehicles(res):
    wanted = {
        "T34_76_AI",
        "Panzer_III_J_AI",
        "Panzer_38t_AI",
        "T34_76_Player",
        "Panzer_38t_Player",
    }
    return {
        n: p
        for p, o in res.objects.items()
        if o.type.name == "GameObject" and (n := parse_complete(o)["m_Name"]) in wanted
    }


def release(apk, prior_zip, out, work):
    out.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk) as za, zipfile.ZipFile(prior_zip) as prev:
        base = za.read(ARCHIVE_PATH)
        data = json.loads(prev.read("integration.json"))
        delta = prev.read(data["overlay_file"])
        require(
            digest(base) == BASE_SHA and digest(delta) == data["overlay_sha256"],
            "Source release checksum differs",
        )
        prior = (
            delta[: data["header_bytes"]]
            + base[data["retain_start"] : data["retain_end"]]
            + delta[data["header_bytes"] :]
        )
        require(
            digest(prior)
            == data["result_sha256"]
            in (PRIOR, PRIOR_ONE_SIDE, PRIOR_TWO_SIDES),
            "Unknown preceding release",
        )
        pack = Members(prior)
        get = lambda n: file(pack.read(n))
        names = {
            p: o.read_typetree(check_read=False)["m_ClassName"]
            for p, o in get("globalgamemanagers.assets").objects.items()
            if o.type.name == "MonoScript"
        }
        stock, res, mapfile = get("level8"), get("resources.assets"), get("level21")
        named = resource_vehicles(res)
        ai_index = json.loads(prev.read("AI/Hatch-Enemy-AI-index.json"))
        idx = {e["id"]: e for e in ai_index["prefabs"]}
        a = SimpleNamespace(
            sf=res,
            files={"resources.assets": res, "level8": stock},
            scripts={("globalgamemanagers.assets", p): n for p, n in names.items()},
            templates={},
        )
        for o in res.objects.values():
            a.templates.setdefault(o.type.name, o)
        for ext in res.externals:
            if ext.path in pack.members and ext.path not in a.files:
                a.files[ext.path] = get(ext.path)
        entries = []
        with zipfile.ZipFile(io.BytesIO(za.read("assets/Hatch/mods/T26.hatch"))) as mod:
            entries += [create(a, named, mod, work, player=p) for p in (False, True)]
        previous_t26 = idx["T26"]
        require(
            all(
                entries[0][k] == previous_t26[k]
                for k in (
                    "runtime_sha256",
                    "gameplay",
                    "road_wheels",
                    "model_triangles",
                    "prefab",
                )
            ),
            "T26 source geometry or gameplay changed",
        )
        from ...enemy_verify import verify as verify_prefab

        with zipfile.ZipFile(io.BytesIO(za.read("assets/Hatch/mods/T26.hatch"))) as mod:
            from ...enemy_visuals import read_model

            h = json.loads(mod.read("hatch.json"))
            _, ns, ims = read_model(mod.read("runtime.bin"), h)
            entries[0]["validation"] = verify_prefab(
                a, work / entries[0]["file"], entries[0], (ns, ims, h)
            )
        previous_t26.update(entries[0])
        with zipfile.ZipFile(
            io.BytesIO(prev.read("assets/Hatch/mods/Panzer_II_Ausf_F.hatch"))
        ) as mod:
            ge = create(a, named, mod, work, player=True)
            require(
                ge["runtime_sha256"] == idx["Panzer_II_Ausf_F"]["runtime_sha256"]
                and ge["gameplay"]["weapon"]
                == idx["Panzer_II_Ausf_F"]["gameplay"]["weapon"],
                "German player/AI packages disagree",
            )
            entries.append(ge)
        models = {}
        adds = []
        for e in entries:
            n = e["file"]
            r = (work / n).read_bytes()
            if n not in pack.members or pack.read(n) != r:
                require(
                    n not in pack.members
                    or e["prefab"].endswith("_Player")
                    or n == "T26_AI.assets",
                    "Published native AI file changed",
                )
                adds.append((n, r))
            models[e["id"], e["prefab"].endswith("_Player")] = (
                n,
                file(r),
                e["root_path_id"],
            )
        for id in ("BT7", "Panzer_II_Ausf_F", "Panzer_IV_Ausf_C"):
            e = idx[id]
            n = e["file"]
            r = pack.read(n)
            require(digest(r) == e["sha256"], "Changed prefab: " + id)
            models[id, False] = (n, file(r), e["root_path_id"])
        for id in ("T34_76", "Panzer_III_J", "Panzer_38t"):
            models[id, False] = ("resources.assets", res, named[id + "_AI"])
        hh = layout.heightgrid()
        props = layout.placements(hh)
        deployment = stage(hh, props, legacy=True)
        from .lanes import Lanes

        Lanes(hh, props).bake(deployment)
        ox, oz = OBJECTIVE_XZ
        obj = [ox, round(float(layout.ground(hh, ox, oz)), 4), oz]
        fonts, gui = get("sharedassets0.assets"), get("sharedassets1.assets")
        if data["result_sha256"] == PRIOR:
            title = get("level0")
        else:
            # Build the two buttons from the same unmodified campaign row, not from last revision's bound Button.
            base_members = Members(base)
            title = file(prepare_menu_base({k: base_members.read(k) for k in DIGESTS}))
        m0, ui_source = menu(
            title, get("level1"), names, fonts, stock.objects[159011], gui.objects[121]
        )
        spec = {
            "format": 2,
            "id": "barbarossa_01",
            "title": TITLE,
            "campaign": "巴巴罗萨行动",
            "environment": "barbarossa_polesie_summer",
            "objective_position": obj,
            "sides": {},
        }
        scenes = []
        mg = get("globalgamemanagers")
        bs = next(o for o in mg.objects.values() if o.type.name == "BuildSettings")
        v = parse_complete(bs)
        require(
            len(v["scenes"]) in (22, 23, 24)
            and v["scenes"][21].endswith("Barbarossa_Polesie_Summer.unity"),
            "Unknown scene table",
        )
        for side in SIDES:
            rows = perspective(deployment, side)
            print("Composing", side.code, side.vehicle, flush=True)
            config, scene = make(
                stock if side is SOVIET else get("level8"),
                mapfile,
                models,
                rows,
                names,
                ui_source,
                obj,
                gui,
                fonts,
                hh,
                props,
                side,
            )
            spec["sides"][side.code] = dict(
                name=side.name,
                player=side.vehicle,
                objective=side.objective,
                briefing=side.briefing,
                scene=side.scene,
                index=side.index,
                units=rows,
                **config,
            )
            if side.index < len(v["scenes"]):
                require(
                    v["scenes"][side.index] == side.scene,
                    "Existing slot belongs to a different mission",
                )
            else:
                require(len(v["scenes"]) == side.index, "Invalid scene index")
                v["scenes"].append(side.scene)
            scenes.append((side.member, scene))
            (work / side.member).write_bytes(scene)
        bs.set_raw_data(encode_complete(bs, v))
        mgr = mg.save()
        (work / "level0").write_bytes(m0)
        (work / "globalgamemanagers").write_bytes(mgr)
        (work / "mission.json").write_bytes(dumps(spec))
        flags = {n: "level8" for n, sc in scenes if n not in pack.members}
        flags.update({n: "resources.assets" for n, _ in adds if n not in pack.members})
        result = append_members(
            prior, [("level0", m0), ("globalgamemanagers", mgr), *scenes, *adds], flags
        )
        h, s, e, blocks, members = metadata(base)
        _, s2, _, blocks2, members2 = metadata(result)
        require(
            blocks2[: len(blocks)] == blocks and result[s2 : s2 + e - s] == base[s:e],
            "Base blocks differ",
        )
        overlay = result[:s2] + result[s2 + e - s :]
        release = {
            "format": 1,
            "overlay_file": "Barbarossa-01.overlay",
            "base_sha256": BASE_SHA,
            "prior_result_sha256": data["result_sha256"],
            "factions": [s.code for s in SIDES],
            "result_sha256": digest(result),
            "overlay_sha256": digest(overlay),
            "header_bytes": s2,
            "retain_start": s,
            "retain_end": e,
            "menu_merged": True,
            "campaign_merged": True,
            "android_device_test": False,
        }
        (work / "mission.unity3d").write_bytes(result)
        print("Validating serialized release", flush=True)
        from .verify import verify

        report = verify(result, prior, spec, names)
        (work / "verification.json").write_bytes(dumps(report))
        dest = out / "Barbarossa-01-Gates-of-Hell.zip"
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for name in prev.namelist():
                if name.startswith("assets/Hatch/") or name == "apply_overlay.py":
                    z.writestr(name, prev.read(name))
            z.writestr("AI/Hatch-Enemy-AI-index.json", dumps(ai_index))
            z.writestr("integration.json", dumps(release))
            z.writestr("Barbarossa-01.overlay", overlay)
            z.writestr("mission.json", dumps(spec))
            z.write(Path(__file__).with_name("FONT-LICENSE.txt"), "FONT-LICENSE.txt")
            z.writestr("verification.json", dumps(report))
            z.write(Path(__file__).with_name("README-zh.md"), "README-zh.md")
        print(dest, flush=True)
        return dest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apk", required=True, type=Path)
    p.add_argument("--prior", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--work", required=True, type=Path)
    a = p.parse_args()
    release(a.apk, a.prior, a.output, a.work)
