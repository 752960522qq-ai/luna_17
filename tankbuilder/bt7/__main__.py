"""Build the authored BT-7 from the supplied CC BY dual-vehicle GLB."""

import argparse
import json
import shutil
from pathlib import Path

from .export import build


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--project", type=Path, required=True)
    args = cli.parse_args()
    d = args.project
    d.mkdir(parents=True, exist_ok=True)
    configs = Path(__file__).resolve().parents[2] / "tanks/BT7"
    for name in ("manifest", "tank", "weapon", "armor"):
        f = configs / (name + ".json")
        if f.resolve() != (d / f.name).resolve():
            shutil.copyfile(f, d / f.name)
    thumb = configs / "thumbnail.png"
    if thumb.exists() and thumb.resolve() != (d / thumb.name).resolve():
        shutil.copyfile(thumb, d / thumb.name)
    r = build(args.source, d)
    (d / "rig.json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n")
    print(
        "BT-7 (1937):",
        len(r["wheels"]),
        "wheels,",
        len(r["tracks"]),
        "independent belts",
    )


if __name__ == "__main__":
    main()
