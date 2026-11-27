"""Build the mission from the previous cumulative release and the original game using repository tools."""

import argparse, hashlib, io, json, zipfile
from pathlib import Path
from types import SimpleNamespace
import lz4.block
from ...extra_campaign import file, ARCHIVE_PATH
from ...enemy_prefabs import create, BASE_SHA
from ...serialization import parse_complete, encode_complete
from ...campaign_ugui import require
from .. import layout
from ..bundle import append_members, metadata
from . import TITLE, INDEX, SCENE
from .interface import menu
from .buildscene import make
from .roster import stage

PRIOR = "ac1a6e542f162212706f838386aa1949b28dbc06b3b4a1efc8ce5ee76e89442e"


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
                block = (
                    chunk
                    if mode & 63 == 0
                    else lz4.block.decompress(chunk, uncompressed_size=n)
                )
                buf.extend(block[max(0, offset - a) : min(n, offset + size - a)])
            if a + n >= offset + size:
                break
            a += n
            b += c
        require(len(buf) == size, "Bad UnityFS member " + name)
        return bytes(buf)


def resource_vehicles(res):
    wanted = {"T34_76_AI", "Panzer_III_J_AI", "Panzer_38t_AI", "T34_76_Player"}
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
            digest(prior) == data["result_sha256"] == PRIOR,
            "Expected cumulative IV C release",
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
        ai_idx = json.loads(prev.read("AI/Hatch-Enemy-AI-index.json"))
        idx = {o["id"]: o for o in ai_idx["prefabs"]}
        a = SimpleNamespace(
            sf=res,
            files={"resources.assets": res, "level8": stock},
            scripts={("globalgamemanagers.assets", p): n for p, n in names.items()},
        )
        a.templates = {}
        for o in res.objects.values():
            a.templates.setdefault(o.type.name, o)
        with zipfile.ZipFile(io.BytesIO(za.read("assets/Hatch/mods/T26.hatch"))) as mod:
            entries = [create(a, named, mod, work, player=p) for p in (False, True)]
        require(
            entries[0]["sha256"] == idx["T26"]["sha256"],
            "Friendly T26 geometry differs from released model",
        )
        models = {}
        adds = []
        for e in entries:
            n = e["file"]
            raw = (work / n).read_bytes()
            models["T26", n == "T26_Player.assets"] = (n, file(raw), e["root_path_id"])
            adds.append((n, raw))
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
        rows = stage(hh, props)
        obj = [-180, round(float(layout.ground(hh, -180, -54)), 4), -54]
        from .lanes import Lanes

        Lanes(hh, props).bake(rows)
        fonts = get("sharedassets0.assets")
        m0, (home, txt) = menu(get("level0"), get("level1"), names, fonts)
        print("Composing battle and 21 unit graphs", flush=True)
        ui, scene = make(
            stock,
            mapfile,
            models,
            rows,
            names,
            home,
            txt,
            obj,
            get("sharedassets1.assets"),
            fonts,
            hh,
            props,
        )
        mg = get("globalgamemanagers")
        bs = next(o for o in mg.objects.values() if o.type.name == "BuildSettings")
        v = parse_complete(bs)
        require(
            len(v["scenes"]) == INDEX
            and v["scenes"][-1].endswith("Barbarossa_Polesie_Summer.unity"),
            "Scene index already used",
        )
        v["scenes"].append(SCENE)
        bs.set_raw_data(encode_complete(bs, v))
        mgr = mg.save()
        spec = {
            "format": 1,
            "id": "barbarossa_01",
            "title": TITLE,
            "campaign": "巴巴罗萨行动",
            "scene": SCENE,
            "index": INDEX,
            "environment": "barbarossa_polesie_summer",
            "objective": "夺取村口阵地",
            "objective_position": obj,
            "ui": ui,
            "groups": {"player": 451, "friend": 7063, "enemy": 1940},
            "units": rows,
        }
        (work / "level22").write_bytes(scene)
        (work / "level0").write_bytes(m0)
        (work / "globalgamemanagers").write_bytes(mgr)
        (work / "mission.json").write_bytes(dumps(spec))
        result = append_members(
            prior,
            [("level0", m0), ("globalgamemanagers", mgr), ("level22", scene), *adds],
            {"level22": "level8", **{n: "resources.assets" for n, _ in adds}},
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
            "prior_result_sha256": PRIOR,
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
                if (
                    name.startswith("assets/Hatch/")
                    or name == "AI/Hatch-Enemy-AI-index.json"
                    or name == "apply_overlay.py"
                ):
                    z.writestr(name, prev.read(name))
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
