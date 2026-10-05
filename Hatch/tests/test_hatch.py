"""Exercise the production native parser with real model bytes and corrupted inputs."""
import argparse,json,os,struct,subprocess,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class HatchTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.d=Path(cls.temp.name);cls.exe=cls.d/'parser'
  subprocess.run(['gcc','-std=c11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(ROOT/'tests/hatch_parser.c'),'-lm','-o',str(cls.exe)],check=True)
  with zipfile.ZipFile(ARGS.package) as z:cls.blob=z.read('runtime.bin');cls.manifest=json.loads(z.read('hatch.json'))
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def run_parser(self,blob,success=True,duplicate=False):
  p=self.d/'runtime.bin';p.write_bytes(blob)
  result=subprocess.run([str(self.exe),str(p)]+([str(p)] if duplicate else []),capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
  self.assertNotIn('runtime error:',result.stderr);self.assertNotIn('AddressSanitizer',result.stderr)
  self.assertEqual(result.returncode,0 if success else 1,result.stderr)
  return result
 def test_real_model_and_config(self):
  self.assertEqual(self.run_parser(self.blob).stdout.strip(),'1');self.assertGreater(self.manifest['nodes'],100);self.assertGreater(self.manifest['textures'],0)
 def test_header_and_size(self):
  for n in [0,12,23,200,1000,len(self.blob)-1]:
   with self.subTest(length=n):self.run_parser(self.blob[:n],False)
 def test_duplicate_identity(self):self.assertIn('Duplicate tank ID',self.run_parser(self.blob,False,True).stderr)
 def test_bad_parameters(self):
  for offset,fmt,value in [(24+320,'I',6),(24+324+30*4,'i',3),(24+448+2*4,'f',float('nan'))]:
   b=bytearray(self.blob);struct.pack_into('<'+fmt,b,offset,value);self.run_parser(b,False)
 def test_hierarchy_and_material(self):
  for offset,value in [(616,0),(620,1024),(616+56,9999)]:
   b=bytearray(self.blob);struct.pack_into('<i',b,offset,value);self.run_parser(b,False)
 def test_invalid_mesh_index(self):
  b=bytearray(self.blob);at=616
  for _ in range(self.manifest['nodes']):
   vertices,indices=struct.unpack_from('<II',b,at+48)
   if vertices:
    struct.pack_into('<I',b,at+176+vertices*32,vertices);break
   at+=176+vertices*32+indices*4
  self.run_parser(b,False)
 def test_texture_magic_and_trailing_data(self):
  b=bytearray(self.blob);at=616
  for _ in range(self.manifest['nodes']):
   v,i=struct.unpack_from('<II',b,at+48);at+=176+v*32+i*4
  b[at+4:at+12]=b'NOTIMAGE';self.run_parser(b,False)
  b=bytearray(self.blob)+b'x';struct.pack_into('<I',b,12,len(b));self.run_parser(b,False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--report',type=Path);ARGS,remaining=p.parse_known_args()
 r=unittest.main(argv=['hatch']+remaining,exit=False,verbosity=2).result
 if ARGS.report:ARGS.report.write_text(json.dumps({'tests_run':r.testsRun,'passed':r.wasSuccessful(),'failures':len(r.failures),'errors':len(r.errors),'scope':'native package parser, ASan/UBSan; not Unity runtime'},indent=2))
 raise SystemExit(0 if r.wasSuccessful() else 1)
