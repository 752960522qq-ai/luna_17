"""Stage reserve vehicles with stock TimedEvent and transplant one intact enemy aircraft."""

import struct
from ...serialization import parse_complete, encode_complete
from ...unity_assets import pp
from ...campaign_ugui import PTR, require, write_calls
from .codec import part, update, cname

TIMES = {"wave2": 90.0, "relief": 150.0}
AIR = {"SO": (34823, "Ju87-G_AI", 78.0), "GE": (23066, "Il-2M3_AI", 135.0)}


def move_air(sf, side, group):
    g, name, _ = AIR[side.code]
    go = parse_complete(sf.objects[g])
    require(go["m_Name"] == name, "Wrong native enemy aircraft")
    tr = part(sf, g, "Transform")
    orig = parse_complete(sf.objects[tr])["m_Father"]["m_PathID"]
    dst = part(sf, group, "Transform")
    require(orig != dst, "Stock aircraft already in selected group")
    for p, include in ((orig, False), (dst, True)):
        v = parse_complete(sf.objects[p])
        a = v["m_Children"]
        update(
            sf, p, m_Children=a + [pp(tr)] if include else [c for c in a if c != pp(tr)]
        )
    update(sf, tr, m_Father=pp(dst))
    update(sf, g, m_IsActive=False)
    return g


def install(link, g, rows, base, side, air, timer):
    from .interface import event

    sf = link.sf
    timings = {**TIMES, "air": AIR[side.code][2]}
    events = {}
    # Put the clocks on the selected scenario itself. It starts only after stock GameControl
    # has selected that scenario. Reserve tanks have no collision, AI or renderers before then.
    for phase, seconds in timings.items():
        targets = [r["root"] for r in rows if r["phase"] == phase]
        if phase == "air":
            targets = [air]
        gate = []
        if phase == "relief":
            end = sf.objects[side.objective_control]
            er = bytearray(end.data or end.get_raw_data())
            er[12] = 0
            end.set_raw_data(bytes(er))
            collider = part(sf, base, "SphereCollider")
            update(sf, collider, m_Enabled=False)
            gate = [
                event(
                    side.objective_control,
                    "UnityEngine.Behaviour, UnityEngine.CoreModule",
                    "set_enabled",
                    6,
                    flag=True,
                ),
                event(
                    collider,
                    "UnityEngine.Collider, UnityEngine.PhysicsModule",
                    "set_enabled",
                    6,
                    flag=True,
                ),
            ]
        require(targets, "No targets for scheduled event")
        # A plain scene marker gives the HUD actual activation, not a second clock.
        marker = link.alloc()
        mt = link.alloc()
        gv = parse_complete(sf.objects[g])
        gv.update(
            m_Name="Hatch Phase " + phase,
            m_IsActive=False,
            m_Component=[{"component": pp(mt)}],
        )
        link.add(sf.objects[g], marker, encode_complete(sf.objects[g], gv))
        # Put indicators outside the four stock scenario children used by GameControl.
        anchor = part(sf, base, "Transform")
        rv = parse_complete(sf.objects[anchor])
        rv.update(
            m_GameObject=pp(marker),
            m_Father=pp(anchor),
            m_Children=[],
            m_LocalPosition={"x": 0.0, "y": 0.0, "z": 0.0},
        )
        link.add(sf.objects[anchor], mt, encode_complete(sf.objects[anchor], rv))
        v = parse_complete(sf.objects[anchor])
        update(sf, anchor, m_Children=v["m_Children"] + [pp(mt)])
        for root in targets:
            update(sf, root, m_IsActive=False)
        targets.append(marker)
        r = bytearray(timer.get_raw_data()[:32])
        PTR.pack_into(r, 0, 0, g)
        ff, p = PTR.unpack_from(r, 16)
        ext = timer.assets_file.externals[ff - 1]
        PTR.pack_into(r, 16, link.external(ext.path, ext), p)
        require(
            cname(timer, link.names) == "TimedEvent", "Missing original mission clock"
        )
        actions = write_calls([(i, True) for i in targets])
        r += (
            struct.pack("<fii", seconds, 1, len(targets) + len(gate))
            + actions[4:]
            + b"".join(gate)
        )
        tid = link.alloc()
        link.add(timer, tid, bytes(r))
        gv = parse_complete(sf.objects[g])
        update(sf, g, m_Component=gv["m_Component"] + [{"component": pp(tid)}])
        events[phase] = {
            "seconds": seconds,
            "targets": targets,
            "timer": tid,
            "marker": marker,
        }
    return dict(events=events, air_root=air, aircraft=AIR[side.code][1])
