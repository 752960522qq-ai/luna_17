"""Install only the generic loader in the APK; all game hooks live in a .hatch."""
import contextlib
import hashlib
import io
import json
import re
import struct
import zipfile
from pathlib import Path
from repack import patch_manifest, write_entry
from hatch.package import validate, CORE_ID

# The released r11 APK is an explicitly supported migration source.
R11_SHA256 = 'b3d9498c7bf4881d33c5fcc857d94715eaeffc532175087d4d26ab9e170efda2'

def repack_loader(source, dex, output, profile_path, packages, unity_data=None):
    profile = json.loads(Path(profile_path).read_text())
    docs = [validate(path) for path in packages]
    ids = [doc['id'] for doc in docs]
    if len(ids) != len(set(ids)) or CORE_ID not in ids or sum(d.get('type','tank')=='tank' for d in docs)>16:
        raise ValueError('Invalid builtin package catalog')
    with contextlib.ExitStack() as stack:
        outer = stack.enter_context(zipfile.ZipFile(source))
        if 'AndroidManifest.xml' in outer.namelist():
            base, splits = outer, []
        else:
            base = stack.enter_context(zipfile.ZipFile(io.BytesIO(outer.read('base.apk'))))
            splits = [stack.enter_context(zipfile.ZipFile(io.BytesIO(outer.read(name)))) for name in outer.namelist() if name.endswith('.apk') and name != 'base.apk']
        if hashlib.sha256(base.read('assets/bin/Data/Managed/Metadata/global-metadata.dat')).hexdigest() != profile['metadata_sha256']:
            raise ValueError('Unsupported game metadata')
        migrated = 'lib/arm64-v8a/libaotmod.so' in base.namelist()
        if migrated and hashlib.sha256(Path(source).read_bytes()).hexdigest() != R11_SHA256:
            raise ValueError('Migration requires the exact released r11 APK')
        manifest = patch_manifest(base.read('AndroidManifest.xml'), launcher='com.hatch.loader.HatchActivity', game_activity='com.hatch.loader.HatchGameActivity', label='突击坦克 · 舱盖', old_launchers=('com.unity3d.player.UnityPlayerActivity','com.luna17.aot.ModActivity'))
        replacement = None
        if unity_data:
            replacement = Path(unity_data).read_bytes()
            report = json.loads((Path(unity_data).parent/'asset_report.json').read_text())
            if report['input_sha256'] != profile['unity_data_sha256'] or report['output_sha256'] != hashlib.sha256(replacement).hexdigest():
                raise ValueError('Unity bundle fingerprint mismatch')
        if not migrated and replacement is None:
            raise ValueError("Clean input needs --unity-data from scripts/prepare_hatch_weapons.py; the original T34 template has no HE pools")
        written = set(); dex_indices = []
        with zipfile.ZipFile(output, 'w', allowZip64=False) as out:
            for archive in [base, *splits]:
                for entry in archive.infolist():
                    name = entry.filename
                    if entry.is_dir() or name in written or (archive is not base and not name.startswith('lib/arm64-v8a/')): continue
                    if name == 'stamp-cert-sha256' or name == 'META-INF/MANIFEST.MF' or re.fullmatch(r'META-INF/[^/]+\.(RSA|DSA|EC|SF)', name, re.I): continue
                    if name == 'lib/arm64-v8a/libaotmod.so' or name.startswith('assets/Hatch/'): continue
                    if migrated and name == 'classes4.dex': continue
                    data = archive.read(name)
                    if name == 'lib/arm64-v8a/libil2cpp.so' and hashlib.sha256(data).hexdigest()!=profile['libil2cpp_sha256']:
                        raise ValueError('Unsupported native game library')
                    match = re.fullmatch(r'classes(\d*)\.dex', name)
                    if match: dex_indices.append(int(match.group(1) or 1))
                    if name == 'AndroidManifest.xml': data = manifest
                    if name == 'assets/bin/Data/data.unity3d' and replacement is not None: data = replacement
                    write_entry(out, name, data, entry.compress_type); written.add(name)
            if 'lib/arm64-v8a/libil2cpp.so' not in written: raise ValueError('ARM64 library missing')
            write_entry(out, f'classes{max(dex_indices)+1}.dex', Path(dex).read_bytes())
            catalog = []
            for path, doc in zip(packages, docs):
                content = Path(path).read_bytes()
                write_entry(out, 'assets/Hatch/mods/'+doc['id']+'.hatch', content, zipfile.ZIP_STORED)
                catalog.append({'id':doc['id'],'name':doc['name'],'sha256':hashlib.sha256(content).hexdigest(),'size':len(content)})
            write_entry(out,'assets/Hatch/catalog.json',json.dumps({'format':2,'loader_version':'0.2','mods':catalog},ensure_ascii=False,indent=2).encode())
    return Path(output)
