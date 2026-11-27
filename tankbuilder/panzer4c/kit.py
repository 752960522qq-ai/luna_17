"""Create a cumulative engineering ZIP, retaining the previous loose prefabs and checking shipped bytes."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from ..bt7.integrate import check
from .source import ID


def build(integration, previous, ai_dir, verification, out):
    docs = Path(__file__).resolve().parents[2] / "docs"
    index = json.loads((ai_dir / "Hatch-Enemy-AI-index.json").read_text())["prefabs"]
    entries = {e["id"]: e for e in index}
    report = json.loads((integration / "integration.json").read_text())
    catalog = {
        e["id"]: e
        for e in json.loads((integration / "assets/Hatch/catalog.json").read_text())[
            "mods"
        ]
    }
    files = {
        p.relative_to(integration).as_posix(): p
        for p in integration.rglob("*")
        if p.is_file()
    }
    files.update(
        {
            "AI/" + entries[ID]["file"]: ai_dir / entries[ID]["file"],
            "AI/Hatch-Enemy-AI-index.json": ai_dir / "Hatch-Enemy-AI-index.json",
            "使用说明.txt": docs / "panzer-iv-c-kit.txt",
            "PanzerIV-C-Notes.md": docs / "panzer-iv-c.md",
            "verification/rig.json": verification / "rig-qa.json",
            "verification/native-loader.txt": verification / "native-qa.txt",
        }
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_suffix(".tmp")
    try:
        with (
            zipfile.ZipFile(previous) as prior,
            zipfile.ZipFile(
                partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as z,
        ):
            old = json.loads(prior.read("AI/Hatch-Enemy-AI-index.json"))["prefabs"]
            check(
                old == index[:-1] and entries[ID] == index[-1],
                "Registry is not additive",
            )
            for v in report["preserved_player_additions"]:
                path = "AI/" + entries[v]["file"]
                z.writestr(path, prior.read(path))
            for name, file in sorted(files.items()):
                z.write(file, name)
        with zipfile.ZipFile(partial) as z:
            check(z.testzip() is None, "ZIP CRC check failed")

            def sha(key):
                return hashlib.sha256(z.read(key)).hexdigest()

            check(
                sha(report["overlay_file"]) == report["overlay_sha256"],
                "Corrupt cumulative overlay",
            )
            for v in [*report["preserved_player_additions"], ID]:
                path = "assets/Hatch/mods/" + v + ".hatch"
                check(
                    sha(path) == catalog[v]["sha256"]
                    and z.getinfo(path).file_size == catalog[v]["size"],
                    "Corrupt .hatch: " + v,
                )
                check(
                    sha("AI/" + entries[v]["file"]) == entries[v]["sha256"],
                    "Corrupt native prefab: " + v,
                )
        partial.replace(out)
    finally:
        partial.unlink(missing_ok=True)
    return out


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    for k in ("integration", "previous", "ai-dir", "verification", "out"):
        c.add_argument("--" + k, type=Path, required=True)
    print(build(**vars(c.parse_args())))
