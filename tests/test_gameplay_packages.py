import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from hatch.features import pack_features
from hatch.package import validate
ROOT=Path(__file__).resolve().parents[1]

class Features(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'feature.hatch'
        pack_features(ROOT/'mods/better_tank_experience',self.path)
    def tearDown(self):self.temp.cleanup()
    def test_standalone_data_package(self):
        doc=validate(self.path);self.assertEqual(doc['type'],'gameplay');self.assertEqual(doc['version'],'0.1')
        with zipfile.ZipFile(self.path) as archive:
            payload=json.loads(archive.read('features.json'));self.assertEqual(payload['damage']['apFillingGrams'],155)
            self.assertEqual(set(archive.namelist()),{'hatch.json','features.json'})
    def test_corrupt_config_or_interface_rejected(self):
        with zipfile.ZipFile(self.path) as src:entries={n:src.read(n) for n in src.namelist()}
        for update in ({'api_version':2},{'features_sha256':'0'*64},{'capabilities':[]},{'features_bytes':65537}):
            doc=json.loads(entries['hatch.json']);doc.update(update)
            with zipfile.ZipFile(self.path,'w') as dst:
                for name,data in entries.items():dst.writestr(name,json.dumps(doc) if name=='hatch.json' else data)
            with self.subTest(update=update),self.assertRaises(ValueError):validate(self.path)
    def test_general_dependency_declaration(self):
        with zipfile.ZipFile(self.path) as src:entries={n:src.read(n) for n in src.namelist()}
        doc=json.loads(entries['hatch.json']);doc['requires']['terrain_extension']='0.2'
        with zipfile.ZipFile(self.path,'w') as dst:
            for name,data in entries.items():dst.writestr(name,json.dumps(doc) if name=='hatch.json' else data)
        self.assertEqual(validate(self.path)['requires']['terrain_extension'],'0.2')
if __name__=='__main__':unittest.main()
