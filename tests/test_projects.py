import copy,json,tempfile,unittest,zipfile
from pathlib import Path
from PIL import Image
from tankbuilder.project import ROOT,create_project,read_documents,save_documents,import_model,replace_texture,pack_project,generate_runtime_header,validate_project
from tankbuilder.modelrig import Model
from tankbuilder.tankpack import validate_pack
class Projects(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.d=Path(self.temp.name)/'tank';create_project(self.d,ident='TEST_TANK')
 def tearDown(self):self.temp.cleanup()
 def test_import_texture_pack_roundtrip(self):
  self.assertTrue(import_model(self.d,ROOT/'tanks/T54_1949/model.glb')['valid'])
  m=Model(self.d/'model.glb');mat=next(x for x in m.g.materials if x.pbrMetallicRoughness and x.pbrMetallicRoughness.baseColorTexture);old=mat.pbrMetallicRoughness.baseColorTexture.index;old_images=len(m.g.images)
  png=Path(self.temp.name)/'paint.png';Image.new('RGB',(32,32),'red').save(png)
  self.assertTrue(replace_texture(self.d,mat.name,png)['valid']);changed=Model(self.d/'model.glb');self.assertEqual(len(changed.g.images),old_images+1);self.assertNotEqual(next(x for x in changed.g.materials if x.name==mat.name).pbrMetallicRoughness.baseColorTexture.index,old)
  out=Path(self.temp.name)/'tank.tankpack';pack_project(self.d,out);self.assertTrue(validate_pack(out)['can_inject'])
 def test_parameters_generate_native_config(self):
  d=read_documents(self.d);d['tank']['maxForwardSpeed']=72;d['armor']['body']['front']=190;d['weapon']['reload']=7.4;save_documents(self.d,d);h=Path(self.temp.name)/'config.h';generate_runtime_header([self.d],h);self.assertIn('72',h.read_text());self.assertIn('{190,',h.read_text());self.assertIn('TEST_TANK',h.read_text())
 def test_invalid_parameter_and_binding_preserve_previous_pack(self):
  out=Path(self.temp.name)/'tank.tankpack';pack_project(self.d,out);before=out.read_bytes();d=read_documents(self.d);d['tank']['weightTonnes']=float('nan');d['rig']['gun']['node']=99999;save_documents(self.d,d);self.assertFalse(validate_project(self.d)['valid'])
  with self.assertRaises(ValueError):pack_project(self.d,out)
  self.assertEqual(out.read_bytes(),before)
 def test_unsafe_archive_rejected(self):
  out=Path(self.temp.name)/'evil.tankpack'
  with zipfile.ZipFile(out,'w') as z:z.writestr('../escape','bad')
  with self.assertRaises(ValueError):validate_pack(out)
if __name__=='__main__':unittest.main()
