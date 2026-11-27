"""Build, independently validate, and optionally integrate the reusable Polesie scene."""

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from . import layout as L
from .bundle import check_overlay, overlay, unpack_source
from .cartography import cartography, overview
from .native import SCENE_PATH, build, read_bundle, register
from .portable import export
from .verify import validate


def manifest(h, items):
    decks = {row[0] for row in L.BRIDGES}
    return {
        "id": "barbarossa_polesie_summer",
        "name": "巴巴罗萨行动 · 西波列西亚乡野",
        "historical_setting": "1941 · 初夏；虚构复合地形",
        "unity_scene": SCENE_PATH,
        "scene_index": 21,
        "unity_player_file": "level21",
        "size_m": [L.SIZE, L.SIZE],
        "north_axis": "+Z",
        "origin_xz_m": [-L.HALF, -L.HALF],
        "water_elevation_m": L.WATER,
        "includes_mission": False,
        "preview_camera": "Map Preview Camera",
        "spawn_points": [],
        "anchors": {
            name: [
                x,
                round(float(L.DECK if name in decks else L.ground(h, x, z)), 3),
                z,
            ]
            for name, (x, z) in L.ANCHORS.items()
        },
        "roads": {
            name: {"width_m": width, "control_points_xz_m": pts}
            for name, (width, pts) in L.ROADS.items()
        },
        "field_strips": len(L.PLOTS),
        "placed": dict(sorted(Counter(o["kind"] for o in items).items())),
    }


def write_json(path, d):
    path.write_text(
        json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="Reviewed Hatch APK or its data.unity3d",
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Directory for standalone map assets"
    )
    parser.add_argument(
        "--unity-data",
        type=Path,
        help="Also write the verified UnityFS data to a new file",
    )
    parser.add_argument(
        "--check-container",
        action="store_true",
        help="Round-trip a complete UnityFS container in memory",
    )
    parser.add_argument(
        "--labeled-overview",
        action="store_true",
        help="Export Chinese overview (requires local Noto Sans CJK fonts)",
    )
    parser.add_argument(
        "--render-inputs",
        action="store_true",
        help="Export the four tiling textures and control map for an exact ground material in Blender",
    )
    args = parser.parse_args()
    if args.unity_data and (
        args.unity_data.exists() or args.unity_data.resolve() == args.source.resolve()
    ):
        parser.error("--unity-data must be a new output file")
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    b = read_bundle(args.source)
    h = L.heightgrid()
    items = L.placements(h)
    w = L.splat(items)
    scene, kit = build(b, h, w, items)
    manager = register(b)
    report = validate(b, scene, manager, h, w, items)
    if args.unity_data or args.check_container:
        raw = unpack_source(args.source)
        tested = overlay(raw, scene, manager)
        report["container"] = check_overlay(raw, tested, scene, manager)
        if args.unity_data:
            args.unity_data.parent.mkdir(parents=True, exist_ok=True)
            with args.unity_data.open("xb") as dest:
                dest.write(tested)
        del raw, tested
    (out / "level21").write_bytes(scene)
    (out / "globalgamemanagers").write_bytes(manager)
    export(out / "Barbarossa-Polesie.glb", b, h, w, items, kit)
    if args.render_inputs:
        from . import props
        from .native import ONE

        layers = out / "render-layers"
        layers.mkdir(exist_ok=True)
        for i, im in enumerate(
            [
                *[b.files[ONE].objects[j].read().image for j in (107, 144)],
                *props.crops(),
            ]
        ):
            im.convert("RGB").save(layers / f"tile{i}.png")
        Image.fromarray(w[::-1]).save(layers / "splat-view.png")
        np.save(layers / "h.npy", h)
    m = cartography(h, w, items, 1040)
    m.resize((600, 600), Image.Resampling.LANCZOS).save(out / "Minimap_Polesie_600.png")
    if args.labeled_overview:
        overview(m, out / "Polesie-Map-Overview.png")
    write_json(out / "map.json", manifest(h, items))
    report["files_sha256"] = {
        p: hashlib.sha256((out / p).read_bytes()).hexdigest()
        for p in (
            "level21",
            "globalgamemanagers",
            "Barbarossa-Polesie.glb",
            "Minimap_Polesie_600.png",
        )
    }
    write_json(out / "verification.json", report)
    shutil.copyfile(
        Path(__file__).resolve().parents[2] / "docs/barbarossa-polesie.md",
        out / "README.md",
    )
    print(
        f"{SCENE_PATH}: {report['scenery_instances']} scenery instances, {report['mission_anchors']} neutral markers"
    )
    print(out.resolve())


if __name__ == "__main__":
    main()
