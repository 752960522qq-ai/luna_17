"""Mission staging in the existing fictional Polesie coordinate system (+Z north)."""

from math import hypot, atan2, degrees
from .. import layout as land

# Stable physical positions for both choices. Germany attacks from the northern fields;
# the Soviet player and garrison start near their village entrance, not across the map.
FORMATION = (
    ("SO", "T26", [(-211, -73), (-237, -89), (-158, -78), (-266, -108), (-133, -109)]),
    ("SO", "BT7", [(-109, -141), (-255, -151), (-302, -126)]),
    ("SO", "T34_76", [(-228, -345), (-148, -330)]),
    ("GE", "Panzer_IV_Ausf_C", [(-245, 554), (-219, 562)]),
    ("GE", "Panzer_II_Ausf_F", [(-175, 501), (-153, 518), (-132, 530)]),
    ("GE", "Panzer_III_J", [(-289, 514), (-312, 530), (-274, 534)]),
    ("GE", "Panzer_38t", [(-201, 527), (-183, 541), (-162, 558)]),
)
# Distinct approaches enter the native 15 m trigger; support units stop outside it.
CAPTURE = {
    ("Panzer_IV_Ausf_C", 1): (-191, -54),
    ("Panzer_II_Ausf_F", 1): (-178, -56),
    ("Panzer_II_Ausf_F", 2): (-173, -52),
    ("Panzer_III_J", 1): (-186, -56),
    ("Panzer_38t", 1): (-179, -51),
}
# Local defensive stations, kept distinct even if scenery nudges their authored centres.
STATIONS = {
    "T26": [(-210, -56), (-244, -72), (-156, -54), (-268, -86), (-122, -85)],
    "BT7": [(-111, -100), (-254, -95), (-272, -109)],
    "T34_76": [(-220, -100), (-171, -84)],
}
# Unit-centre clearance, including the vehicle footprint. Decor without collision is excluded.
RADIUS = dict(
    barn=14,
    cottage_lime=11,
    cottage_log=11,
    cottage_shingle=11,
    shed=9,
    fence=10,
    haystack=6,
    well=6,
    windmill=13,
    broadleaf=6,
    pine=5,
    orchard_tree=5,
)


def stage(h, props):
    positions = []

    def pick(x, z, others=()):
        offsets = sorted(
            ((dx, dz) for dx in range(-32, 33, 4) for dz in range(-32, 33, 4)),
            key=lambda a: (a[0] * a[0] + a[1] * a[1], a),
        )
        for dx, dz in offsets:
            a, b = x + dx, z + dz
            ground = float(land.ground(h, a, b))
            if min(ground, float(land.shore(a, b))) < 10:
                continue
            if any(hypot(a - c, b - d) < 14 for c, d in others):
                continue
            if any(
                hypot(a - p["x"], b - p["z"]) < RADIUS[p["kind"]] * p["scale"] + 3
                for p in props
                if p["kind"] in RADIUS
            ):
                continue
            gradient = max(
                abs(float(land.ground(h, a + ox, b + oz)) - ground)
                for ox, oz in ((3, 0), (-3, 0), (0, 3), (0, -3))
            )
            if gradient > 0.72:
                continue
            return a, round(ground, 4), b
        raise ValueError(f"No clear deployment square near {(x, z)}")

    from . import OBJECTIVE_XZ
    from math import dist

    rows = []
    stations = []
    for nation, tank, seeds in FORMATION:
        for v, (x, z) in enumerate(seeds, 1):
            a, y, b = pick(x, z, positions)
            positions.append((a, b))
            if nation == "GE":
                qx, qz = CAPTURE.get((tank, v), (a, -18 if v % 2 else -26))
                wing = (
                    ("west" if tank == "Panzer_III_J" else "east")
                    if tank in ("Panzer_III_J", "Panzer_IV_Ausf_C")
                    else None
                )
                if wing:
                    lane = (-353 if wing == "west" else -71) + 8 * (v - 1)
                    targets = [pick(lane, 330), pick(lane, 86), pick(qx, qz)]
                else:
                    targets = [pick(a, 310), pick(a, 80), pick(qx, qz)]
                if (tank, v) in CAPTURE and dist(
                    (targets[-1][0], targets[-1][2]), OBJECTIVE_XZ
                ) >= 13:
                    raise ValueError("Attack waypoint outside the village objective")
            else:
                gx, gz = STATIONS[tank][v - 1]
                q = pick(gx, gz, stations)
                stations.append((q[0], q[2]))
                targets = [q]
            aim = (targets[0][0], targets[0][2]) if nation == "GE" else (a, b + 50)
            rows.append(
                dict(
                    nation=nation,
                    phase=(
                        "relief"
                        if tank == "T34_76"
                        else "wave2"
                        if nation == "GE" and wing
                        else "opening"
                    ),
                    lane=(wing if nation == "GE" else None),
                    tank=tank,
                    id=f"{nation}_{tank}_{v:02}",
                    pos=[a, round(y + 0.35, 4), b],
                    ground=y,
                    yaw=round(degrees(atan2(aim[0] - a, aim[1] - b)), 4),
                    route=[[tx, 0.0, tz] for tx, _, tz in targets],
                )
            )
    return rows


def perspective(deployment, side):
    # 'nation' is physical ownership. 'team' is the player's view and may reverse.
    rows = []
    for u in deployment:
        role = (
            "player"
            if u["id"] == side.player_id
            else ("friend" if u["nation"] == side.code else "enemy")
        )
        rows.append(
            dict(u, team=role, route=[] if role == "player" else list(u["route"]))
        )
    return rows
