#!/usr/bin/env python3
"""Add HE pools to the unchanged T34 player template used by Hatch."""
import argparse
import hashlib
import json
from pathlib import Path

from tankbuilder.unity_assets import Adapter, read_mb
from tankbuilder.weapon_assets import clone_he_pool


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    profile = json.loads((Path(__file__).resolve().parents[1] /
                          'profiles/attack-on-tank-5.1.0.json').read_text())
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != profile['unity_data_sha256']:
        raise ValueError('Expected the original 5.1.0 Unity bundle')
    adapter = Adapter(source)
    before = {(o.assets_file.name, o.path_id): hashlib.sha256(o.get_raw_data()).hexdigest()
              for o in adapter.env.objects}
    launcher = adapter.sf.objects[125757]
    values = read_mb('Launcher', launcher.get_raw_data())
    if values['shellHeGos'] or len(values['shellApGos']) != 2:
        raise ValueError('T34 launcher layout changed')
    parent = adapter.sf.objects[values['thisTrf']['m_PathID']]
    pool = clone_he_pool(adapter, launcher, parent)
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / 'data.unity3d'
    bundle = next(f for f in adapter.env.files.values() if hasattr(f, 'save_fs'))
    output.write_bytes(bundle.save(packer='lz4'))
    saved = Adapter(output)
    changed = [key for key, digest in before.items()
               if hashlib.sha256(saved.files[key[0]].objects[key[1]].get_raw_data()).hexdigest() != digest]
    if set(changed) != {('resources.assets', 125757), ('resources.assets', parent.path_id)}:
        raise AssertionError('Unexpected original resource changes: ' + repr(changed))
    result = read_mb('Launcher', saved.sf.objects[125757].get_raw_data())
    if result['shellHeGos'] != pool or result['shellApGos'] != values['shellApGos']:
        raise AssertionError('Projectile pool references did not survive serialization')
    report = dict(adapter='aot-5.1.0-arm64-v1', input_sha256=source_hash,
                  output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  changed_original_objects=changed, added_objects=adapter.created,
                  ap_pool_preserved=True, he_pool_count=len(pool), android_device_test=False)
    (destination / 'asset_report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output_dir), indent=2))
