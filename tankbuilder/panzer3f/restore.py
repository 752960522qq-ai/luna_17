"""Restore staged vehicles and registered Unity resources against their original base. No APK output."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def restore(apk, integration, overlay, vehicle, out, additional_vehicle=(), companion=None):
    spec = json.loads(integration.read_text())
    data_path = 'assets/bin/Data/data.unity3d'
    with zipfile.ZipFile(apk) as z:
        base = z.read(data_path)
        catalog = json.loads(z.read('assets/Hatch/catalog.json'))
    delta = overlay.read_bytes()
    if sha(base) != spec['baseResourceSha256'] or sha(delta) != spec['overlaySha256']:
        raise ValueError('The base game or resource overlay does not match the receipt.')
    if catalog['mods'] != spec.get('originalCatalog', spec['catalog']['mods'][:-1]):
        raise ValueError('The base catalog differs. Rebuild the resources against the intended game.')
    primary = spec['vehicleFile']
    expected = spec.get('requiredVehicles', {primary: spec['vehicleSha256']})
    # The primary module can be renamed after download. Additional modules keep their catalog names.
    files = {primary: vehicle}
    for part in additional_vehicle:
        if part.name in files:
            raise ValueError('Duplicate module: ' + part.name)
        files[part.name] = part
    if files.keys() != expected.keys() or expected.get(primary) != spec['vehicleSha256']:
        raise ValueError('Expected exactly these modules: ' + ', '.join(expected))
    for name, path in files.items():
        if Path(name).name != name or sha(path.read_bytes()) != expected[name]:
            raise ValueError('Unexpected Hatch module: ' + name)
    runtime = spec.get('runtimeFile')
    if runtime or companion is not None:
        if (runtime != 'lib/arm64-v8a/libhatchcampaign.so' or companion is None or
                sha(companion.read_bytes()) != spec.get('runtimeSha256File')):
            raise ValueError('Supply the matching ARM64 gameplay companion via --companion.')
    header = spec['headerBytes']
    merged = delta[:header] + base[spec['retainStart']:spec['retainEnd']] + delta[header:]
    if sha(merged) != spec['resultResourceSha256']:
        raise ValueError('Reconstructed resources failed verification.')
    dest = out / data_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(merged)
    mods = out / 'assets/Hatch/mods'
    mods.mkdir(parents=True, exist_ok=True)
    for name, path in files.items():
        shutil.copyfile(path, mods / name)
    if runtime:
        dest = out / runtime
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(companion, dest)
    for name, obj in [('assets/Hatch/catalog.json', spec['catalog']),
                      ('AI/Hatch-Enemy-AI-index.json', spec['aiIndex'])]:
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    print('Restored', len(files), 'vehicle module(s), catalogs and Unity resources to', out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('apk', 'integration', 'overlay', 'vehicle', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--additional-vehicle', type=Path, action='append', default=[])
    parser.add_argument('--companion', type=Path)
    restore(**vars(parser.parse_args()))
