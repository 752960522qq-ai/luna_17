"""Prepare Panzer II Ausf.F in the reviewed Hatch vehicle coordinate system."""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from pygltflib import Scene, Skin

from ..bt7.export import Output, quat
from ..bt7.paint import finish
from .source import CREDIT, ID, Basis, read, shoe_sets, wheels
from .surface import belt, cross, tread_tile

COLORS = {
    "panzer_grau": (68, 72, 75),
    "panels": (72, 76, 78),
    "running_gear": (64, 68, 68),
    "rubber": (42, 43, 43),
    "gunmetal": (52, 57, 60),
    "steel": (76, 77, 74),
    "exhaust": (82, 70, 59),
    "timber": (115, 91, 59),
    "headlamp": (167, 164, 141),
    "kreuz_white": (193, 194, 184),
    "kreuz_black": (24, 26, 26),
}


def texture(src, key):
    if key == "tread":
        im = tread_tile(src)
        return finish(np.asarray(im, float), 4262, 0.82, False)
    col = COLORS[key]
    w = 384 if key in ("panzer_grau", "panels") else 192
    y, x = np.indices((w, w))
    arr = np.zeros((w, w, 3)) + col
    if key == "timber":
        arr += (
            np.sin(y * 0.32 + 2 * np.sin(x * 0.026)) * 0.8
            + np.sin(y * 0.13 + 0.9 * np.cos(x * 0.015)) * 3.5
        )[:, :, None]
    if key == "rubber":
        arr += (np.sin(y * 0.45 + x * 0.05) * 1.0)[:, :, None]
    if key == "headlamp":
        arr += (np.cos(x * 0.39) * 6 + np.cos(y * 0.41) * 4)[:, :, None]
    return finish(
        arr,
        2100 + list(COLORS).index(key),
        0.70 if key.startswith("kreuz") else 1.13,
        key not in ("rubber", "headlamp", "kreuz_black"),
    )


def skin_track(g, root, track, ws, label):
    joints = [root] + [w["suspensionNode"] for w in ws]
    ib = []
    for j in joints:
        M = np.eye(4)
        M[:3, 3] = -g.pos[j]
        ib.append(M.T.ravel())
    g.g.nodes[track].skin = len(g.g.skins)
    g.g.skins.append(
        Skin(
            name="Pz2F_track_" + label,
            joints=joints,
            skeleton=root,
            inverseBindMatrices=g.add_array(ib, "MAT4"),
        )
    )
    pr = g.g.meshes[g.g.nodes[track].mesh].primitives[0]
    v = g.array(pr.attributes.POSITION)
    z = np.array([q["center"][2] for q in ws])
    j = np.zeros((len(v), 4), np.uint16)
    w = np.zeros((len(v), 4))
    blend = (
        np.clip(1 - v[:, 1] / 0.41, 0, 1)
        * np.clip((v[:, 2] - z[0] + 0.42) / 0.42, 0, 1)
        * np.clip((z[-1] + 0.42 - v[:, 2]) / 0.42, 0, 1)
    )
    for i, pt in enumerate(v):
        b = np.clip(np.searchsorted(z, pt[2]), 1, len(z) - 1)
        a = b - 1
        t = np.clip((pt[2] - z[a]) / (z[b] - z[a]), 0.0, 1.0)
        j[i, :3] = [0, a + 1, b + 1]
        w[i, :3] = [1 - blend[i], blend[i] * (1 - t), blend[i] * t]
    pr.attributes.JOINTS_0 = g.add_array(j, "VEC4", 5123)
    pr.attributes.WEIGHTS_0 = g.add_array(w, "VEC4")


def generate(src, out):
    out.mkdir(parents=True, exist_ok=True)
    configs = Path(__file__).resolve().parents[2] / "tanks" / ID
    for name in (
        "manifest.json",
        "tank.json",
        "weapon.json",
        "armor.json",
        "thumbnail.png",
    ):
        f = configs / name
        if f.is_file() and f.resolve() != (out / name).resolve():
            shutil.copyfile(f, out / name)
    ps = read(src)
    B = Basis(ps)
    ws, owner = wheels(ps)
    sets = shoe_sets(ps)
    shoe_ids = set(sets["left"] + sets["right"])
    tile = ps[
        min(
            sets["left"],
            key=lambda i: abs(ps[i].center[1]) + 4 * abs(ps[i].center[2] + 750),
        )
    ]
    g = Output(tile, "Pz2F", texture)
    g.pos = []
    root = g.node("Hull")
    g.g.scenes = [Scene(nodes=[root])]
    g.g.scene = 0
    # The lower turret shell, not the off-center cupola, locates yaw; the opposed mantlet bearings locate pitch.
    ring = ps[412].p.reshape(-1, 3)
    ring = ring[ring[:, 2] < ring[:, 2].min() + 8]
    yaw = (ring.min(0) + ring.max(0)) / 2
    turret = g.node("Turret", root, B.point(yaw))
    pivot = B.point([-67, -1935, 2129])
    gun = g.node("Gun", turret, pivot)
    recoil = g.node("Barrel_Recoil", gun, pivot)

    def muzzle(i):
        v = ps[i].p.reshape(-1, 3)
        k = v[v[:, 1] < v[:, 1].min() + 1]
        v = (k.min(0) + k.max(0)) / 2
        v[1] -= 3
        return B.point(v)

    main = muzzle(539)
    coax = muzzle(478)
    mn = g.node("Muzzle_Main", recoil, main)
    cn = g.node("Muzzle_Coax_MG34", gun, coax)
    groups = {root: [], turret: [], gun: [], recoil: []}
    wheelparts = {w["name"]: [] for w in ws}
    fixed = []
    raw_part = {}
    for i, o in ps.items():
        if i in shoe_ids:
            continue
        loc = turret if o.m == 6 else root
        ma = {
            0: "panels",
            1: "gunmetal",
            2: "panels",
            3: "panzer_grau",
            4: "rubber",
            5: "steel",
            6: "panzer_grau",
            7: "timber",
        }[o.m]
        if i in (539, 540):
            loc = recoil
        if i in (460, 474, 516, 478):
            loc = gun
        if i in (429, 498):
            ma = "exhaust"
        if i == 902:
            ma = "gunmetal"
        if i in owner and o.m != 4:
            ma = "running_gear"
        part = B.part(o, ma)
        if part is None:
            continue
        raw_part[i] = part
        if i in owner:
            w = next(w for w in ws if w["name"] == owner[i])
            center = B.point(w["center"])
            part.v[:, 2] = (
                center[2] + (part.v[:, 2] - center[2]) * B.scale[2] / B.scale[1]
            )
            wheelparts[w["name"]].append(part)
            continue
        groups[loc].append(part)
        if loc == root:
            fixed.append(part.v[part.ix.reshape(-1, 3)])
    for node, parts in groups.items():
        g.mesh(node, parts)
    fixed = np.concatenate(fixed)
    markings = []
    for label, axis, sgn, key, raw, size in [
        ("LeftBox", 0, -1, 624, [1340, 1895, 1370], 0.249),
        ("RightBox", 0, 1, 121, [-1930, -848, 1370], 0.249),
        ("Rear", 2, 1, None, [285, 3390, 420], 0.183),
    ]:
        target = raw_part[key].v[raw_part[key].ix.reshape(-1, 3)] if key else fixed
        uv = [2, 1] if axis == 0 else [0, 1]
        targetpos = B.point(raw)[uv]
        marks, center = cross(target, fixed, axis, sgn, targetpos, size)
        node = g.node("Balkenkreuz_" + label, root)
        g.mesh(node, marks)
        markings.append(
            {
                "node": node,
                "name": label,
                "axis": axis,
                "outward": sgn,
                "placement": center,
                "size": size,
            }
        )
    records = []
    tracks = []
    periods = []
    lengths = []
    for side in ("left", "right"):
        for w in [q for q in ws if q["side"] == side]:
            cen = B.point(w["center"])
            nm = w["name"]
            road = w["kind"] == "road"
            pr = g.node("Suspension_" + nm, root, cen) if road else root
            wn = g.node(nm, pr, cen)
            g.mesh(wn, wheelparts[nm])
            e = {
                "name": nm,
                "node": wn,
                "side": side,
                "roadWheel": road,
                "wheelKind": w["kind"],
                "center": cen.tolist(),
                "radius": float(w["rawRadius"] * B.scale[2]),
                "sourceParts": w["parts"],
            }
            if road:
                e.update(suspensionNode=pr, restLocalPosition=cen.tolist())
            records.append(e)
        part, per, length, thick = belt([ps[i] for i in sets[side]], B)
        periods.append(per)
        lengths.append(length)
        tag = side[0]
        tn = g.node("track_" + tag, root)
        part.m = "tread_" + tag
        g.mesh(tn, [part])
        tracks.append(tn)
        skin_track(
            g,
            root,
            tn,
            [w for w in records if w["side"] == side and w["roadWheel"]],
            tag,
        )
    if abs(periods[0] - periods[1]) > 0.0001:
        raise ValueError("Track pitch discrepancy")
    times = np.linspace(0, 4, 49)
    g.clip(
        "Wheel_spin_1m_s",
        [
            (w["node"], "rotation", times, quat(0, -times / w["radius"]))
            for w in records
        ],
    )
    g.clip(
        "Leaf_suspension",
        [
            (
                w["suspensionNode"],
                "translation",
                times,
                np.array(w["center"])
                + np.column_stack(
                    [
                        times * 0,
                        0.045
                        * np.sin(times * np.pi / 2)
                        * np.sin(times * 3.2 + w["center"][2] * 2.5),
                        times * 0,
                    ]
                ),
            )
            for w in records
            if w["roadWheel"]
        ],
    )
    tm = np.array([0, 1, 2, 3, 4])
    g.clip(
        "Turret_pitch_and_recoil",
        [
            (turret, "rotation", tm, quat(1, np.radians([0, 28, 0, -28, 0]))),
            (gun, "rotation", tm, quat(0, np.radians([0, 16, 0, -9.5, 0]))),
            (
                recoil,
                "translation",
                np.array([0, 1.0, 1.07, 1.3, 4]),
                np.array([[0, 0, 0], [0, 0, 0], [0, 0, 0.055], [0, 0, 0], [0, 0, 0]]),
            ),
        ],
    )
    g.g.asset.extras = {
        **CREDIT,
        "coordinates": "metres; -Z forward, +Y up",
        "variant": "Panzer II Ausf.F; hull height excludes separate radio whip",
    }
    g.save(out / "model.glb")

    def box(v, org):
        lo = v.min(0)
        hi = v.max(0)
        return {"size": (hi - lo).tolist(), "center": ((lo + hi) / 2 - org).tolist()}

    hull = box(B.point(ps[347].p.reshape(-1, 3)), g.pos[root])
    h = hull["center"][1] + hull["size"][1] / 2
    hull["size"][1] = h
    hull["center"][1] = h / 2
    r = {
        "format": 1,
        "forward": "-Z",
        "turret": {"node": turret, "pivot": g.pos[turret].tolist(), "speedDegSec": 20},
        "gun": {
            "node": gun,
            "pivot": pivot.tolist(),
            "elevation": 20,
            "depression": 10,
            "recoil": 0.055,
            "recoilNode": recoil,
        },
        "muzzle": {"node": mn, "position": main.tolist()},
        "coaxMuzzle": {"node": cn, "position": coax.tolist()},
        "wheels": records,
        "tracks": ["track_l", "track_r"],
        "trackLoopMeters": float(np.mean(periods)),
        "trackAnimation": {
            "axis": "V",
            "physicalLoopMeters": lengths,
            "linksPerLoop": 94,
            "texturePeriodMeters": float(np.mean(periods)),
            "beltThickness": thick,
            "originalStaticSpareLinksKeptSeparate": True,
        },
        "suspension": {
            "travel": 0.13,
            "restCompression": 0.064,
            "springPerWheel": 146000,
            "damperPerWheel": 5600,
            "totalMassKg": 9500,
            "contacts": 10,
        },
        "colliders": {
            "hull": hull,
            "turret": box(B.point(ps[412].p.reshape(-1, 3)), g.pos[turret]),
            "unit": {"center": [0, 1.075, 0], "size": [2.28, 2.15, 4.81]},
        },
        "markings": markings,
        "source": CREDIT,
        "sourceDimensionsExcludingRadioWhip": [4.81, 2.28, 2.15],
    }
    (out / "rig.json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n")
    return r


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--project", type=Path, required=True)
    a = p.parse_args()
    r = generate(a.source, a.project)
    print("Built", len(r["wheels"]), "wheels;", r["markings"])
