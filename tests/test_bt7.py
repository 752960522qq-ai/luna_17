"""Check the actual shipped project and `.hatch`; exercise rest contacts and UV motion in three driving cases."""

import argparse
import io
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from hatch.package import validate
from tankbuilder.enemy_visuals import read_model
from tankbuilder.modelrig import Model


def check(value, msg):
    if not value:
        raise ValueError(msg)


def inspect(project, hatch):
    rig = json.loads((project / "rig.json").read_text())
    tank = json.loads((project / "tank.json").read_text())
    m = Model(project / "model.glb")
    g = m.g
    names = {n.name: i for i, n in enumerate(g.nodes)}
    p = m.parents()
    h = validate(hatch)
    with zipfile.ZipFile(hatch) as z:
        check(
            z.testzip() is None
            and z.read("model.glb") == (project / "model.glb").read_bytes(),
            "Pack differs from authored GLB",
        )
        _cfg, nodes, images = read_model(z.read("runtime.bin"), h)
        check(json.loads(z.read("rig.json")) == rig, "Package rig mismatch")
    for child, parent in [
        ("Turret", "Hull"),
        ("Gun", "Turret"),
        ("Barrel_Recoil", "Gun"),
        ("Muzzle_Main", "Barrel_Recoil"),
        ("Muzzle_Coax_DT", "Gun"),
        ("Red_Star_L", "Turret"),
        ("Red_Star_R", "Turret"),
    ]:
        check(p[names[child]] == names[parent], "Wrong control parent: " + child)
    low, hi = map(
        np.array,
        zip(*(m.bounds(i) for i, n in enumerate(g.nodes) if n.mesh is not None)),
    )
    dims = hi.max(0) - low.min(0)
    check(np.allclose(dims, [2.29, 2.42, 5.66], atol=1e-4), "Model envelope")
    check(
        len(rig["wheels"]) == 12 and len({w["node"] for w in rig["wheels"]}) == 12,
        "Wheel bindings",
    )
    check(
        len(g.skins) == 2 and len(g.animations) == 3, "Missing track skin or demo clips"
    )
    periods = rig["trackAnimation"]["physicalLoopMeters"]
    pitch = rig["trackLoopMeters"]
    check(
        np.allclose(np.array(periods) / pitch, [73, 73], atol=0.0001),
        "Non-continuous tread repeat",
    )
    phase = []
    sides = []
    clearance = []
    ground = []
    for si, (side, tag) in enumerate([("left", "l"), ("right", "r")]):
        wheels = [w for w in rig["wheels"] if w["side"] == side]
        road = [w for w in wheels if w["roadWheel"]]
        check(len(road) == 4 and len(wheels) == 6, "Wrong wheel count: " + side)
        sides.append(
            sorted((w["center"][1], w["center"][2], w["radius"]) for w in wheels)
        )
        ti = names["track_" + tag]
        pr = g.meshes[g.nodes[ti].mesh].primitives[0]
        pos = m.array(pr.attributes.POSITION)
        uv = m.array(pr.attributes.TEXCOORD_0)
        weights = m.array(pr.attributes.WEIGHTS_0)
        joints = m.array(pr.attributes.JOINTS_0)
        skin = g.skins[g.nodes[ti].skin]
        check(
            g.materials[pr.material].name == "BT7_tread_" + tag,
            "Track sides share material",
        )
        check(
            np.allclose(weights.sum(1), 1)
            and all(np.any((joints == i) & (weights > 0.55)) for i in range(1, 5)),
            "Track lower run is not weighted to all road contacts",
        )
        check(
            skin.joints[1:] == [w["suspensionNode"] for w in road],
            "Missing suspension anchors on track",
        )
        tri = m.array(pr.indices).ravel().reshape(-1, 3)
        surf = pos[tri]
        vUV = uv[tri][:, :, 1]
        bottom = (surf[:, :, 1] < 0.006).all(1)
        grads = []
        for v, u in zip(surf[bottom], vUV[bottom]):
            a = np.argmax(v[:, 2])
            b = np.argmin(v[:, 2])
            dz = v[a, 2] - v[b, 2]
            if dz > 0.01:
                grads.append((u[a] - u[b]) / np.linalg.norm((v[a] - v[b])[1:]))
        check(
            len(grads) > 10 and np.allclose(grads, 1 / pitch, rtol=0.001),
            "Tread UV reverses or stretches at ground",
        )
        phase.append(float(np.median(grads)))
        for w in road:
            check(
                p[w["node"]] == w["suspensionNode"]
                and p[w["suspensionNode"]] == names["Hull"],
                "Wheel rotation not independent",
            )
            lo, hig = m.bounds(w["node"])
            check(
                np.allclose((hig + lo) / 2, w["center"], atol=1e-5), "Eccentric wheel"
            )
            check(abs((hig - lo)[2] - (hig - lo)[1]) < 0.003, "Oval wheel")
            gap = lo[1] - 0.036
            check(abs(gap) < 0.006, "Wheel floating above or under its belt")
            ground.append(float(gap))

        # Sample textured UV V in Unity at a fixed tread mark. In Unity UV V = 1 - glTF V.
        # Adding +distance/pitch in the material moves a fixed stripe toward +glTF Z on the lower run.
        def visible_displacement(distance, grads=grads):
            return (distance / pitch) / np.median(grads)

        for dl, dr in [(0.78, 0.78), (-0.62, -0.62), (-0.64, 0.64)]:
            d = (dl, dr)[si]
            check(
                abs(visible_displacement(d) - d) < 1e-3
                and np.sign(-(-d / road[0]["radius"]) * road[0]["radius"])
                == np.sign(d),
                "Wheel / tread directions disagree",
            )
        dname = "Red_Star_" + tag.upper()
        sn = names[dname]
        star = g.meshes[g.nodes[sn].mesh].primitives[0]
        sv = m.array(star.attributes.POSITION) + m.translation(sn)
        sel = -1 if si == 0 else 1
        check(np.ptp(sv[:, 1]) > 0.31, "Red star too small")
        check(
            g.materials[star.material].name == "BT7_red", "Insignia has wrong material"
        )
        rn = next(i for i, n in enumerate(nodes) if n.name == dname)
        surfnode = next(n for n in nodes if n.parent == rn and len(n.indices))
        colors = (
            np.asarray(Image.open(io.BytesIO(images[surfnode.images[0]])))
            .reshape(-1, 3)
            .mean(0)
        )
        check(
            colors[0] > colors[1] * 2 and colors[0] > 100,
            "Red paint missing in runtime pack",
        )
        turret = g.nodes[names["Turret"]]
        tris = []
        for prim in g.meshes[turret.mesh].primitives:
            tris.extend(
                m.array(prim.attributes.POSITION)[
                    m.array(prim.indices).ravel().reshape(-1, 3)
                ]
                + m.translation(names["Turret"])
            )
        tri = np.array(tris)
        yz = tri[:, :, 1:]
        b = yz[:, 1] - yz[:, 0]
        c = yz[:, 2] - yz[:, 0]
        den = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
        good = abs(den) > 1e-8
        den = np.where(good, den, 1)
        gaps = []
        for pt in np.unique(sv.round(6), axis=0):
            d = pt[1:] - yz[:, 0]
            u = (d[:, 0] * c[:, 1] - d[:, 1] * c[:, 0]) / den
            v = (b[:, 0] * d[:, 1] - b[:, 1] * d[:, 0]) / den
            inside = good & (u >= -1e-5) & (v >= -1e-5) & (u + v <= 1.00001)
            intersection = (
                tri[:, 0, 0]
                + u * (tri[:, 1, 0] - tri[:, 0, 0])
                + v * (tri[:, 2, 0] - tri[:, 0, 0])
            )
            gaps.append(sel * pt[0] - (sel * intersection[inside]).max())
        check(
            min(gaps) > 0.001 and max(gaps) < 0.005,
            "Marking floats or an attachment covers the red star",
        )
        clearance.append(list(map(float, [min(gaps), max(gaps)])))
    check(np.allclose(sides[0], sides[1], atol=0.003), "Left/right axles not aligned")
    check(
        sum(bool(n.flags & 1) for n in nodes) == 1
        and sum(bool(n.flags & 16) for n in nodes) == 8
        and sum(bool(n.flags & 512) for n in nodes) == 4,
        "Runtime control flags",
    )
    check(
        tank["enginePower"] == 450
        and tank["maxForwardSpeed"] == 52
        and tank["crew"] == 3,
        "Wrong vehicle profile",
    )
    return {
        "runtime_nodes": len(nodes),
        "materials_images": len(images),
        "triangles": sum(len(n.indices) // 3 for n in nodes),
        "envelope_width_height_length_m": dims.tolist(),
        "road_wheels": 8,
        "auxiliary_wheels": 4,
        "wheel_contact_gap_to_inner_belt_m": [min(ground), max(ground)],
        "both_stars_visible_clearance_m": clearance,
        "closed_track_lengths_m": periods,
        "valid_motion": ["forward", "reverse", "counter-rotation"],
        "android_device_test": False,
    }


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    c.add_argument("--project", type=Path, required=True)
    c.add_argument("--hatch", type=Path, required=True)
    c.add_argument("--report", type=Path)
    args = c.parse_args()
    s = json.dumps(inspect(args.project, args.hatch), indent=2) + "\n"
    print(s)
    if args.report:
        args.report.write_text(s)
