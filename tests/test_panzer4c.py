"""Inspect the final C-model project AND its actual packaged control graph, track UVs, paint and ammunition."""

import argparse
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from hatch.package import validate
from tankbuilder.enemy_visuals import read_model
from tankbuilder.modelrig import Model


def check(v, label):
    if not v:
        raise ValueError(label)


def clearance(tri, p, axis, sign):
    uv = [2, 1] if axis == 0 else [0, 1]
    flat = tri[:, :, uv]
    a = flat[:, 0]
    b = flat[:, 1] - a
    c = flat[:, 2] - a
    d = p[uv] - a
    det = b[:, 0] * c[:, 1] - c[:, 0] * b[:, 1]
    valid = abs(det) > 1e-8
    div = np.where(valid, det, 1.0)
    u = (d[:, 0] * c[:, 1] - c[:, 0] * d[:, 1]) / div
    v = (b[:, 0] * d[:, 1] - d[:, 0] * b[:, 1]) / div
    mask = valid & (u >= -0.00002) & (v >= -0.00002) & (u + v < 1.00002)
    z = tri[:, :, axis]
    hit = z[:, 0] + u * (z[:, 1] - z[:, 0]) + v * (z[:, 2] - z[:, 0])
    return sign * p[axis] - (sign * hit[mask]).max()


def verify(project, hatch):
    h = validate(hatch)
    m = Model(project / "model.glb")
    g = m.g

    def read(n):
        return json.loads((project / (n + ".json")).read_text())

    rig = read("rig")
    tank = read("tank")
    with zipfile.ZipFile(hatch) as z:
        check(
            z.testzip() is None
            and z.read("model.glb") == (project / "model.glb").read_bytes(),
            "Wrong packaged mesh",
        )
        check(
            all(
                json.loads(z.read(n + ".json")) == read(n)
                for n in ("rig", "tank", "weapon", "manifest", "armor")
            ),
            "Wrong packaged data",
        )
        cfg, nodes, images = read_model(z.read("runtime.bin"), h)
        weapon = read("weapon")
        check(
            weapon["caliber"] == 75
            and h["continuous_fire"] is False
            and "magazine" not in h
            and weapon["reload"] == 5.0
            and sum(weapon["ammo"].values()) == 80,
            "Cannon/loadout",
        )
        check(
            h["id"] == "Panzer_IV_Ausf_C"
            and h["id"] == read("manifest")["id"]
            and h["vehicle_kind"] == "tank"
            and cfg[4 + 30] == 16,
            "Runtime identity/axles",
        )
    names = {n.name: i for i, n in enumerate(g.nodes)}
    parent = m.parents()
    for child, pr in [
        ("Turret", "Hull"),
        ("Gun", "Turret"),
        ("Barrel_Recoil", "Gun"),
        ("Muzzle_Main", "Barrel_Recoil"),
        ("Muzzle_Coax_MG34", "Gun"),
    ]:
        check(parent[names[child]] == names[pr], "Wrong hierarchy: " + child)
    check(
        np.linalg.norm(
            m.translation(names["Muzzle_Main"])
            - m.translation(names["Muzzle_Coax_MG34"])
        )
        > 0.42,
        "Coax bound to the short gun muzzle",
    )

    def parts(i):
        for pr in g.meshes[g.nodes[i].mesh].primitives:
            idx = m.array(pr.indices).reshape(-1, 3)
            p = m.array(pr.attributes.POSITION)
            yield pr, idx, p + m.translation(i)

    hull = np.concatenate(
        [
            p[ix]
            for i, n in enumerate(g.nodes)
            if n.mesh is not None and not n.name.startswith("Balkenkreuz")
            for _, ix, p in parts(i)
        ]
    )
    marks = []
    for rec in rig["markings"]:
        i = rec["node"]
        check(parent[i] == names["Hull"], "Detached marking")
        dist = []
        for (pr, _, p), color in zip(parts(i), ("white", "black"), strict=True):
            mat = g.materials[pr.material]
            check(mat.name.endswith("kreuz_" + color), "Marking layer")
            im = np.array(
                Image.open(
                    io.BytesIO(
                        images[
                            g.textures[
                                mat.pbrMetallicRoughness.baseColorTexture.index
                            ].source
                        ]
                    )
                )
            )
            check(
                im.mean() > 165 if color == "white" else im.mean() < 40,
                "Marking colour",
            )
            dist.extend(
                clearance(hull, x, rec["axis"], rec["outward"])
                for x in np.unique(p, axis=0)
            )
        check(
            min(dist) > 0.0008 and max(dist) < 0.005,
            "Floating/occluded marking: " + rec["name"],
        )
        marks.append(rec["name"])
    check(len(set(marks)) == 3, "Missing insignia")
    skins = []
    gaps = []
    slopes = []
    rad_err = []
    anim = rig["trackAnimation"]
    period = rig["trackLoopMeters"]
    for side in ["left", "right"]:
        ws = [w for w in rig["wheels"] if w["side"] == side]
        check(
            Counter(w["wheelKind"] for w in ws)
            == {"road": 8, "return": 4, "idler": 1, "drive": 1},
            "Wrong variant wheel count",
        )
        rd = [w for w in ws if w["roadWheel"]]
        pairs = [b for b in rig["bogies"] if b["side"] == side]
        check(
            len(pairs) == 4
            and [n for b in pairs for n in b["wheels"]] == [w["name"] for w in rd]
            and all(g.nodes[b["node"]].mesh is not None for b in pairs),
            "Bogie geometry/pairing",
        )
        for w in ws:
            cen = np.array(w["center"])
            p = np.vstack([q for _, _, q in parts(w["node"])])
            r = np.linalg.norm(p[:, 1:] - cen[None, 1:], axis=1).max()
            rad_err.append(abs(r - w["radius"]))
            check(rad_err[-1] < 0.006, "Wheel axle/radius mismatch " + w["name"])
            if w["roadWheel"]:
                check(
                    parent[w["node"]] == w["suspensionNode"]
                    and parent[w["suspensionNode"]] == names["Hull"],
                    "Wheel/anchor parent",
                )
                gaps.append(float(p[:, 1].min() - anim["beltThickness"]))
        tn = names["track_" + side[0]]
        sk = g.skins[g.nodes[tn].skin]
        skins.append(len(sk.joints) - 1)
        check(
            sk.joints[1:] == [w["suspensionNode"] for w in rd],
            "Crossed/absent track weights",
        )
        pr, ix, p = next(parts(tn))
        check(
            g.materials[pr.material].name == "Pz4C_tread_" + side[0],
            "Track material not independent",
        )
        j = m.array(pr.attributes.JOINTS_0)
        w = m.array(pr.attributes.WEIGHTS_0)
        check(
            np.allclose(w.sum(1), 1)
            and all(np.any((j == k) & (w > 0.7)) for k in range(1, 9)),
            "Weight/road contact coverage",
        )
        check(abs(p[:, 1].min()) < 1e-5, "Track floats")
        uv = m.array(pr.attributes.TEXCOORD_0)[:, 1]
        good = []
        for t in ix:
            pts = p[t]
            a = np.argmin(pts[:, 2])
            b = np.argmax(pts[:, 2])
            dz = pts[b, 2] - pts[a, 2]
            if (
                np.ptp(pts[:, 1]) < 1e-6
                and pts[:, 1].max() < 0.062
                and abs(pts[:, 2]).max() < 1.85
                and dz > 0.14
            ):
                good.append((uv[t[b]] - uv[t[a]]) / dz)
        check(
            len(good) >= 18 and np.max(abs(np.array(good) * period - 1)) < 0.003,
            "Tread UV stretch, seam or sign",
        )
        slopes.append(float(np.median(good)))
    check(max(abs(x) for x in gaps) < 0.001, "Wheel/track contact")
    for d in [(1, 1), (-0.8, -0.8), (-0.85, 0.85)]:
        check(
            np.allclose(np.array(d) / period / slopes, d, atol=0.001),
            "Wheel/UV direction",
        )
    check(
        np.allclose(
            np.array(anim["physicalLoopMeters"]) / period, [25, 25], atol=0.001
        ),
        "Tread seam",
    )
    check(
        sum(bool(n.flags & 16) for n in nodes) == 16
        and sum(bool(n.flags & 512) for n in nodes) == 12
        and sum(bool(n.flags & 64) for n in nodes) == 2,
        "Lost controls in runtime",
    )
    geom = hull.reshape(-1, 3)
    span = np.ptp(geom, axis=0)
    height = m.bounds(names["Turret"])[1][1] - geom[:, 1].min()
    check(
        np.allclose([span[2], span[0], height], [5.92, 2.83, 2.68], atol=0.003)
        and span[1] > height + 0.6,
        "Reference envelope/whip",
    )
    check(
        tank["weightTonnes"] == 18.5
        and tank["crew"] == 5
        and tank["enginePower"] == 300
        and tank["maxForwardSpeed"] == 42,
        "Wrong historical stats",
    )
    tex = g.materials[next(parts(names["Turret"]))[0].material]
    im = np.asarray(
        Image.open(
            io.BytesIO(
                images[
                    g.textures[tex.pbrMetallicRoughness.baseColorTexture.index].source
                ]
            )
        ).convert("RGB")
    )
    check(
        np.std(im) > 10 and 32 < np.median(im) < 85,
        "Baked detail missing or pale gray turret",
    )
    return {
        "id": h["id"],
        "runtime_sha256": h["runtime_sha256"],
        "runtime_nodes": len(nodes),
        "textures": len(images),
        "triangles": sum(len(n.indices) // 3 for n in nodes),
        "wheel_axles": 28,
        "suspension_contacts": sum(skins),
        "paired_bogies": 8,
        "max_wheel_radius_error_m": float(max(rad_err)),
        "wheel_belt_gap_m": [min(gaps), max(gaps)],
        "ground_uv_gradient": slopes,
        "checks": ["forward", "reverse", "counter-rotation"],
        "model_height_with_antenna_m": float(span[1]),
        "size_without_antenna_m": [float(span[2]), float(span[0]), float(height)],
        "insignia": marks,
        "trigger": "single shot",
        "game_reload_seconds": weapon["reload"],
        "android_device_test": False,
    }


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    for n in ("project", "hatch", "report"):
        c.add_argument("--" + n, type=Path, required=True)
    o = c.parse_args()
    r = verify(o.project, o.hatch)
    o.report.write_text(json.dumps(r, indent=2) + "\n")
    print(json.dumps(r, indent=2))
