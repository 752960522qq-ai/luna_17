"""Exercise the actual game Activity with the same entry used after task restore."""

import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOUBLES = {
    "android/os/Bundle.java": "package android.os; public class Bundle {}",
    "android/content/Intent.java": "package android.content; public class Intent {}",
    "com/unity3d/player/UnityPlayerActivity.java": """package com.unity3d.player;
        public class UnityPlayerActivity {
            public static Runnable onUnityCreate;
            protected void onCreate(android.os.Bundle b) { onUnityCreate.run(); }
            protected void onDestroy() {}
            protected void onActivityResult(int r, int c, android.content.Intent i) {}
        }""",
    "com/hatch/loader/HatchLoader.java": """package com.hatch.loader;
        final class HatchLoader {
            static boolean ready, attempted, startCalled;
            static int preparations;
            static String prepareForUnity(Object a) {
                attempted = true;
                if (!ready) { ready = true; preparations++; }
                return null;
            }
            static void start(Object a) { startCalled = true; }
            static boolean result(Object a,int r,int c,android.content.Intent i) { return false; }
            static void stop() {}
        }""",
    "com/hatch/loader/RestoreRun.java": """package com.hatch.loader;
        public class RestoreRun {
            public static void main(String[] args) {
                if (args[0].equals("launcher")) HatchLoader.prepareForUnity(new Object());
                com.unity3d.player.UnityPlayerActivity.onUnityCreate = () -> {
                    if (!HatchLoader.attempted || !HatchLoader.ready)
                        throw new AssertionError("Unity created before prerequisite preparation");
                };
                new HatchGameActivity().onCreate(new android.os.Bundle());
                if (!HatchLoader.startCalled || HatchLoader.preparations != 1)
                    throw new AssertionError("Missing module start or duplicated preparation");
            }
        }""",
}


class TaskRestore(unittest.TestCase):
    def test_cold_task_restore_and_launcher(self):
        java = ["java", "com.sun.tools.javac.Main", "-source", "8", "-target", "8", "-Xlint:-options"]
        with tempfile.TemporaryDirectory() as tmp:
            dest = pathlib.Path(tmp)
            for name, source in DOUBLES.items():
                path = dest / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source)
            actual = ROOT / "loader/src/com/hatch/loader/HatchGameActivity.java"
            subprocess.run([*java, "-d", tmp, actual, *dest.rglob("*.java")], check=True)
            for entry in ("restored-task", "launcher"):
                with self.subTest(entry=entry):
                    subprocess.run(
                        ["java", "-cp", tmp, "com.hatch.loader.RestoreRun", entry], check=True
                    )


if __name__ == "__main__":
    unittest.main()
