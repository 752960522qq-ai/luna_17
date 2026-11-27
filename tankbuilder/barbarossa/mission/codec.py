"""Link native object graphs. References are read only from typed fields, not guessed from integers."""

import copy, struct
from ...campaign_ugui import PTR, require
from ...enemy_assets import refs
from ...serialization import assert_roundtrip, parse_complete, encode_complete
from ...unity_assets import pp, EditableObject, SCHEMA, read_mb, encode_value


def part(sf, g, typ):
    return next(
        c["component"]["m_PathID"]
        for c in parse_complete(sf.objects[g])["m_Component"]
        if sf.objects[c["component"]["m_PathID"]].type.name == typ
    )


def kids(sf, g):
    t = next(
        c["component"]["m_PathID"]
        for c in parse_complete(sf.objects[g])["m_Component"]
        if sf.objects[c["component"]["m_PathID"]].type.name
        in ("Transform", "RectTransform")
    )
    return [
        parse_complete(sf.objects[c["m_PathID"]])["m_GameObject"]["m_PathID"]
        for c in parse_complete(sf.objects[t])["m_Children"]
    ]


def update(sf, p, **kw):
    o = sf.objects[p]
    raw = encode_complete(o, dict(assert_roundtrip(o), **kw))
    if not isinstance(o, EditableObject):
        x = object.__new__(EditableObject)
        x.__dict__.update(o.__dict__)
        sf.objects[p] = o = x
    o.set_raw_data(raw)


def cname(o, names):
    return names[PTR.unpack_from(o.get_raw_data(), 16)[1]]


def i32(b, p):
    return struct.unpack_from("<i", b, p)[0]


# Unstripped fields checked against stock instances of the same components.
def extra_offsets(c, b):
    fixed = {
        "DriverControl": (32, 44, 56, 68),
        "MachineGun": (),
        "NetworkTransform": (),
        "NetworkObjectPrefabData": (),
        "UnitVisible": (),
        "ShellMove": (32, 44, 56, 68, 80, 92, 104, 124, 136, 148),
        "BombMove": (32, 44, 56, 68, 80, 92, 108, 120),
        "TrackPieceMove": (32, 56, 72, 84),
        "UnitDamage": (32, 44, 56, 68, 84, 96, 112, 124),
        "UnitDisplay": (32, 56),
        "UnitExposure": (32, 44, 56),
        "UnitNetwork": tuple(range(32, 140, 12)),
        "UnitSighting": (32, 44, 56, 68),
    }
    if c in fixed:
        return fixed[c]
    if c == "AIControl":
        n = i32(b, 92)
        require(n == 1, "Unexpected launcher count")
        return (32, 44, 56, 68, 80, 96, 108, 120, 132, 144, 264 + 12 * i32(b, 200))
    if c == "ShaderControl":
        n = i32(b, 32)
        require(36 + 12 * n == len(b), "Shader binding shape")
        return tuple(range(36, len(b), 12))
    if c == "RealTrackMove":
        n = i32(b, 52)
        require(60 + 12 * n == len(b), "Track binding shape")
        return (32, *range(56, 56 + 12 * n, 12))
    if c == "NetworkObject":
        n = i32(b, 48)
        require(56 + 12 * n == len(b), "NetworkBehaviour list shape")
        return tuple(range(52, 52 + 12 * n, 12))
    raise ValueError("No reviewed component codec: " + c)


class Linker:
    def __init__(self, sf, names):
        self.sf = sf
        self.names = names
        self.next = max(sf.objects) + 1
        self.byfile = {e.path: i for i, e in enumerate(sf.externals, 1)}
        self.types = {}
        for i, t in enumerate(sf.types):
            self.types[self.key(t)] = i

    @staticmethod
    def key(t):
        return (t.class_id, t.script_id, t.old_type_hash)

    def alloc(self):
        p = self.next
        self.next += 1
        return p

    def external(self, path, orig=None):
        if path not in self.byfile:
            sample = orig or next(
                e for e in self.sf.externals if e.path == "resources.assets"
            )
            e = copy.copy(sample)
            e.path = path
            self.sf.externals.append(e)
            self.byfile[path] = len(self.sf.externals)
        return self.byfile[path]

    def mapper(self, src, fn, ids):
        def link(p):
            f, i = p["m_FileID"], p["m_PathID"]
            if not i:
                return pp()
            if f == 0 and i in ids:
                return pp(ids[i])
            if f == 0:
                require(i in src.objects, f"Broken source {fn}:{i}")
                return pp(i, self.external(fn))
            ext = src.externals[f - 1]
            return pp(i, self.external(ext.path, ext))

        return link

    def add(self, o, p, raw):
        sf = self.sf
        typ = o.serialized_type
        k = self.key(typ)
        if k not in self.types:
            # MonoBehaviour types additionally refer to MonoScript entries by index.
            nt = copy.copy(typ)
            if typ.class_id == 114 and typ.script_type_index >= 0:
                s = o.assets_file.script_types[typ.script_type_index]
                sfid = s.local_serialized_file_index
                require(sfid > 0, "Unexpected local MonoScript")
                e = o.assets_file.externals[sfid - 1]
                fid = self.external(e.path, e)
                i = next(
                    (
                        i
                        for i, x in enumerate(sf.script_types)
                        if x.local_serialized_file_index == fid
                        and x.local_identifier_in_file == s.local_identifier_in_file
                    ),
                    None,
                )
                if i is None:
                    x = copy.copy(s)
                    x.local_serialized_file_index = fid
                    i = len(sf.script_types)
                    sf.script_types.append(x)
                nt.script_type_index = i
            self.types[k] = len(sf.types)
            sf.types.append(nt)
        idx = self.types[k]
        x = object.__new__(EditableObject)
        x.__dict__.update(o.__dict__)
        x.assets_file = sf
        x.path_id = p
        x.type_id = idx
        x.serialized_type = sf.types[idx]
        x.set_raw_data(raw)
        sf.objects[p] = x
        return x

    def behaviour(self, o, link, team=None, route=None):
        raw = o.get_raw_data()
        b = bytearray(raw)
        c = cname(o, self.names)
        if c in SCHEMA:
            v = refs(read_mb(c, raw), link)
            if c == "UnitStatus" and team:
                v["iFFNum"] = {"player": 0, "friend": 1, "enemy": 2}[team]
            b[32:] = b"".join(encode_value(f, v[f["name"]]) for f in SCHEMA[c])
            offsets = (0, 16)
        else:
            offsets = (0, 16, *extra_offsets(c, raw))
        for at in offsets:
            f, i = PTR.unpack_from(raw, at)
            v = link(pp(i, f))
            PTR.pack_into(b, at, v["m_FileID"], v["m_PathID"])
        if c == "AIControl" and route is not None:
            n = i32(b, 200)
            require(len(b) == 312 + 12 * n, "Unsupported stock AI waypoint format")
            b[200 : 204 + 12 * n] = struct.pack("<i", len(route)) + b"".join(
                struct.pack("<3f", *q) for q in route
            )
            struct.pack_into(
                "<i", b, 188, 1
            )  # Stock campaign leader's movement switch.
        return bytes(b)
