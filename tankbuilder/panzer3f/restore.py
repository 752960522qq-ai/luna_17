"""Restore staged resources from the private vehicle files and the matching base. No APK output."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

def sha(data):
    return hashlib.sha256(data).hexdigest()

def restore(apk, integration, overlay, vehicle, out):
    spec = json.loads(integration.read_text())
    data_path = 'assets/bin/Data/data.unity3d'
    with zipfile.ZipFile(apk) as z:
        base = z.read(data_path)
        catalog = json.loads(z.read('assets/Hatch/catalog.json'))
    delta = overlay.read_bytes()
    if sha(base) != spec['baseResourceSha256'] or sha(delta) != spec['overlaySha256']:
        raise ValueError('The staged resources were prepared against a different game version.')
    if sha(vehicle.read_bytes()) != spec['vehicleSha256']:
        raise ValueError('The Hatch module does not match the staged model.')
    if catalog['mods'] != spec['catalog']['mods'][:-1]:
        raise ValueError('The prior vehicle catalog differs; use integrate.stage to rebuild additively.')
    header = spec['headerBytes']
    merged = delta[:header] + base[spec['retainStart']:spec['retainEnd']] + delta[header:]
    if sha(merged) != spec['resultResourceSha256']:
        raise ValueError('Reconstructed resources failed verification.')
    dest = out / data_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(merged)
    mods = out / 'assets/Hatch/mods'
    mods.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(vehicle, mods / spec['vehicleFile'])
    for name, obj in [('assets/Hatch/catalog.json', spec['catalog']),
                      ('AI/Hatch-Enemy-AI-index.json', spec['aiIndex'])]:
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    print('Vehicle, catalogs and Unity resources restored to', out)

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('apk','integration','overlay','vehicle','out'):
        parser.add_argument('--' + key, type=Path, required=True)
    restore(**vars(parser.parse_args()))
