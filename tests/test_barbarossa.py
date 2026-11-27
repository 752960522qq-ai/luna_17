"""Checks against the artifacts, plus two deliberately broken driving scenarios.

PYTHONPATH=. python tests/test_barbarossa.py --source /path/to/data.unity3d --output /path/to/Polesie
"""

import argparse
import json
import struct
from pathlib import Path

import numpy as np

from tankbuilder.barbarossa import layout as L
from tankbuilder.barbarossa.bundle import (
    check_overlay,
    metadata,
    overlay,
    unpack_source,
)
from tankbuilder.barbarossa.native import check, read_bundle
from tankbuilder.barbarossa.verify import road_checks, validate


def must_fail(fn, message):
    try:
        fn()
    except ValueError as ex:
        if message in str(ex):
            return
        raise
    raise AssertionError("Expected rejection: " + message)


def glb_check(raw, h, items):
    magic, version, size = struct.unpack_from("<4sII", raw)
    check((magic, version, size) == (b"glTF", 2, len(raw)), "Invalid GLB header")
    n, tag = struct.unpack_from("<I4s", raw, 12)
    check(tag == b"JSON", "Missing glTF scene")
    d = json.loads(raw[20 : 20 + n])
    size, tag = struct.unpack_from("<I4s", raw, 20 + n)
    buf = raw[28 + n :]
    check(
        tag == b"BIN\0" and size == len(buf) == d["buffers"][0]["byteLength"],
        "Invalid glTF binary",
    )
    nodes = {v["name"]: v for v in d["nodes"]}
    mesh = d["meshes"][nodes["Field_Polesie"]["mesh"]]
    a = d["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
    v = d["bufferViews"][a["bufferView"]]
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    points = np.frombuffer(
        buf, dtype="<f4", count=a["count"] * 3, offset=start
    ).reshape(L.RES, L.RES, 3)
    x, z = L.grid(L.RES)
    check(
        np.array_equal(points[:, :, 0], x) and np.array_equal(points[:, :, 2], -z),
        "Mirrored or displaced preview",
    )
    check(
        np.allclose(points[:, :, 1], h * (64 / 32766), atol=5e-6),
        "GLB terrain disagrees with native heights",
    )
    for i, o in enumerate(items):
        name = f"{o['kind']}_{i:04}"
        vec = nodes[name]["translation"]
        check(
            np.allclose(vec, [o["x"], o["y"], -o["z"]]),
            "Displaced preview object: " + name,
        )
    check(
        all("bufferView" in i and "uri" not in i for i in d["images"]),
        "GLB references an external image",
    )


def test(source, out):
    raw = unpack_source(source)
    b = read_bundle(source)
    h = L.heightgrid()
    items = L.placements(h)
    w = L.splat(items)
    sc = (out / "level21").read_bytes()
    reg = (out / "globalgamemanagers").read_bytes()
    stats = validate(b, sc, reg, h, w, items)
    glb_check((out / "Barbarossa-Polesie.glb").read_bytes(), h, items)
    dec = json.loads((out / "map.json").read_text())
    check(
        set(dec["anchors"]) == set(L.ANCHORS) and not dec["includes_mission"],
        "Unusable mission manifest",
    )
    worst = {n: (x, z, l, width, L.DECK) for n, x, z, l, width in L.BRIDGES}
    no_objects = [[2400, 2500, 1, 0, 1, 1]]
    obstacle_on_road = [[-149, float(L.road_z(-149)), 1, 0, 3, 3]]
    must_fail(
        lambda: road_checks(h, obstacle_on_road, L.ANCHORS, worst), "Solid obstacle"
    )
    # Add a low gap across the dry approach, without changing the deck.
    hh = h.copy()
    cx = round((150 + 72 / 2 + 6 + 700) * 256 / 1400)
    cz = round((-30 + 700) * 256 / 1400)
    hh[cz - 1 : cz + 2, cx : cx + 2] = 0
    must_fail(lambda: road_checks(hh, no_objects, L.ANCHORS, worst), "Submerged road")
    integ = overlay(raw, sc, reg)
    check_overlay(raw, integ, sc, reg)
    must_fail(lambda: overlay(integ, sc, reg), "slot collision")
    bad = bytearray(raw)
    bad[0] = 0
    must_fail(lambda: metadata(bad), "Unsupported UnityFS version")
    print(
        "PASS: serialized scene/registry and unchanged container blocks; mirrored-axis GLB instance comparison; road obstruction, submerged approach and duplicate slot rejected."
    )
    print("Route samples:", stats["road_center_samples"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    test(a.source, a.output)
