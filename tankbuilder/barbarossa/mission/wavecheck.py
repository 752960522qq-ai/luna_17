"""Read the actual clock, aircraft and physical mesh bindings in the serialized release."""

from collections import Counter
import struct
from ...serialization import parse_complete as v
from ...unity_assets import read_mb
from ...enemy_assets import subtree
from ...campaign_ugui import require, PTR, write_calls
from .codec import cname, part, kids
from .waves import TIMES, AIR


def schedule(sf, stock, spec, side, names, enemy):
    from .interface import event

    s = spec["schedule"]
    air = s["air_root"]
    timing = {**TIMES, "air": AIR[side.code][2]}
    require(
        air in enemy
        and v(sf.objects[air])["m_Name"] == AIR[side.code][1]
        and not v(sf.objects[air])["m_IsActive"],
        "Wrong aircraft or side",
    )
    for ag, ps, at in subtree(stock, air):
        for p in ps:
            o = stock.objects[p]
            if o.type.name == "MonoBehaviour":
                require(
                    sf.objects[p].get_raw_data() == o.get_raw_data(),
                    "Altered plane AI, armament or affiliation",
                )
    for ph, delay in timing.items():
        ev = s["events"][ph]
        clk = sf.objects[ev["timer"]]
        r = clk.get_raw_data()
        targets = [u["root"] for u in spec["units"] if u["phase"] == ph]
        if ph == "air":
            targets = [air]
        gate = []
        if ph == "relief":
            gate = [
                event(
                    side.objective_control,
                    "UnityEngine.Behaviour, UnityEngine.CoreModule",
                    "set_enabled",
                    6,
                    flag=True,
                ),
                event(
                    part(sf, spec["base"], "SphereCollider"),
                    "UnityEngine.Collider, UnityEngine.PhysicsModule",
                    "set_enabled",
                    6,
                    flag=True,
                ),
            ]
        targets.append(ev["marker"])
        marker = v(sf.objects[ev["marker"]])
        require(
            not marker["m_IsActive"]
            and marker["m_Name"] == "Hatch Phase " + ph
            and cname(clk, names) == "TimedEvent"
            and r[12]
            and PTR.unpack_from(r) == (0, side.scenario)
            and struct.unpack_from("<fi", r, 32) == (delay, 1)
            and r[40:]
            == struct.pack("<i", len(targets) + len(gate))
            + write_calls([(i, True) for i in targets])[4:]
            + b"".join(gate)
            and targets == ev["targets"],
            "Wrong timed event: " + ph,
        )
    rows = spec["units"]
    require(
        v(sf.objects[spec["base"]])["m_IsActive"]
        and not sf.objects[side.objective_control].get_raw_data()[12]
        and Counter(u["phase"] for u in rows)
        == {"opening": 14, "wave2": 5, "relief": 2},
        "Wrong starting wave or early victory",
    )
    require(
        {u["lane"] for u in rows if u["phase"] == "wave2"} == {"west", "east"}
        and all(u["pos"][2] < -290 for u in rows if u["phase"] == "relief"),
        "Missing flank or rear approach",
    )
    return timing


def belts(sf, body):
    b = read_mb("BodyMove", sf.objects[body].get_raw_data())
    ids = []
    require(
        len(b["largeWheelLodTrfs"]) == 16 and len(b["smallWheelLodTrfs"]) == 12,
        "T26 runtime wheel layout mismatch",
    )
    for i, ref in enumerate(b["scrollLodRends"]):
        rr = v(sf.objects[ref["m_PathID"]])
        child = rr["m_GameObject"]["m_PathID"]
        parent = v(sf.objects[part(sf, child, "Transform")])["m_Father"]["m_PathID"]
        go = v(sf.objects[parent])["m_GameObject"]["m_PathID"]
        mf = v(sf.objects[part(sf, child, "MeshFilter")])["m_Mesh"]
        mesh = v(sf.objects[mf["m_PathID"]])
        require(
            mf["m_FileID"] == 0
            and rr["m_Enabled"]
            and kids(sf, go) == [child]
            and v(sf.objects[go])["m_Name"] == ("T26_Belt_L80", "T26_Belt_R80")[i]
            and mesh["m_IsReadable"]
            and mesh["m_KeepVertices"]
            and mesh["m_KeepIndices"]
            and mesh["m_VertexData"]["m_VertexCount"] == (32191, 32227)[i],
            "Unbound or immutable T26 mesh",
        )
        ids.append(mf["m_PathID"])
    require(len(set(ids)) == 2, "Left and right share geometry")
    return set(ids)
