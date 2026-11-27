"""Stage one independent SerializedFile against the 5.1.0 game dependencies."""

import copy
import struct
from collections import defaultdict

from .serialization import assert_roundtrip, encode_complete, parse_complete
from .unity_assets import SCHEMA, EditableObject, pp, read_mb, write_mb, xyz


def refs(tree, change):
    if isinstance(tree, dict):
        if set(tree) == {"m_FileID", "m_PathID"}:
            return change(tree)
        return {k: refs(v, change) for k, v in tree.items()}
    if isinstance(tree, (tuple, list)):
        return [refs(v, change) for v in tree]
    return tree


def script_class(adapter, o):
    r = struct.unpack_from("<iq", o.get_raw_data(), 16)
    sf = adapter.sf
    f = sf.name if not r[0] else sf.externals[r[0] - 1].path.rsplit("/", 1)[-1]
    return adapter.scripts[f, r[1]]


def subtree(sf, gid):
    todo = [gid]
    seen = set()
    while todo:
        g = todo.pop()
        if g in seen:
            raise ValueError("Cycle or duplicate child in stock prefab")
        seen.add(g)
        ps = [j["component"]["m_PathID"] for j in parse_complete(sf.objects[g])["m_Component"]]
        tr = next(p for p in ps if sf.objects[p].type.name == "Transform")
        yield g, ps, tr
        for x in parse_complete(sf.objects[tr])["m_Children"]:
            todo.append(parse_complete(sf.objects[x["m_PathID"]])["m_GameObject"]["m_PathID"])


class Stage:
    def __init__(self, a, root, name, he_donor, *, player=False):
        self.a = a
        self.base = a.sf
        self.root = root
        self.sf = copy.copy(a.sf)
        self.sf.objects = {}
        self.sf.name = name
        self.sf.types = list(a.sf.types)
        self.sf.externals = list(a.sf.externals)
        self.sf.externals.append(
            copy.copy(next(e for e in a.files["level8"].externals if e.path == "resources.assets"))
        )
        self.stock = len(self.sf.externals)
        self.next_id = max(a.sf.objects) + 1
        self.templates = {}
        self.parts = defaultdict(list)
        self.nodes = list(subtree(self.base, root))
        self.owned = set()
        for g, ps, _ in self.nodes:
            self.owned.update([g, *ps])
            for p in ps:
                o = self.base.objects[p]
                kind = script_class(a, o) if o.type.name == "MonoBehaviour" else o.type.name
                self.parts[kind].append(p)
        controllers = ("PlayerControl",) if player else ("AIControl", "DriverControl")
        for kind in (*controllers, "UnitStatus", "BodyMove", "TurretMove", "Launcher"):
            if len(self.parts[kind]) != 1:
                raise ValueError(f"{name}: expected one {kind}")
        if self.parts["AIControl" if player else "PlayerControl"]:
            raise ValueError("Unexpected controller on stock vehicle")
        self.launch = self.parts["Launcher"][0]
        self.added_shells = []
        self.fixes = {}
        cur = read_mb("Launcher", self.base.objects[self.launch].get_raw_data())
        self.fire = cur["thisTrf"]["m_PathID"]
        if he_donor and not cur["shellHeGos"]:
            donor = read_mb("Launcher", self.base.objects[he_donor].get_raw_data())
            oldfire = donor["thisTrf"]["m_PathID"]
            # Preserve this vehicle's own stock collision exclusion. Some use their turret, others the hull.
            shot = cur["shellApGos"][0]["m_PathID"]
            shot_parts = next(subtree(self.base, shot))[1]
            sm = next(
                self.base.objects[p]
                for p in shot_parts
                if self.base.objects[p].type.name == "MonoBehaviour"
                and script_class(a, self.base.objects[p]) == "ShellMove"
            )
            fid, box = struct.unpack_from("<iq", sm.get_raw_data(), 92)
            if fid or box not in self.parts["BoxCollider"]:
                raise ValueError("Invalid stock projectile collision exclusion")
            for r in donor["shellHeGos"]:
                g = r["m_PathID"]
                self.added_shells.append(g)
                for y, ps, tr in subtree(self.base, g):
                    if y in self.owned:
                        raise ValueError("HE donor overlaps the tank")
                    self.owned.update([y, *ps])
                    for p in ps:
                        o = self.base.objects[p]
                        if o.type.name != "MonoBehaviour" or script_class(a, o) != "ShellMove":
                            continue
                        raw = o.get_raw_data()
                        before = struct.unpack_from("<iq", raw, 44)
                        owner = struct.unpack_from("<iq", raw, 92)
                        if (
                            before != (0, oldfire)
                            or owner[0]
                            or self.base.objects[owner[1]].type.name != "BoxCollider"
                        ):
                            raise ValueError("HE pool binding changed")
                        self.fixes[p] = {44: self.fire, 92: box}
        self.owned.update(
            x.local_identifier_in_file
            for x in self.sf.script_types
            if x.local_serialized_file_index == 0 and x.local_identifier_in_file in self.base.objects
        )
        # Keep opaque behaviour payloads unchanged. Include any possible outgoing local dependency,
        # including harmless scalar coincidences, instead of patching integers that resemble PPtrs.
        processed = set()
        todo = list(self.owned)
        while todo:
            p = todo.pop()
            if p in processed:
                continue
            processed.add(p)
            o = self.base.objects[p]
            if o.type.name != "MonoBehaviour" or script_class(a, o) in SCHEMA:
                continue
            raw = self.opaque(p)
            for off in range(32, len(raw) - 11, 4):
                f, i = struct.unpack_from("<iq", raw, off)
                if f or not i or i in self.owned or i not in self.base.objects:
                    continue
                typ = self.base.objects[i].type.name
                if typ == "GameObject":
                    extra = {z for g, ps, tr in subtree(self.base, i) for z in (g, *ps)}
                elif typ in ("Material", "Mesh", "AudioClip", "Texture2D"):
                    extra = {i}
                else:
                    raise ValueError(
                        f"Unreviewed opaque external reference {script_class(a, o)} -> {typ}:{i}"
                    )
                todo.extend(extra - self.owned)
                self.owned.update(extra)
        for p in sorted(self.owned):
            o = self.base.objects[p]
            kind = o.type.name
            self.copy(p, o, o.get_raw_data())
            if kind == "MonoBehaviour":
                cls = script_class(a, o)
                if cls in SCHEMA:
                    self.set_mb(p, cls, refs(read_mb(cls, o.get_raw_data()), self.redirect))
                else:
                    self.sf.objects[p].set_raw_data(self.opaque(p))
            else:
                tree = assert_roundtrip(o)
                self.put(p, refs(tree, self.redirect))
        if self.added_shells:
            launch = self.mb(self.launch, "Launcher")
            launch["shellHeGos"] = [pp(i) for i in self.added_shells]
            self.set_mb(self.launch, "Launcher", launch)
            for sh in self.added_shells:
                tr = self.tr(sh)
                self.attach(tr, self.fire, (0, 0, 0, 0, 0, 0, 1, 1, 1, 1))
                g = self.get(sh)
                g["m_IsActive"] = False
                self.put(sh, g)

    def opaque(self, p):
        data = bytearray(self.base.objects[p].get_raw_data())
        for o, i in self.fixes.get(p, {}).items():
            struct.pack_into("<iq", data, o, 0, i)
        return bytes(data)

    def redirect(self, p):
        return (
            pp(p["m_PathID"], self.stock)
            if p["m_FileID"] == 0 and p["m_PathID"] and p["m_PathID"] not in self.owned
            else p
        )

    def copy(self, i, src, raw):
        o = object.__new__(EditableObject)
        o.__dict__.update(src.__dict__)
        o.assets_file = self.sf
        o.path_id = i
        o.set_raw_data(raw)
        self.sf.objects[i] = o
        return i

    def template(self, kind):
        if kind not in self.templates:
            self.templates[kind] = assert_roundtrip(self.a.templates[kind])
        return copy.deepcopy(self.templates[kind])

    def standard_material(self):
        if "Standard" not in self.templates:
            t = assert_roundtrip(self.base.objects[1])
            p = t["m_Shader"]
            shader = self.base.objects[p["m_PathID"]]
            # Inspect only the name. Leave the original compiled shader external and byte-for-byte untouched.
            if (
                p["m_FileID"]
                or shader.read_typetree(check_read=False)["m_ParsedForm"]["m_Name"] != "Standard"
            ):
                raise ValueError("Stock Standard shader changed")
            t["m_Shader"] = pp(shader.path_id, self.stock)
            self.templates["Standard"] = t
        return copy.deepcopy(self.templates["Standard"])

    def make(self, kind, tree):
        if kind not in self.a.templates:
            self.a.templates[kind] = next(o for o in self.base.objects.values() if o.type.name == kind)
        o = self.a.templates[kind]
        if o.assets_file is not self.base:
            raise ValueError("Template is not from resources.assets: " + kind)
        i = self.next_id
        self.next_id += 1
        self.copy(i, o, encode_complete(o, tree))
        return i

    def get(self, i):
        return parse_complete(self.sf.objects[i])

    def put(self, i, t):
        o = self.sf.objects[i]
        o.set_raw_data(encode_complete(o, t))

    def mb(self, i, c):
        return read_mb(c, self.sf.objects[i].get_raw_data())

    def set_mb(self, i, c, t):
        write_mb(self.sf.objects[i], c, t)

    def tr(self, go):
        return next(
            p["component"]["m_PathID"]
            for p in self.get(go)["m_Component"]
            if self.sf.objects[p["component"]["m_PathID"]].type.name == "Transform"
        )

    def go(self, tr):
        return self.get(tr)["m_GameObject"]["m_PathID"]

    def attach(self, tr, parent, trs):
        t = self.get(tr)
        old = t["m_Father"]
        old_pid = old["m_PathID"]
        if old_pid and old["m_FileID"] == 0 and old_pid != parent:
            op = self.get(old_pid)
            op["m_Children"] = [r for r in op["m_Children"] if r != pp(tr)]
            self.put(old_pid, op)
        t.update(
            m_Father=pp(parent),
            m_LocalPosition=xyz(trs[:3]),
            m_LocalRotation=dict(zip("xyzw", trs[3:7])),
            m_LocalScale=xyz(trs[7:]),
        )
        self.put(tr, t)
        pt = self.get(parent)
        if pp(tr) not in pt["m_Children"]:
            pt["m_Children"].append(pp(tr))
            self.put(parent, pt)

    def node(self, name, layer):
        gt = self.template("GameObject")
        gt.update(m_Name=name, m_Component=[], m_Tag=0, m_Layer=layer, m_IsActive=True)
        g = self.make("GameObject", gt)
        tt = self.template("Transform")
        tt.update(m_GameObject=pp(g), m_Father=pp(), m_Children=[])
        tr = self.make("Transform", tt)
        gt["m_Component"] = [{"component": pp(tr)}]
        self.put(g, gt)
        return g, tr
