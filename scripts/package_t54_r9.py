#!/usr/bin/env python3
"""Package the exact r9 snapshot without recompiling older native/Java source."""
import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(data): return hashlib.sha256(data).hexdigest()

def prepare(baseline, data, output):
    snapshot = json.loads((ROOT / 'prebuilt/5.1.0/r9/snapshot.json').read_text())
    if sha(baseline.read_bytes()) != snapshot['baseline_apk_sha256']:
        raise ValueError('Expected released r8 APK')
    if sha(data.read_bytes()) != snapshot['unity_data_sha256']:
        raise ValueError('Expected verified r9 Unity data')
    dex = (ROOT / 'prebuilt/5.1.0/r9/mod.dex').read_bytes()
    module = (ROOT / 'prebuilt/5.1.0/r9/libaotmod.so').read_bytes()
    assert sha(dex) == snapshot['dex_sha256'] and sha(module) == snapshot['native_module_sha256']
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(baseline) as old, zipfile.ZipFile(output, 'w') as new:
        assert sha(old.read('lib/arm64-v8a/libaotmod.so')) == snapshot['native_module_sha256']
        assert len(old.namelist()) == len(set(old.namelist()))
        for info in old.infolist():
            assert info.filename != 'META-INF/MANIFEST.MF'
            assert not re.match(r'META-INF/[^/]+\.(?:RSA|DSA|EC|SF)$', info.filename, re.I)
            content = data.read_bytes() if info.filename == 'assets/bin/Data/data.unity3d' else dex if info.filename == 'classes4.dex' else old.read(info.filename)
            new.writestr(info, content)
    with zipfile.ZipFile(baseline) as old, zipfile.ZipFile(output) as new:
        assert new.testzip() is None and set(old.namelist()) == set(new.namelist())
        changed = [n for n in new.namelist() if sha(old.read(n)) != sha(new.read(n))]
        assert set(changed) == {'classes4.dex', 'assets/bin/Data/data.unity3d'}
    return snapshot

def run(*args):
    r = subprocess.run(list(map(str, args)), check=True, capture_output=True, text=True)
    return r.stdout + r.stderr

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True); p.add_argument('--unity-data', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--config', type=Path)
    p.add_argument('--work-dir', type=Path, default=ROOT / 'build/r9'); p.add_argument('--unsigned-only', action='store_true')
    a = p.parse_args(); a.work_dir.mkdir(parents=True, exist_ok=True)
    if a.unsigned_only:
        prepare(a.baseline, a.unity_data, a.output); print('Unsigned APK:', a.output)
    else:
        if not a.config: p.error('--config required for signing')
        c = json.loads(a.config.read_text()); unsigned = a.work_dir / 'unsigned.apk'; aligned = a.work_dir / 'aligned.apk'
        snapshot = prepare(a.baseline, a.unity_data, unsigned)
        log = run(c['zipalign'], '-f', '-P', '16', '4', unsigned, aligned)
        log += run('java', '-jar', c['apksigner'], 'sign', '--ks', c['keystore'], '--ks-key-alias', c.get('alias', 'luna17'),
            '--ks-pass', 'file:' + c['password_file'], '--v1-signing-enabled', 'false', '--v2-signing-enabled', 'true',
            '--v3-signing-enabled', 'true', '--min-sdk-version', '28', '--out', a.output, aligned)
        verified = run('java', '-jar', c['apksigner'], 'verify', '--verbose', '--print-certs', a.output)
        assert 'Signer #1 certificate SHA-256 digest: ' + snapshot['certificate_sha256'] in verified
        log += verified + run(c['zipalign'], '-c', '-P', '16', '4', a.output)
        (a.work_dir / 'verification.txt').write_text(log); print(a.output)
