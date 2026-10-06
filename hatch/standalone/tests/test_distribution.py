"""Production installer checks using the bundled real tank package."""
import importlib.util,json,struct,tempfile,unittest,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('hatch_integrate',ROOT/'integrate.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class DistributionTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_bundled_tank(self):self.assertEqual(mod.validate_pack(ROOT/'mods/T54_1949.hatch')['id'],'T54_1949')
 def test_duplicate_ids_rejected(self):
  shutil.copyfile(ROOT/'mods/T54_1949.hatch',self.d/'a.hatch');shutil.copyfile(ROOT/'mods/T54_1949.hatch',self.d/'b.hatch')
  with self.assertRaisesRegex(ValueError,'Duplicate tank ID'):mod.collect_mods(self.d)
 def test_empty_mod_folder(self):self.assertEqual(mod.collect_mods(self.d),[])
 def test_unsafe_paths_rejected(self):
  p=self.d/'bad.hatch'
  with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','x')
  with self.assertRaisesRegex(ValueError,'Unsafe'):mod.validate_pack(p)
 def test_wrong_format_rejected(self):
  p=self.d/'bad.hatch'
  with zipfile.ZipFile(p,'w') as z:z.writestr('tank.json','{}')
  with self.assertRaisesRegex(ValueError,'convert raw'):mod.validate_pack(p)
 def test_modified_runtime_rejected(self):
  p=self.d/'bad.hatch'
  with zipfile.ZipFile(ROOT/'mods/T54_1949.hatch') as source,zipfile.ZipFile(p,'w') as z:
   z.writestr('hatch.json',source.read('hatch.json'));b=bytearray(source.read('runtime.bin'));b[-1]^=1;z.writestr('runtime.bin',b)
  with self.assertRaisesRegex(ValueError,'checksum'):mod.validate_pack(p)
 def test_4k_and_16k_alignment(self):
  p=self.d/'out.apk'
  with zipfile.ZipFile(p,'w') as z:
   mod.write_aligned(z,'a',b'1');mod.write_aligned(z,'lib/arm64-v8a/test.so',b'1234',zipfile.ZIP_STORED);mod.write_aligned(z,'assets/Hatch/mods/a.hatch',b'123',zipfile.ZIP_STORED)
  mod.check_alignment(p)
 def test_bad_metadata_rejected_before_output(self):
  p=self.d/'game.apk';out=self.d/'out.apk'
  with zipfile.ZipFile(p,'w') as z:z.writestr('AndroidManifest.xml',b'bad');z.writestr('assets/bin/Data/Managed/Metadata/global-metadata.dat',b'bad')
  with self.assertRaisesRegex(ValueError,'metadata'):mod.assemble(p,out,[])
  self.assertFalse(out.exists())
 def test_already_integrated_input_rejected(self):
  p=self.d/'game.apk'
  with zipfile.ZipFile(p,'w') as z:z.writestr('AndroidManifest.xml',b'bad');z.writestr('lib/arm64-v8a/libaotmod.so',b'bad')
  with self.assertRaisesRegex(ValueError,'already contains'):mod.assemble(p,self.d/'out.apk',[])
if __name__=='__main__':unittest.main(verbosity=2)
