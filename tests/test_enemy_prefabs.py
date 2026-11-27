"""Opt-in regression checks on the *emitted* 5.1.0 assets (no APK build)."""

import argparse
import json
import struct
import tempfile
import unittest
from pathlib import Path

import UnityPy

from tankbuilder.enemy_assets import script_class
from tankbuilder.enemy_verify import verify
from tankbuilder.serialization import apply_reviewed_typetrees
from tankbuilder.unity_assets import Adapter, read_mb, write_mb


class EnemyPrefabRegression(unittest.TestCase):
    source = staged = None

    @classmethod
    def setUpClass(cls):
        if not cls.source or not cls.staged:
            raise unittest.SkipTest("requires the source data.unity3d and previously staged assets")
        cls.base = Adapter(cls.source)
        entries = json.loads((cls.staged / "Hatch-Enemy-AI-index.json").read_text())["prefabs"]
        cls.entry = next(e for e in entries if e["id"] == "T26")

    def check_mutation(self, class_name, mutate, error):
        path = self.staged / self.entry["file"]
        env = UnityPy.load(str(path))
        apply_reviewed_typetrees(env)
        sf = next(iter(env.files.values()))
        candidates = [
            o
            for o in sf.objects.values()
            if o.type.name == "MonoBehaviour" and script_class(self.base, o) == class_name
        ]
        self.assertEqual(len(candidates), 1)
        mutate(sf, candidates[0])
        with tempfile.TemporaryDirectory() as d:
            damaged = Path(d) / path.name
            damaged.write_bytes(sf.save())
            with self.assertRaisesRegex(ValueError, error):
                verify(self.base, damaged, self.entry)

    def test_friendly_allegiance_is_rejected(self):
        def friendly(_, status):
            values = read_mb("UnitStatus", status.get_raw_data())
            values["iFFNum"] = 1
            write_mb(status, "UnitStatus", values)

        self.check_mutation("UnitStatus", friendly, "enemy identity")

    def test_stock_instead_of_instance_muzzle_is_rejected(self):
        def wrong_owner(sf, launcher):
            # This PPtr resolves successfully, but it points at the donor asset instead of the spawned tank.
            v = read_mb("Launcher", launcher.get_raw_data())
            go = sf.objects[v["shellApGos"][0]["m_PathID"]]
            from tankbuilder.serialization import parse_complete

            shot = next(
                sf.objects[r["component"]["m_PathID"]]
                for r in parse_complete(go)["m_Component"]
                if sf.objects[r["component"]["m_PathID"]].type.name == "MonoBehaviour"
                and script_class(self.base, sf.objects[r["component"]["m_PathID"]]) == "ShellMove"
            )
            raw = bytearray(shot.get_raw_data())
            stock = next(i + 1 for i, e in enumerate(sf.externals) if e.path == "resources.assets")
            struct.pack_into("<i", raw, 44, stock)
            shot.set_raw_data(bytes(raw))

        self.check_mutation("Launcher", wrong_owner, "projectile mount/owner collider")

    def test_shared_track_renderer_is_rejected(self):
        def duplicate(_, body):
            v = read_mb("BodyMove", body.get_raw_data())
            v["scrollLodRends"][1] = v["scrollLodRends"][0]
            write_mb(body, "BodyMove", v)

        self.check_mutation("BodyMove", duplicate, "track renderer")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", required=True, type=Path)
    p.add_argument("--staged", required=True, type=Path)
    args = p.parse_args()
    EnemyPrefabRegression.source = args.data
    EnemyPrefabRegression.staged = args.staged
    unittest.main(argv=["test_enemy_prefabs"], verbosity=2)
