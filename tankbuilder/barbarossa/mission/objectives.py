"""Stock MissionEndControl stores two editor notes and independent gameplay flags."""

import struct
from ...campaign_ugui import PTR, read_string, require

# win: elimination, friendly arrival, stock reserved flag; loss: last ally, hostile arrival; marker mode.
ATTACK = ("味方到達時", (0, 1, 0), "自分以外全滅時", (1, 0), 6)
DEFEND = ("敵全滅時", (1, 0, 0), "敵到達時", (0, 1), 6)


def decode(raw):
    note, p = read_string(raw, 56)
    win = struct.unpack_from("<3i", raw, p)
    lose_note, p = read_string(raw, p + 12)
    lose = struct.unpack_from("<2i", raw, p)
    marker = struct.unpack_from("<i", raw, p + 8)[0]
    require(p + 12 == len(raw), "Unknown MissionEndControl tail")
    return note, win, lose_note, lose, marker


def bind(sf, side):
    # Run before pruning unused stock scenarios: the defence preset belongs to M1-2 SO.
    target = sf.objects[side.objective_control]
    a = target.get_raw_data()
    b = sf.objects[side.template_control].get_raw_data()
    require(
        PTR.unpack_from(a, 32) == PTR.unpack_from(b, 32) == (0, 155115)
        and PTR.unpack_from(a, 44) == PTR.unpack_from(b, 44) == (0, 155487),
        "Mission rules do not target this game's controller/HUD",
    )
    require(
        decode(b) == (DEFEND if side.code == "SO" else ATTACK),
        "Native attack/defence rule changed",
    )
    target.set_raw_data(
        a[:56] + b[56:]
    )  # Keep the actual side's Base, enabled flag, script and both manager bindings.
