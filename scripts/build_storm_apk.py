#!/usr/bin/env python3
"""Sign the verified Stormbreak fields and real weather recordings over the cumulative base."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assemble_campaign_apk import CAT, DATA
from update_campaign_loader import CERT, digest, repack_apk, verify_apk
from tankbuilder.barbarossa.storm.restore import FILES, sha

STREAM = "assets/bin/Data/StormWeather.resource"
CREDITS = "assets/Hatch/licenses/Storm-Recordings.txt"


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def run(*cmd, env=None):
    return subprocess.check_output(cmd, env=env, text=True)


def verified_signer(cmd, apk):
    text = run(*cmd, "verify", "--verbose", "--print-certs", apk)
    check(f"certificate SHA-256 digest: {CERT}" in text, "APK signer differs from the project's")
    check("Verified using v3 scheme (APK Signature Scheme v3): true" in text, "Missing valid v3 signature")
    v2 = run(*cmd, "verify", "--verbose", "--min-sdk-version", "24", "--max-sdk-version", "27", apk)
    check("Verified using v2 scheme (APK Signature Scheme v2): true" in v2, "Missing valid v2 signature")
    return text


def build(a):
    check(a.apk.resolve() != a.out.resolve(), "Output must not replace the base APK")
    check(sha(a.cert) == CERT, "Expected the existing Hatch signing certificate")
    signer = ("java", "-cp", a.apksigner, "com.android.apksigner.ApkSignerTool")
    verified_signer(signer, a.apk)
    with zipfile.ZipFile(a.kit) as k:
        old = json.loads(k.read("integration.json"))
    check(sha(a.apk) == old["base_apk_sha256"], "Wrong base APK for the two-mission kit")
    new = json.loads((a.assets / "integration.json").read_bytes())
    report = json.loads((a.assets / "verification.json").read_bytes())
    campaign = json.loads((a.assets / "campaign.json").read_bytes())
    resource = a.assets / "data.unity3d"
    ids = {code: s["index"] for code, s in campaign["second"]["sides"].items()}
    check(
        new["base_sha256"] == old["base_sha256"]
        and report["status"] == "passed" and report["matchesResourceSHA256"] == new["result_sha256"] == sha(resource)
        and ids == {"SO": 24, "GE": 25}
        and campaign["weatherAudio"] == "field-recordings" and campaign["weatherCredits"] == CREDITS
        and all(s["audibleBanksDecoded"] == 3 for s in report["missions"].values()),
        "Only a verified two-faction recorded storm build can be signed",
    )
    updates = {DATA: resource.read_bytes(), STREAM: (a.assets / "StormWeather.resource").read_bytes()}
    for name in FILES:
        if name == STREAM or name.startswith("AI/"):
            continue  # The AI prefab index is an editor manifest; the prefab assets are in data.unity3d.
        local = a.runtime / name
        check(sha(local) == old["staged_files"][name], f"Unverified staged file: {name}")
        updates[name] = local.read_bytes()
    updates[CREDITS] = (ROOT / "tankbuilder/barbarossa/storm/RECORDINGS.txt").read_bytes()
    with zipfile.ZipFile(a.apk) as base:
        check(digest(base, DATA) == new["base_sha256"], "The original UnityFS entry changed")
        oldmods = json.loads(base.read(CAT))["mods"]
        mods = json.loads(updates[CAT])["mods"]
        by_id = {m["id"]: m for m in mods}
        check(len(by_id) == len(mods) and all(by_id[m["id"]] == m for m in oldmods), "An existing module was changed")
        check(set(by_id) - {m["id"] for m in oldmods} == {"T28", "Panzer_III_Ausf_F"}, "Missing new vehicles")
        for mod in mods:
            name = "assets/Hatch/mods/" + mod["id"] + ".hatch"
            h = hashlib.sha256(updates[name]).hexdigest() if name in updates else digest(base, name)
            check(h == mod["sha256"], f"Hatch catalog mismatch: {mod['id']}")
        added = {n: zipfile.ZIP_DEFLATED if n == CREDITS else zipfile.ZIP_STORED
                 for n in sorted(set(updates) - set(base.namelist()))}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=a.work, prefix="storm-sign-") as folder:
        unsigned = Path(folder) / "unsigned.apk"
        tmp_signed = Path(folder) / "signed.apk"
        print("Repacking the two missions, the Hatch catalog and the sound stream", flush=True)
        repack_apk(a.apk, unsigned, updates, added=added)
        subprocess.run([
            *signer, "sign", "--key", a.key, "--cert", a.cert,
            "--min-sdk-version", "28", "--v1-signing-enabled", "false",
            "--v2-signing-enabled", "true", "--v3-signing-enabled", "true", "--v4-signing-enabled", "false",
            "--alignment-preserved", "true", "--out", tmp_signed, unsigned,
        ], check=True)
        unsigned.unlink()
        message = verified_signer(signer, tmp_signed)
        print("Verified v2/v3 signatures; comparing APK entries and Android manifest", flush=True)
        verify_apk(a.apk, tmp_signed, updates, added=added)
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(a.aapt.resolve().parent / "lib64")
        subprocess.run([a.zipalign, "-c", "-P", "16", "4", tmp_signed], env=env, check=True)
        prefixes = ("package:", "sdkVersion:", "targetSdkVersion:", "launchable-activity:", "native-code:")
        baseline = run(a.aapt, "dump", "badging", a.apk, env=env).splitlines()
        actual = run(a.aapt, "dump", "badging", tmp_signed, env=env).splitlines()
        expected = [line for line in baseline if line.startswith(prefixes)]
        check([line for line in actual if line.startswith(prefixes)] == expected, "Android package, ABI or launcher changed")
        check(any(line.startswith("package:") for line in expected)
              and any("com.hatch.loader.HatchActivity" in line for line in expected),
              "Manifest does not advertise the Hatch launcher")
        os.replace(tmp_signed, a.out)
    result = dict(
        file=a.out.name, bytes=a.out.stat().st_size, sha256=sha(a.out), modCount=len(mods),
        sceneIds=ids, audio={k: v["seconds"] for k, v in campaign["weatherBanks"].items()},
        signedV2=True, signedV3=True, matchesPreviousCertificate=True, zip16KiB=True,
        androidManifest=expected, deviceTest=False,
    )
    a.report.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(message.splitlines()[0], a.out.name, result["bytes"], result["sha256"], flush=True)


if __name__ == "__main__":
    arg = argparse.ArgumentParser(description=__doc__)
    for name in ("apk", "kit", "assets", "runtime", "work", "out", "report", "apksigner", "zipalign", "aapt", "key", "cert"):
        arg.add_argument("--" + name, required=True, type=Path)
    build(arg.parse_args())
