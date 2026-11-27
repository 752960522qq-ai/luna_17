#!/usr/bin/env python3
"""Build the extra campaign against the actual released core; keep its native engine intact."""

import argparse, hashlib, io, json, os, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hatch.package import pack_module


def build(args):
    o = args.work.resolve()
    o.mkdir(parents=True, exist_ok=True)
    sdk = args.build_tools.resolve()
    android = args.android_jar.resolve()
    for n in ("interfaces", "main", "mod", "main-dex", "mod-dex"):
        (o / n).mkdir(exist_ok=True)

    def run(*cmd):
        subprocess.run(list(map(str, cmd)), check=True)

    def jav(out, cp, files):
        run(
            "java",
            "com.sun.tools.javac.Main",
            "-source",
            "8",
            "-target",
            "8",
            "-Xlint:-options",
            "-encoding",
            "UTF-8",
            "-cp",
            os.pathsep.join(map(str, (android, *cp))),
            "-d",
            o / out,
            *files,
        )

    def dex(src, out, others):
        run(
            "java",
            "-cp",
            sdk / "lib/d8.jar",
            "com.android.tools.r8.D8",
            "--lib",
            android,
            "--min-api",
            "28",
            "--output",
            o / out,
            *[i for p in others for i in ("--classpath", o / p)],
            *sorted((o / src).rglob("*.class")),
        )

    jav(
        "interfaces",
        [],
        [
            *sorted((ROOT / "loader/src").rglob("*.java")),
            *sorted((ROOT / "app/stubs").rglob("*.java")),
        ],
    )
    jav("main", [], sorted((ROOT / "campaign-runtime/java").rglob("*.java")))
    jav(
        "mod",
        [o / "interfaces", o / "main"],
        sorted((ROOT / "mods/tankinvincible/src").rglob("*.java")),
    )
    dex("main", "main-dex", [])
    dex("mod", "mod-dex", ["interfaces", "main"])
    run(
        args.clang,
        "-std=c11",
        "-O2",
        "-shared",
        "-fPIC",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wl,-z,max-page-size=16384,-z,defs,-soname,libhatchcampaign.so",
        ROOT / "campaign-runtime/campaign.c",
        "-ldl",
        "-lm",
        "-o",
        o / "libhatchcampaign.so",
    )
    with (
        zipfile.ZipFile(args.base_apk) as apk,
        zipfile.ZipFile(
            io.BytesIO(apk.read("assets/Hatch/mods/tankinvincible3000.hatch"))
        ) as core,
    ):
        orig = core.read("module.so")
        h = json.loads(core.read("hatch.json"))
        assert (
            hashlib.sha256(orig).hexdigest()
            == h["native_sha256"]
            == "5f0195c93f967c0e24458e1d39a751c39f4256653cc836a09f3ff2644b93a02f"
        )
    (o / "released-core.so").write_bytes(orig)
    pack_module(
        o / "mod-dex/classes.dex",
        o / "released-core.so",
        o / "tankinvincible3000.hatch",
    )
    return o


def overlay(kit, work):
    core = "assets/Hatch/mods/tankinvincible3000.hatch"
    cat = "assets/Hatch/catalog.json"
    members = {
        core: (work / "tankinvincible3000.hatch").read_bytes(),
        "classes5.dex": (work / "main-dex/classes.dex").read_bytes(),
        "lib/arm64-v8a/libhatchcampaign.so": (
            work / "libhatchcampaign.so"
        ).read_bytes(),
    }
    temp = kit.with_suffix(".next")
    with (
        zipfile.ZipFile(kit) as old,
        zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as out,
    ):
        catalog = json.loads(old.read(cat))
        (record,) = [e for e in catalog["mods"] if e["id"] == "tankinvincible3000"]
        record.update(
            size=len(members[core]), sha256=hashlib.sha256(members[core]).hexdigest()
        )
        members[cat] = json.dumps(catalog, ensure_ascii=False, indent=2).encode()
        for n in old.namelist():
            if n not in members:
                out.writestr(n, old.read(n))
        for n, data in members.items():
            out.writestr(n, data)
    temp.replace(kit)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("work", "build-tools", "android-jar", "clang", "base-apk", "kit"):
        p.add_argument("--" + n, required=True, type=Path)
    a = p.parse_args()
    overlay(a.kit, build(a))
