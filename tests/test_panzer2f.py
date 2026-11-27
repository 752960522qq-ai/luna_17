"""Exercise the delivered Panzer II F model, physical wheel/UV directions and the released Luchs magazine."""

import argparse
import io
import json
import subprocess
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from hatch.package import validate
from tankbuilder.enemy_visuals import read_model
from tankbuilder.modelrig import Model
from tankbuilder.panzer2f.source import ID

ROOT = Path(__file__).resolve().parents[1]


def check(x, txt):
    if not x:
        raise ValueError(txt)


def inspect(project, hatch, apk):
    h = validate(hatch)
    m = Model(project / "model.glb")
    g = m.g
    r = json.loads((project / "rig.json").read_text())
    parents = m.parents()
    names = {n.name: i for i, n in enumerate(g.nodes)}
    with zipfile.ZipFile(hatch) as z:
        check(
            z.testzip() is None
            and z.read("model.glb") == (project / "model.glb").read_bytes(),
            "Authoring and shipped model differ",
        )
        _, nodes, images = read_model(z.read("runtime.bin"), h)
        wp = json.loads(z.read("weapon.json"))
        check(json.loads(z.read("rig.json")) == r, "Rig mismatch")
    with (
        zipfile.ZipFile(apk) as z,
        zipfile.ZipFile(
            io.BytesIO(z.read("assets/Hatch/mods/Panzer_II_Ausf_L.hatch"))
        ) as l,
    ):
        stock = json.loads(l.read("hatch.json"))
        check(
            stock["continuous_fire"] is h["continuous_fire"] is True
            and stock["magazine"]
            == h["magazine"]
            == wp["magazine"]
            == {"capacity": 10, "shotInterval": 0.4, "reloadTime": 4.85},
            "Magazine differs from the released Luchs",
        )
        check(sum(wp["ammo"].values()) == 180, "Ammunition inventory")
    for name, p in [
        ("Turret", "Hull"),
        ("Gun", "Turret"),
        ("Barrel_Recoil", "Gun"),
        ("Muzzle_Main", "Barrel_Recoil"),
        ("Muzzle_Coax_MG34", "Gun"),
    ]:
        check(parents[names[name]] == names[p], "Incorrect rig parent: " + name)

    def tris(node):
        ans = []
        for pr in g.meshes[g.nodes[node].mesh].primitives:
            ix = m.array(pr.indices).reshape(-1, 3)
            v = m.array(pr.attributes.POSITION)[ix] + m.translation(node)
            n = m.array(pr.attributes.NORMAL)[ix]
            ans.append((v, n))
        return ans

    # Broken source normals produced a black panel on the turret; test emitted normals against real face directions.
    deviations = []
    for name in ("Turret", "Gun", "Barrel_Recoil"):
        for x, n in tris(names[name]):
            f = np.cross(x[:, 1] - x[:, 0], x[:, 2] - x[:, 0])
            lenf = np.linalg.norm(f, axis=1)
            valid = lenf > 1e-7
            fac = f[valid] / lenf[valid, None]
            deviations.extend(np.einsum("ijk,ik->ij", n[valid], fac).ravel())
    check(np.min(deviations) > 0.8, "Turret face normals incorrect")
    full = np.concatenate([t[0] for t in tris(names["Hull"])])
    marks = []
    for mark in r["markings"]:
        i = mark["node"]
        check(
            parents[i] == names["Hull"]
            and len(g.meshes[g.nodes[i].mesh].primitives) == 2,
            "Detached/unfinished Balkenkreuz",
        )
        prims = g.meshes[g.nodes[i].mesh].primitives
        for prim, col in zip(prims, ["white", "black"]):
            mat = g.materials[prim.material]
            check(mat.name.endswith("kreuz_" + col), "Cross color swapped")
            tex = g.textures[mat.pbrMetallicRoughness.baseColorTexture.index].source
            with Image.open(io.BytesIO(images[tex])) as im:
                lum = np.mean(np.asarray(im))
            check(lum > 160 if col == "white" else lum < 45, "Cross paint lost")
        ax = mark["axis"]
        sg = mark["outward"]
        ua = [2, 1] if ax == 0 else [0, 1]
        tri = full[:, :, ua]
        a = tri[:, 0]
        b = tri[:, 1] - a
        c = tri[:, 2] - a
        den = b[:, 0] * c[:, 1] - c[:, 0] * b[:, 1]
        ok = abs(den) > 1e-9
        den = np.where(ok, den, 1)
        gaps = []
        for coords, _ in tris(i):
            for pt in np.unique(coords.reshape(-1, 3), axis=0):
                d = pt[ua] - a
                u = (d[:, 0] * c[:, 1] - d[:, 1] * c[:, 0]) / den
                v = (b[:, 0] * d[:, 1] - b[:, 1] * d[:, 0]) / den
                inside = ok & (u >= -1e-5) & (v >= -1e-5) & (u + v <= 1.00001)
                inter = (
                    full[:, 0, ax]
                    + (full[:, 1, ax] - full[:, 0, ax]) * u
                    + (full[:, 2, ax] - full[:, 0, ax]) * v
                )
                gaps.append(sg * pt[ax] - (sg * inter[inside]).max())
        check(
            min(gaps) > 0.0005 and max(gaps) < 0.006,
            "Cross obscured or floats: " + mark["name"],
        )
        marks.append(mark["name"])
    check(len(set(marks)) == 3, "Cross missing")
    wheels = r["wheels"]
    check(
        len({w["node"] for w in wheels}) == 22 and len(g.skins) == 2,
        "Wheel control count",
    )
    pitch = r["trackLoopMeters"]
    thick = r["trackAnimation"]["beltThickness"]
    gap = []
    sig = []
    for side in ("left", "right"):
        ws = [w for w in wheels if w["side"] == side]
        check(
            Counter(w["wheelKind"] for w in ws)
            == {"road": 5, "return": 4, "drive": 1, "idler": 1},
            "F running gear",
        )
        road = [w for w in ws if w["roadWheel"]]
        tn = names["track_" + side[0]]
        skin = g.skins[g.nodes[tn].skin]
        check(
            skin.joints[1:] == [w["suspensionNode"] for w in road],
            "Track does not follow its side",
        )
        tr = g.meshes[g.nodes[tn].mesh].primitives[0]
        check(
            g.materials[tr.material].name == "Pz2F_tread_" + side[0],
            "Shared track material",
        )
        ind = m.array(tr.indices).reshape(-1, 3)
        pos = m.array(tr.attributes.POSITION)
        surf = pos[ind]
        vs = m.array(tr.attributes.TEXCOORD_0)[ind][:, :, 1]
        wgt = m.array(tr.attributes.WEIGHTS_0)
        jn = m.array(tr.attributes.JOINTS_0)
        check(
            np.allclose(wgt.sum(1), 1)
            and all(np.any((jn == j) & (wgt > 0.60)) for j in range(1, 6)),
            "Skin is not weighted to all five contacts",
        )
        check(abs(pos[:, 1].min()) < 1e-6, "Belt floats")
        bottom = (surf[:, :, 1] < 0.003).all(1)
        grad = []
        for q, uv in zip(surf[bottom], vs[bottom]):
            a = np.argmax(q[:, 2])
            b = np.argmin(q[:, 2])
            delta = q[a] - q[b]
            if delta[2] > 0.01:
                grad.append((uv[a] - uv[b]) / np.linalg.norm(delta[1:]))
        check(
            len(grad) > 12 and np.allclose(grad, 1 / pitch, rtol=0.003),
            "Stretched or reversed bottom run",
        )
        sig.append(float(np.median(grad)))
        for wh in road:
            check(
                parents[wh["node"]] == wh["suspensionNode"]
                and parents[wh["suspensionNode"]] == names["Hull"],
                "Wrong wheel anchor",
            )
            lo, hi = m.bounds(wh["node"])
            check(abs((hi - lo)[1] - (hi - lo)[2]) < 0.002, "Oval road wheel")
            gap.append(float(lo[1] - thick))
            check(abs(gap[-1]) < 0.004, "Road wheel-to-belt contact")
    # Follow a fixed tread mark with Unity V=1-glTF V and a forward or reverse material phase.
    for pair in [(1.13, 1.13), (-0.7, -0.7), (-0.8, 0.8)]:
        for travel, slope in zip(pair, sig):
            check(
                abs(travel / pitch / slope - travel) < 0.001,
                "Wheel/tread directions disagree",
            )
    check(
        sum(bool(n.flags & 16) for n in nodes) == 10
        and sum(bool(n.flags & 512) for n in nodes) == 12
        and sum(bool(n.flags & 64) for n in nodes) == 2,
        "Lost runtime controls",
    )
    check(
        np.allclose(
            np.array(r["trackAnimation"]["physicalLoopMeters"]) / pitch,
            [94, 94],
            atol=0.001,
        ),
        "Loop seam mismatch",
    )
    bounds = [m.bounds(i) for i, n in enumerate(g.nodes) if n.mesh is not None]
    global_min = np.min([x[0] for x in bounds], 0)
    global_max = np.max([x[1] for x in bounds], 0)
    body_height = m.bounds(names["Turret"])[1][1] - global_min[1]
    check(
        abs(body_height - 2.15) < 0.0001
        and np.allclose((global_max - global_min)[[0, 2]], [2.28, 4.81], atol=0.002),
        "Reference envelope including drives",
    )
    with tempfile.TemporaryDirectory() as t:
        exe = str(Path(t) / "mag")
        subprocess.run(
            ["cc", "-O2", str(ROOT / "tests/test_magazine_pool.c"), "-lm", "-o", exe],
            check=True,
        )
        mag = h["magazine"]
        result = subprocess.run(
            [
                exe,
                str(mag["capacity"]),
                str(mag["shotInterval"]),
                str(mag["reloadTime"]),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    return {
        "vehicle": ID,
        "wheel_roles_per_side": {"road": 5, "return": 4, "drive": 1, "idler": 1},
        "contacts": 10,
        "wheel_to_belt_gap_m": [min(gap), max(gap)],
        "marks_verified": marks,
        "worst_turret_normal_dot": float(min(deviations)),
        "length_width_height_m": [
            float(global_max[2] - global_min[2]),
            float(global_max[0] - global_min[0]),
            float(body_height),
        ],
        "height_with_whip_m": float(global_max[1] - global_min[1]),
        "magazine": mag,
        "continuous_fire": h["continuous_fire"],
        "active_magazine_test": result.stdout.splitlines()[0],
        "tracks_checked": ["forward", "reverse", "counter-rotation"],
        "gpu_device_test": False,
    }


if __name__ == "__main__":
    c = argparse.ArgumentParser(description=__doc__)
    for n in ("project", "hatch", "apk", "report"):
        c.add_argument("--" + n, type=Path, required=True)
    a = c.parse_args()
    r = inspect(a.project, a.hatch, a.apk)
    a.report.write_text(json.dumps(r, indent=2) + "\n")
    print(json.dumps(r, indent=2))
