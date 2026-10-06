#!/usr/bin/env python3
"""Rebuild the supplied T54 and Matilda packages with the r11 source fixes."""
import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from hatch.pack import pack_project
from hatch.standalone.integrate import validate_pack
from tankbuilder.modelrig import Model
from tankbuilder.project import FILES
from tankbuilder.t54_controls import repair_model, verify_model


def rebuild(source, destination):
    info = validate_pack(source)
    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary)
        with zipfile.ZipFile(source) as archive:
            for name in FILES:
                (project / name).write_bytes(archive.read(name))
        if info['id'] == 'T54_1949':
            model = Model(project / 'model.glb')
            if not any(n.name == 'details_73_turret' for n in model.g.nodes):
                repair_model(model).save(project / 'repaired.glb')
                verify_model(Model(project / 'model.glb'), Model(project / 'repaired.glb'))
                (project / 'repaired.glb').replace(project / 'model.glb')
            rig_path = project / 'rig.json'
            rig = json.loads(rig_path.read_text())
            rig['colliders']['hull']['center'][1] = rig['colliders']['hull']['size'][1] / 2
            rig_path.write_text(json.dumps(rig, indent=2) + '\n')
        elif info['id'] == 'Matilda_III':
            weapon_path = project / 'weapon.json'
            weapon = json.loads(weapon_path.read_text())
            weapon['shells']['AP'].update(penetrationMm=89, parameterOrigin='User override: 89 mm')
            weapon['shells']['AP'].pop('source', None)
            weapon_path.write_text(json.dumps(weapon, indent=2) + '\n')
        else:
            raise ValueError('Expected T54_1949 or Matilda_III')
        output = destination / (info['id'] + '-Hatch-0.1.hatch')
        pack_project(project, output)
        return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--t54', type=Path, required=True)
    parser.add_argument('--matilda', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source in [args.t54, args.matilda]:
        print(rebuild(source, args.output_dir))
