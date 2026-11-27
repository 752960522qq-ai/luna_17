#!/usr/bin/env python3
"""Rebuild the Java startup path in a released APK and matching kit, preserving all native code."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile

from assemble_campaign_apk import LOADER, CORE, DEX, CAT, NATIVE, SIG
from build_campaign_runtime import build_java
from hatch.package import validate
from repack import patch_manifest, write_entry

CERT = "734e17a0550eb23e3e5975dc90a7932eb513ee0e62ad4804b436cacd5f15413e"
ROOT = Path(__file__).resolve().parents[1]


def digest(zip_file, name):
    with zip_file.open(name) as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def build_updates(work, apk, android, r8):
    build_java(work, android, r8)
    dex = (work / "mod-dex/classes.dex").read_bytes()
    new_core = work / "tankinvincible3000.hatch"
    with zipfile.ZipFile(apk) as src:
        old_core = src.read(CORE)
        with zipfile.ZipFile(io.BytesIO(old_core)) as old, zipfile.ZipFile(new_core, "w") as out:
            desc = json.loads(old.read("hatch.json"))
            assert desc["native_sha256"] == hashlib.sha256(old.read("module.so")).hexdigest()
            assert desc["native_sha256"] == "5f0195c93f967c0e24458e1d39a751c39f4256653cc836a09f3ff2644b93a02f"
            desc.update(dex_sha256=hashlib.sha256(dex).hexdigest(), dex_bytes=len(dex))
            for entry in old.infolist():
                n = entry.filename
                data = dex if n == "module.dex" else (json.dumps(desc, ensure_ascii=False, indent=2).encode()
                                                      if n == "hatch.json" else old.read(n))
                out.writestr(entry, data)
        validate(new_core)
        catalog = json.loads(src.read(CAT))
        record, = [e for e in catalog["mods"] if e["id"] == "tankinvincible3000"]
        previous = record["sha256"]
        assert previous == hashlib.sha256(old_core).hexdigest() and len(catalog["mods"]) == 13
        binary = new_core.read_bytes()
        record.update(sha256=hashlib.sha256(binary).hexdigest(), size=len(binary))
        if previous != record["sha256"]:
            record["supersedes_sha256"] = sorted(set(record.get("supersedes_sha256", [])) | {previous})
        def manifest(data):
            return patch_manifest(data, "com.hatch.loader.HatchActivity", "突击坦克 · 舱盖",
                                  ("com.unity3d.player.UnityPlayerActivity", "com.luna17.aot.ModActivity"),
                                  "com.hatch.loader.HatchGameActivity")
        xml = manifest(src.read("AndroidManifest.xml"))
        assert manifest(xml) == xml
    return {LOADER: (work / "loader-dex/classes.dex").read_bytes(),
            DEX: (work / "main-dex/classes.dex").read_bytes(), CORE: binary,
            CAT: json.dumps(catalog, ensure_ascii=False, indent=2).encode(), "AndroidManifest.xml": xml}


def is_signature(name):
    return name == "stamp-cert-sha256" or SIG.fullmatch(name)


def repack_apk(old, new, updates):
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(new, "w", allowZip64=False) as dst:
        assert set(updates) | {NATIVE} <= set(src.namelist())
        for entry in src.infolist():
            n = entry.filename
            if not is_signature(n):
                write_entry(dst, n, updates[n] if n in updates else src.read(n), entry.compress_type,
                            alignment=16384 if n.endswith(".so") else 4)


def verify_apk(old, signed, updates):
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(signed) as dst, signed.open("rb") as raw:
        assert dst.testzip() is None
        expected = {n for n in src.namelist() if not is_signature(n)}
        assert len(expected) == len(dst.namelist()) and expected == set(dst.namelist())
        for entry in dst.infolist():
            n = entry.filename
            if n in updates:
                assert dst.read(n) == updates[n], n
            else:
                assert digest(src, n) == digest(dst, n), n
            if entry.compress_type == zipfile.ZIP_STORED:
                raw.seek(entry.header_offset + 26)
                ln, ex = struct.unpack("<HH", raw.read(4))
                assert (entry.header_offset + 30 + ln + ex) % (16384 if n.endswith(".so") else 4) == 0, n


def repack_kit(old, new, updates):
    changes = dict(updates, **{"README-zh.md": (ROOT / "tankbuilder/barbarossa/mission/README-zh.md").read_bytes()})
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(new, "w", zipfile.ZIP_DEFLATED) as dst:
        for entry in src.infolist():
            n = entry.filename
            dst.writestr(entry, changes[n] if n in changes else src.read(n))
        for n in sorted(changes.keys() - set(src.namelist())):
            dst.writestr(n, changes[n])
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(new) as dst:
        assert dst.testzip() is None
        assert set(src.namelist()) | set(changes) == set(dst.namelist())
        for n in dst.namelist():
            if n in changes: assert dst.read(n) == changes[n], n
            else: assert digest(src, n) == digest(dst, n), n


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("apk", "kit", "out-apk", "out-kit", "android-jar", "r8", "apksigner", "key", "cert"):
        p.add_argument("--" + n, type=Path, required=True)
    a = p.parse_args()
    if hashlib.sha256(a.cert.read_bytes()).hexdigest() != CERT:
        raise ValueError("Expected the existing Hatch project signing certificate")
    if a.apk.resolve() == a.out_apk.resolve() or a.kit.resolve() == a.out_kit.resolve():
        raise ValueError("Output paths must differ from their inputs")
    with tempfile.TemporaryDirectory(prefix="campaign-loader-") as d:
        work = Path(d)
        updates = build_updates(work, a.apk, a.android_jar, a.r8)
        unsigned = work / "unsigned.apk"
        repack_apk(a.apk, unsigned, updates)
        signer = ["java", "-cp", a.apksigner, "com.android.apksigner.ApkSignerTool"]
        subprocess.run([*signer, "sign", "--key", a.key, "--cert", a.cert,
                        "--min-sdk-version", "28", "--v1-signing-enabled", "false",
                        "--v2-signing-enabled", "true", "--v3-signing-enabled", "true",
                        "--alignment-preserved", "true",
                        "--v4-signing-enabled", "false", "--out", a.out_apk, unsigned], check=True)
        report = subprocess.check_output([*signer, "verify", "--verbose", "--print-certs", a.out_apk], text=True)
        assert f"certificate SHA-256 digest: {CERT}" in report
        v2 = subprocess.check_output([*signer, "verify", "--verbose", "--min-sdk-version", "24",
                                      "--max-sdk-version", "27", a.out_apk], text=True)
        assert "Verified using v2 scheme (APK Signature Scheme v2): true" in v2
        assert "Verified using v3 scheme (APK Signature Scheme v3): true" in report
        verify_apk(a.apk, a.out_apk, updates)
        repack_kit(a.kit, a.out_kit, updates)
        print(report.splitlines()[0], "with original certificate; all original game assets, tanks and native libraries match")


if __name__ == "__main__":
    main()
