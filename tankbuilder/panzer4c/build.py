"""Build the UV-preserving Panzer IV C model and its Hatch runtime rig from the credited GLB."""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from pygltflib import Scene
from scipy.spatial import cKDTree

from ..bt7.export import Output, quat
from ..bt7.forms import unit
from ..panzer2f.build import skin_track
from .markings import mount
from .source import CREDIT, ID, Basis, primitive, read, repaint, wheels


def track(src, B, tag):
    # Retain the author's bevels, running face, sides and tread faces. The OBJ also duplicated
    # fourteen paper-thin alpha strips per track; they would become opaque in the mobile renderer.
    v = B.point(src.p)
    uv = src.uv.copy()
    ring = np.unique(np.round(v[np.abs(uv[:, :, 0] - 0.2694) < 0.00045, 1:], 6), axis=0)
    if len(ring) != 50:
        raise ValueError(("Unexpected belt station count", len(ring)))
    mid = (ring.min(0) + ring.max(0)) / 2
    order = np.argsort(np.arctan2(ring[:, 0] - mid[0], ring[:, 1] - mid[1]))
    ring = ring[order]
    k = np.flatnonzero((ring[:, 0] < 0.064) & (abs(ring[:, 1]) < 1))[0]
    ring = np.roll(ring, -k, axis=0)
    if ring[1, 1] < ring[0, 1]:
        ring = np.concatenate((ring[:1], ring[:0:-1]))
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.roll(ring, -1, axis=0) - ring, axis=1))]
    # Match the original metres-per-UV-repeat on the long straight. Snap to a whole number
    # of four-link tiles so the painted running surface never pops at the seam.
    index = cKDTree(ring).query(v[:, :, 1:].reshape(-1, 2))[1].reshape(len(v), 3)
    bottom = (v[:, :, 1] < 0.065).all(1)
    d = np.ptp(v[:, :, 2], axis=1)
    g = np.ptp(uv[:, :, 1], axis=1)
    ok = bottom & (d > 0.3) & (g > 0.6) & (g < 1.3)
    cycles = round(arc[-1] * np.median(g[ok] / d[ok]))
    per = arc[-1] / cycles
    phase = arc[index] / per
    seam = np.ptp(phase, axis=1) > cycles / 2
    phase[seam] = np.where(phase[seam] < cycles / 2, phase[seam] + cycles, phase[seam])
    uv[:, :, 1] = phase
    lower = (ring[:, 0] < 0.07) & (abs(ring[:, 1]) < 1.0)
    thick = float(np.median(ring[lower, 0]) - v[:, :, 1].min())
    return (
        primitive(v, B.normal(src.n), uv, "tread_" + tag),
        per,
        float(arc[-1]),
        cycles,
        thick,
    )


def gen(src, out):
    out.mkdir(parents=True, exist_ok=True)
    cfg = Path(__file__).resolve().parents[2] / "tanks" / ID
    for n in (
        "manifest.json",
        "tank.json",
        "weapon.json",
        "armor.json",
        "thumbnail.png",
    ):
        f = cfg / n
        if f.is_file() and f.resolve() != (out / n).resolve():
            shutil.copyfile(f, out / n)
    ps, images = read(src)
    B = Basis(ps)
    W, owner = wheels(ps, B)
    g = Output(images, "Pz4C", repaint)
    g.pos = []
    root = g.node("Hull")
    g.g.scenes = [Scene(nodes=[root])]
    g.g.scene = 0
    vr = ps[90000].p.reshape(-1, 3)
    ring = vr[abs(vr[:, 2] - vr[:, 2].min()) < 0.0002]
    yc = (ring.min(0) + ring.max(0)) / 2
    turret = g.node("Turret", root, B.point(yc))
    pivot = B.point([0.05946, -0.940, 1.9305])
    gun = g.node("Gun", turret, pivot)
    recoil = g.node("Barrel_Recoil", gun, pivot)

    def tip(ids):
        vs = np.concatenate([ps[i].p.reshape(-1, 3) for i in ids])
        fr = vs[vs[:, 1] < vs[:, 1].min() + 0.00036]
        val = (fr.min(0) + fr.max(0)) / 2
        val[1] -= 0.002
        return B.point(val)

    main = tip([140021])
    coax = tip([i for i in ps if i // 10000 == 1])
    mn = g.node("Muzzle_Main", recoil, main)
    cn = g.node("Muzzle_Coax_MG34", gun, coax)
    pieces = {root: [], turret: [], gun: [], recoil: []}
    raw = {}
    Bogs = []
    belts = {
        side: track(ps[i], B, side[0]) for side, i in [("left", 40000), ("right", 0)]
    }
    records = []
    occupied = {}
    bogienodes = {}
    for side in ("left", "right"):
        road = [w for w in W if w["side"] == side and w["roadWheel"]]
        for j in range(4):
            pair = road[j * 2 : j * 2 + 2]
            center = (pair[0]["center"] + pair[1]["center"]) / 2
            center[1] = B.point([0, 0, 0.425])[1]
            name = f"Bogie_{side[0]}_{j + 1:02d}"
            bn = g.node(name, root, center)
            pieces[bn] = []
            bogienodes[(side, j)] = bn
            Bogs.append(
                {
                    "name": name,
                    "node": bn,
                    "side": side,
                    "wheels": [w["name"] for w in pair],
                    "type": "paired leaf spring",
                }
            )
    for w in W:
        side = w["side"]
        cen = w["center"].copy()
        w["dy"] = 0
        if w["roadWheel"]:
            lower = min(ps[i].box[0][2] for i in w["sourceParts"])
            w["dy"] = belts[side][4] - B.point([0, 0, lower])[1]
            cen[1] += w["dy"]
        anchor = (
            g.node("Suspension_" + w["name"], root, cen) if w["roadWheel"] else root
        )
        node = g.node(w["name"], anchor, cen)
        pieces[node] = []
        for i in w["sourceParts"]:
            occupied[i] = node
        rec = {
            k: w[k]
            for k in ("name", "side", "wheelKind", "roadWheel", "sourceParts", "radius")
        }
        rec.update(node=node, center=cen.tolist())
        records.append(rec)
        if w["roadWheel"]:
            rec.update(suspensionNode=anchor, restLocalPosition=cen.tolist())
    for i, o in ps.items():
        if o.mesh in (0, 4, 3, 5, 8):
            continue  # old open-alpha stencils, already replaced by opaque-safe insignia
        node = root
        if o.mesh in (1, 14) or i == 90067:
            node = gun
        elif o.mesh == 9:
            node = turret
        if i in (60000, 140018, 140019, 140021):
            node = recoil
        v = B.point(o.p)
        n = B.normal(o.n)
        if i in occupied:
            w = owner[i]
            node = occupied[i]
            cen = w["center"]
            # Scale the wheel circumferences isotropically around the actual axle.
            f = B.sc[2] / B.sc[1]
            v[:, :, 2] = cen[2] + (v[:, :, 2] - cen[2]) * f
            n[:, :, 2] /= f
            n = unit(n)
            v[:, :, 1] += w["dy"]
        elif o.mesh in (10, 11, 12, 13) and 0.85 < abs(o.c[0]) < 1.05 and o.c[2] < 0.55:
            side = "left" if o.c[0] > 0 else "right"
            road = [w for w in W if w["side"] == side and w["roadWheel"]]
            pair_z = [
                np.mean([w["rawCenter"][1] for w in road[j * 2 : j * 2 + 2]])
                for j in range(4)
            ]
            j = int(np.argmin(np.abs(np.array(pair_z) - o.c[1])))
            if abs(pair_z[j] - o.c[1]) < 0.32 and o.span[1] < 0.75:
                node = bogienodes[side, j]
        p = primitive(v, n, o.uv, "atlas_" + str(o.atlas))
        if p is not None:
            pieces[node].append(p)
            raw[i] = p
    for node, ls in pieces.items():
        if ls:
            g.mesh(node, ls)

    def faces(p):
        return p.v[p.ix.reshape(-1, 3)]

    hullgeo = np.concatenate([faces(k) for k in pieces[root]])
    marked = []
    for name, ax, sign, pt, size in [
        ("Hull_Left", 0, -1, [0, -1.27, 1.40], 0.24),
        ("Hull_Right", 0, 1, [0, -1.27, 1.40], 0.24),
        ("Rear", 2, 1, [0.6, 2.1, 1.31], 0.205),
    ]:
        uv = [2, 1] if ax == 0 else [0, 1]
        parts, c, sz = mount(hullgeo, ax, sign, B.point(pt)[uv], size)
        nd = g.node("Balkenkreuz_" + name, root)
        g.mesh(nd, parts)
        marked.append(
            {
                "node": nd,
                "name": name,
                "axis": ax,
                "outward": sign,
                "placement": c,
                "size": sz,
            }
        )
    lengths = []
    periods = []
    for side in ("left", "right"):
        part, per, length, cycles, thick = belts[side]
        tn = g.node("track_" + side[0], root)
        g.mesh(tn, [part])
        skin_track(
            g,
            root,
            tn,
            [w for w in records if w["side"] == side and w["roadWheel"]],
            side[0],
        )
        g.g.skins[-1].name = "Pz4C_track_" + side
        lengths.append(length)
        periods.append(per)
    if abs(periods[0] - periods[1]) > 0.0001:
        raise ValueError("asymmetric belt UV repeat")
    times = np.linspace(0, 4, 49)
    g.clip(
        "Wheel_spin_1m_s",
        [
            (w["node"], "rotation", times, quat(0, -times / w["radius"]))
            for w in records
        ],
    )

    def motion(w):
        z = w["center"][2]
        pair = next(b for b in Bogs if w["name"] in b["wheels"])
        mid = g.pos[pair["node"]][2]
        return np.array(w["center"]) + np.stack(
            [
                0 * times,
                np.sin(times * np.pi / 2)
                * (
                    0.037 * np.sin(3.3 * times + mid * 2.3)
                    + 0.016 * np.sin(4.5 * times + z * 2.5)
                ),
                0 * times,
            ],
            axis=1,
        )

    g.clip(
        "Leaf_spring_pairs",
        [
            (w["suspensionNode"], "translation", times, motion(w))
            for w in records
            if w["roadWheel"]
        ],
    )
    t = np.arange(5.0)
    g.clip(
        "Turret_short_gun_and_recoil",
        [
            (turret, "rotation", t, quat(1, np.radians([0, 30, 0, -30, 0]))),
            (gun, "rotation", t, quat(0, np.radians([0, 18, 0, -9, 0]))),
            (
                recoil,
                "translation",
                [0, 1, 1.08, 1.4, 4],
                [[0, 0, 0], [0, 0, 0], [0, 0, 0.13], [0, 0, 0], [0, 0, 0]],
            ),
        ],
    )
    g.g.asset.extras = {
        **CREDIT,
        "coordinates": "metres, -Z forward, +Y up",
        "variant": "Panzer IV Ausf.C, short gun and coax only",
    }
    g.save(out / "model.glb")

    def box(v, org):
        v = v.reshape(-1, 3)
        lo = v.min(0)
        hi = v.max(0)
        return {"center": ((hi + lo) / 2 - org).tolist(), "size": (hi - lo).tolist()}

    hull = box(raw[110014].v, g.pos[root])
    h = hull["center"][1] + hull["size"][1] / 2
    hull["size"][1] = h
    hull["center"][1] = h / 2
    r = {
        "format": 1,
        "forward": "-Z",
        "turret": {"node": turret, "pivot": g.pos[turret].tolist(), "speedDegSec": 18},
        "gun": {
            "node": gun,
            "pivot": pivot.tolist(),
            "elevation": 20,
            "depression": 10,
            "recoil": 0.13,
            "recoilNode": recoil,
        },
        "muzzle": {"node": mn, "position": main.tolist()},
        "coaxMuzzle": {"node": cn, "position": coax.tolist()},
        "wheels": records,
        "bogies": Bogs,
        "tracks": ["track_l", "track_r"],
        "trackLoopMeters": float(np.mean(periods)),
        "trackAnimation": {
            "axis": "V",
            "physicalLoopMeters": lengths,
            "texturePeriodMeters": float(np.mean(periods)),
            "beltThickness": thick,
            "textureTilesPerLoop": cycles,
            "treadsPerTile": 4,
            "stationCountPerLoop": 50,
            "lowerRunDirection": "+Z",
        },
        "suspension": {
            "travel": 0.15,
            "restCompression": 0.075,
            "springPerWheel": 151200,
            "damperPerWheel": 6900,
            "totalMassKg": 18500,
            "contacts": 16,
        },
        "colliders": {
            "hull": hull,
            "turret": box(raw[90000].v, g.pos[turret]),
            "unit": {"center": [0, 1.34, 0], "size": [2.83, 2.68, 5.92]},
        },
        "markings": marked,
        "source": CREDIT,
        "sourceSha256": __import__("hashlib")
        .sha256(Path(src).read_bytes())
        .hexdigest(),
    }
    (out / "rig.json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n")
    return r


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--project", type=Path, required=True)
    a = p.parse_args()
    r = gen(a.source, a.project)
    print(
        len(r["wheels"]), "correctly bound wheels;", r["trackAnimation"], r["markings"]
    )
