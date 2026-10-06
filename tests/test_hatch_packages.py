"""Package corruption, dependency and magazine validation against actual packs."""
import argparse
import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from hatch.package import validate

class Packages(unittest.TestCase):
    def rewrite(self, **updates):
        output=Path(self.temp.name)/'test.hatch'
        with zipfile.ZipFile(ARGS.tank) as src, zipfile.ZipFile(output,'w',zipfile.ZIP_STORED) as dst:
            doc=json.loads(src.read('hatch.json'));doc.update(updates)
            for name in src.namelist():dst.writestr(name,json.dumps(doc).encode() if name=='hatch.json' else src.read(name))
        return output
    def setUp(self):self.temp=tempfile.TemporaryDirectory()
    def tearDown(self):self.temp.cleanup()
    def test_actual_tank_and_module(self):
        self.assertEqual(validate(ARGS.module)['version'],'1.0')
        self.assertEqual(validate(ARGS.tank)['requires'],{'tankinvincible3000':'1.0'})
    def test_magazine_valid(self):
        doc=validate(self.rewrite(magazine={'capacity':5,'shotInterval':.25,'reloadTime':8.}))
        self.assertEqual(doc['magazine']['capacity'],5)
    def test_bad_magazine_rejected(self):
        for values in [(1,.25,8),(5.2,.25,8),(5,0,8),(5,.25,.1),(5,.25,301),(5,float('nan'),8)]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                validate(self.rewrite(magazine=dict(zip(['capacity','shotInterval','reloadTime'],values))))
    def test_runtime_identity_checksum_and_dependency_rejected(self):
        for updates in [dict(id='WrongTank'),dict(runtime_sha256='0'*64),dict(requires={'unknown':'1.0'}),dict(requires={'tankinvincible3000':'0.1'}),dict(id='tankinvincible3000')]:
            with self.subTest(updates=updates),self.assertRaises(ValueError):validate(self.rewrite(**updates))
    def test_old_tank_format_supported(self):
        self.assertEqual(validate(self.rewrite(format=1,loader_version='0.1',requires={}))['format'],1)
    def test_duplicate_archive_entry_rejected(self):
        path=self.rewrite()
        with zipfile.ZipFile(path,'a') as out:out.writestr('hatch.json','{}')
        with self.assertRaises(ValueError):validate(path)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tank',required=True);p.add_argument('--module',required=True)
    ARGS,extra=p.parse_known_args();unittest.main(argv=['test_hatch_packages']+extra)
