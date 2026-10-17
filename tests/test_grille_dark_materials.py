"""Reproduce dark swatches from the repository baseline and check the correction."""
import copy
import json
import struct
import unittest
from pathlib import Path
from scripts.fix_grille_dark_materials import correct, SWATCHES

ROOT = Path(__file__).resolve().parents[1]

def document(data):
    size = struct.unpack_from('<I', data, 12)[0]
    return json.loads(data[20:20+size]), 20+size

class GrilleDarkMaterials(unittest.TestCase):
    def test_two_swatches_only_geometry_and_textures_unchanged(self):
        patched = (ROOT/'tanks/Grille/model.glb').read_bytes()
        final, offset = document(patched)
        original = copy.deepcopy(final)
        for material in original['materials']:
            if material.get('name') in SWATCHES:
                material['pbrMetallicRoughness']['baseColorFactor'] = SWATCHES[material['name']][0]
        payload = json.dumps(original, separators=(',', ':')).encode().ljust(offset-20, b' ')
        baseline = patched[:20]+payload+patched[offset:]
        fixed = correct(baseline)
        actual, actual_offset = document(fixed)
        self.assertEqual(actual, final)
        self.assertEqual(offset, actual_offset)
        self.assertEqual(baseline[offset:], fixed[offset:])
        self.assertEqual(len(baseline), len(fixed))
        self.assertEqual(correct(fixed), fixed)
        for index, material in enumerate(actual['materials']):
            if material.get('name') in SWATCHES:
                self.assertEqual(material['pbrMetallicRoughness']['baseColorFactor'], SWATCHES[material['name']][1])
                # Actual runtime multiplies these factors into untextured meshes.
                self.assertGreater(min(material['pbrMetallicRoughness']['baseColorFactor'][:3]), .2)
            else:
                self.assertEqual(material, original['materials'][index])
        self.assertEqual(actual['nodes'], original['nodes'])
        self.assertEqual(actual['meshes'], original['meshes'])

    def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            correct(b'not a model')

if __name__ == '__main__':
    unittest.main()
