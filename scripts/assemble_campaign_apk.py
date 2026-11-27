#!/usr/bin/env python3
"""Overlay a verified two-sided mission kit onto the full base APK. Signing is a separate step."""

from pathlib import Path
import argparse, hashlib, json, re, zipfile
from repack import write_entry

CAT = "assets/Hatch/catalog.json"
DATA = "assets/bin/Data/data.unity3d"
NATIVE = "lib/arm64-v8a/libhatchcampaign.so"
DEX = "classes5.dex"
LOADER = "classes4.dex"
CORE = "assets/Hatch/mods/tankinvincible3000.hatch"
SIG = re.compile(r"META-INF/(?:MANIFEST\.MF|[^/]+\.(?:RSA|DSA|EC|SF))", re.I)
sha = lambda b: hashlib.sha256(b).hexdigest()


def assemble(base, kit, out):
    with (
        zipfile.ZipFile(base) as a,
        zipfile.ZipFile(kit) as k,
        zipfile.ZipFile(out, "w", allowZip64=False) as z,
    ):
        spec = json.loads(k.read("integration.json"))
        r = json.loads(k.read("verification.json"))
        assert r["status"] == "passed" and len(r["reopened_native_scenes"]) == 2
        original = a.read(DATA)
        assert sha(original) == spec["base_sha256"]
        delta = k.read(spec["overlay_file"])
        assert sha(delta) == spec["overlay_sha256"]
        h = spec["header_bytes"]
        data = (
            delta[:h] + original[spec["retain_start"] : spec["retain_end"]] + delta[h:]
        )
        assert sha(data) == spec["result_sha256"]
        old = json.loads(a.read(CAT))
        catalog = json.loads(k.read(CAT))
        by = {v["id"]: v for v in catalog["mods"]}
        assert len(by) == len(catalog["mods"]) == 13
        for item in old["mods"]:
            if item["id"] != "tankinvincible3000":
                assert item == by[item["id"]]
        files = {n for n in k.namelist() if n.startswith("assets/Hatch/mods/")}
        assert files == {
            CORE,
            *[
                "assets/Hatch/mods/" + i + ".hatch"
                for i in ("BT7", "Panzer_II_Ausf_F", "Panzer_IV_Ausf_C")
            ],
        }
        new = files | {CAT, NATIVE, DEX}
        if LOADER in k.namelist():
            assert LOADER in a.namelist()
            new.add(LOADER)
        assert DEX not in a.namelist() and NATIVE not in a.namelist()
        for i in a.infolist():
            n = i.filename
            if SIG.fullmatch(n) or n == "stamp-cert-sha256":
                continue
            v = data if n == DATA else k.read(n) if n in new else a.read(n)
            write_entry(z, n, v, i.compress_type)
        for n in sorted(new - set(a.namelist())):
            write_entry(z, n, k.read(n), zipfile.ZIP_STORED)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for k in ("base", "kit", "out"):
        p.add_argument("--" + k, type=Path, required=True)
    a = p.parse_args()
    assemble(a.base, a.kit, a.out)
