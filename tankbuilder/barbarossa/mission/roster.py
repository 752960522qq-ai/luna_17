"""Mission staging in the existing fictional Polesie coordinate system (+Z north)."""

from math import hypot, atan2, degrees
from .. import layout as land

# Centre seeds on open ground. Each actor gets its own lane and legal ground position.
FORMATION = (
    ("player", "T26", [(-236, -285)]),
    ("friend", "T26", [(-257, -289), (-217, -289), (-276, -306), (-199, -307)]),
    ("friend", "BT7", [(-180, -250), (-159, -263), (-139, -278)]),
    ("friend", "T34_76", [(-282, -268), (-300, -285)]),
    ("enemy", "Panzer_IV_Ausf_C", [(-245, 179), (-219, 187)]),
    ("enemy", "Panzer_II_Ausf_F", [(-175, 126), (-153, 143), (-132, 155)]),
    ("enemy", "Panzer_III_J", [(-289, 139), (-312, 155), (-274, 159)]),
    ("enemy", "Panzer_38t", [(-201, 152), (-183, 166), (-162, 183)]),
)
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

    rows = []
    counts = {}
    for team, tank, seeds in FORMATION:
        for x, z in seeds:
            a, y, b = pick(x, z, positions)
            positions.append((a, b))
            v = counts.get((team, tank), 0) + 1
            counts[team, tank] = v
            enemy = team == "enemy"
            side = "GE" if enemy else "SO"
            lane = a
            targets = []
            if team != "player":
                # The same Vector3 waypoint array used by stock mission leaders.
                mid = 90 if enemy else -177
                for tx, tz in [(lane, mid), (lane, -8 if enemy else -84)]:
                    if team == "friend" and tank == "BT7" and v == 1 and tz == -84:
                        tx, tz = -181, -62
                    nx, ny, nz = pick(tx, tz)
                    targets.append([nx, 0.0, nz])
            aim = targets[0] if targets else [a, 0, b + 80]
            rows.append(
                dict(
                    team=team,
                    tank=tank,
                    id=f"{side}_{team}_{tank}_{v:02}",
                    pos=[a, round(y + 0.35, 4), b],
                    ground=y,
                    yaw=round(degrees(atan2(aim[0] - a, aim[2] - b)), 4),
                    route=targets,
                )
            )
    return rows
