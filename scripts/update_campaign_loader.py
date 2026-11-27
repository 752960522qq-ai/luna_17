#!/usr/bin/env python3
"""Refresh only the loader in an existing complete campaign APK and resource kit."""

import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile

from assemble_campaign_apk import LOADER, CORE, NATIVE, SIG
from repack import write_entry

CERT = "734e17a0550eb23e3e5975dc90a7932eb513ee0e62ad4804b436cacd5f15413e"
ROOT = Path(__file__).resolve().parents[1]


def digest(zip_file, name):
    with zip_file.open(name) as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def build_loader(work, android, r8):
    classes, dex = work / "classes", work / "dex"
    classes.mkdir()
    dex.mkdir()
    subprocess.run(
        ["java", "com.sun.tools.javac.Main", "-source", "8", "-target", "8",
         "-Xlint:-options", "-encoding", "UTF-8", "-cp", android, "-d", classes,
         *sorted((ROOT / "app/stubs").rglob("*.java")),
         *sorted((ROOT / "loader/src").rglob("*.java"))],
        check=True,
    )
    subprocess.run(
        ["java", "-cp", r8, "com.android.tools.r8.D8", "--min-api", "28",
         "--lib", android, "--classpath", classes, "--output", dex,
         *sorted((classes / "com/hatch/loader").rglob("*.class"))],
        check=True,
    )
    return (dex / "classes.dex").read_bytes()


def is_signature(name):
    return name == "stamp-cert-sha256" or SIG.fullmatch(name)


def repack_apk(old, new, dex):
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(new, "w", allowZip64=False) as dst:
        assert {LOADER, CORE, NATIVE}.issubset(src.namelist())
        assert dex != src.read(LOADER)
        for entry in src.infolist():
            n = entry.filename
            if not is_signature(n):
                write_entry(dst, n, dex if n == LOADER else src.read(n), entry.compress_type,
                            alignment=16384 if n.endswith(".so") else 4)


def verify_apk(old, signed, dex):
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(signed) as dst, signed.open("rb") as raw:
        assert dst.testzip() is None and dst.read(LOADER) == dex
        expected = {n for n in src.namelist() if not is_signature(n)}
        assert len(expected) == len(dst.namelist()) and expected == set(dst.namelist())
        for entry in dst.infolist():
            n = entry.filename
            if n != LOADER:
                assert digest(src, n) == digest(dst, n), n
            if entry.compress_type == zipfile.ZIP_STORED:
                raw.seek(entry.header_offset + 26)
                ln, ex = struct.unpack("<HH", raw.read(4))
                assert (entry.header_offset + 30 + ln + ex) % (16384 if n.endswith(".so") else 4) == 0, n


def repack_kit(old, new, dex):
    with zipfile.ZipFile(old) as src, zipfile.ZipFile(new, "w", zipfile.ZIP_DEFLATED) as dst:
        for entry in src.infolist():
            n = entry.filename
            if n not in (LOADER, "README-zh.md"):
                dst.writestr(entry, src.read(n))
        dst.writestr("README-zh.md", (ROOT / "tankbuilder/barbarossa/mission/README-zh.md").read_bytes())
        dst.writestr(LOADER, dex)
    with zipfile.ZipFile(new) as dst:
        assert dst.testzip() is None and dst.read(LOADER) == dex


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
        dex = build_loader(work, a.android_jar, a.r8)
        unsigned = work / "unsigned.apk"
        repack_apk(a.apk, unsigned, dex)
        signer = ["java", "-cp", a.apksigner, "com.android.apksigner.ApkSignerTool"]
        subprocess.run([*signer, "sign", "--key", a.key, "--cert", a.cert,
                        "--min-sdk-version", "28", "--v1-signing-enabled", "false",
                        "--v2-signing-enabled", "true", "--v3-signing-enabled", "true",
                        "--alignment-preserved", "true",
                        "--v4-signing-enabled", "false", "--out", a.out_apk, unsigned], check=True)
        report = subprocess.check_output([*signer, "verify", "--verbose", "--print-certs", a.out_apk], text=True)
        assert f"certificate SHA-256 digest: {CERT}" in report
        assert "Verified using v3 scheme (APK Signature Scheme v3): true" in report
        verify_apk(a.apk, a.out_apk, dex)
        repack_kit(a.kit, a.out_kit, dex)
        print(report.splitlines()[0], "with original certificate; only classes4.dex changed in the APK")


if __name__ == "__main__":
    main()
