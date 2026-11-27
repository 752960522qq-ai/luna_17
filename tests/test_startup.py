"""Validate startup declarations independently using the Android SDK's binary manifest reader."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from repack import patch_manifest

SOURCE = os.environ.get("HATCH_TEST_APK")
AAPT = os.environ.get("AAPT") or shutil.which("aapt")
LAUNCHER = "com.hatch.loader.HatchActivity"
RESTORE = "com.hatch.loader.HatchGameActivity"


def normalize(manifest):
    return patch_manifest(manifest, LAUNCHER, "突击坦克 · 舱盖",
                          ("com.unity3d.player.UnityPlayerActivity", "com.luna17.aot.ModActivity"), RESTORE)


def dump(xml):
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "manifest.apk"
        with zipfile.ZipFile(f, "w") as z: z.writestr("AndroidManifest.xml", xml)
        return subprocess.check_output([AAPT, "dump", "xmltree", f, "AndroidManifest.xml"], text=True)


class Manifest(unittest.TestCase):
    def test_single_launcher_and_restore_component(self):
        if not SOURCE or not AAPT:
            self.skipTest("use --source and --aapt for the binary manifest test")
        with zipfile.ZipFile(SOURCE) as z: old = z.read("AndroidManifest.xml")
        new = normalize(old)
        self.assertEqual(normalize(new), new)
        tree = dump(new)
        activities = re.findall(r"^      E: activity \(.*?(?=^      E:|\Z)", tree, flags=re.M | re.S)
        launcher, = [s for s in activities if '"' + LAUNCHER + '"' in s]
        restore, = [s for s in activities if '"' + RESTORE + '"' in s]
        self.assertEqual(tree.count('="android.intent.action.MAIN"'), 1)
        self.assertIn("android.intent.category.LAUNCHER", launcher)
        self.assertNotIn("E: intent-filter", restore)
        self.assertRegex(launcher, r'android:exported[^\n]*0xffffffff')
        self.assertRegex(restore, r'android:exported[^\n]*0x0\n')
        for name in ("configChanges", "screenOrientation", "launchMode"):
            attr = r"android:" + name + r"[^\n]+"
            self.assertEqual(re.search(attr, launcher)[0], re.search(attr, restore)[0])
        self.assertRegex(tree, r'="unity.auto-report-fully-drawn"[^\n]*\n[^\n]*0xffffffff')
        self.assertIn("unityplayer.UnityActivity", launcher)
        self.assertIn("unityplayer.UnityActivity", restore)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--aapt", default=AAPT)
    args, rest = p.parse_known_args()
    SOURCE, AAPT = args.source, args.aapt
    unittest.main(argv=["startup", *rest], verbosity=2)
