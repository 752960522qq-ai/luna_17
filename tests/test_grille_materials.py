"""Original source and the real compiler's material/back-face payload checks."""
import hashlib,unittest
from pathlib import Path
import numpy as np
from tankbuilder.modelrig import Model
from hatch.pack import compile_project,NODE
from scripts.fix_grille_dark_materials import SWATCHES
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'upload/s.i.g_331_sdkfz_1381_ausf.h_grille(3).glb'
class GrilleMaterials(unittest.TestCase):
 @unittest.skipUnless(SOURCE.is_file(),'Original uploaded Grille model required')
 def test_original_materials_and_images_preserved(self):
  source=Model(SOURCE);rig=Model(ROOT/'tanks/Grille/model.glb')
  self.assertEqual(rig.g.asset.extras['source_sha256'],hashlib.sha256(SOURCE.read_bytes()).hexdigest())
  for i,mat in enumerate(source.g.materials):
   original=mat.extensions['KHR_materials_pbrSpecularGlossiness'];p=rig.g.materials[i].pbrMetallicRoughness
   expected=original.get('diffuseFactor',[1,1,1,1])
   if mat.name in SWATCHES:
    np.testing.assert_allclose(expected,SWATCHES[mat.name][0])
    expected=SWATCHES[mat.name][1]
   np.testing.assert_allclose(expected,p.baseColorFactor)
   if 'diffuseTexture' in original:self.assertEqual(original['diffuseTexture']['index'],p.baseColorTexture.index)
  for original,current in zip(source.g.images,rig.g.images):
   a=source.g.bufferViews[original.bufferView];b=rig.g.bufferViews[current.bufferView]
   self.assertEqual(source.blob[a.byteOffset:a.byteOffset+a.byteLength],rig.blob[b.byteOffset:b.byteOffset+b.byteLength])
 def test_double_sided_surfaces_keep_uvs_and_reverse_normals(self):
  payload,info=compile_project(ROOT/'tanks/Grille');offset=616;records={};backs=0
  for _ in range(info['nodes']):
   record=NODE.unpack_from(payload,offset);offset+=NODE.size;count,indices=record[12:14]
   v=np.frombuffer(payload,'<f4',count*8,offset).reshape(-1,8);offset+=count*32
   ix=np.frombuffer(payload,'<u4',indices,offset);offset+=indices*4
   name=record[-1].split(b'\0')[0].decode();records[name]=(record,v,ix)
   if name.endswith('_back'):
    original,front,front_ix=records[name[:-5]];backs+=1
    np.testing.assert_array_equal(v[:,:3],front[:,:3]);np.testing.assert_array_equal(v[:,3:6],-front[:,3:6]);np.testing.assert_array_equal(v[:,6:],front[:,6:])
    np.testing.assert_array_equal(ix.reshape(-1,3),front_ix.reshape(-1,3)[:,[0,2,1]])
    self.assertEqual(record[14:20],original[14:20])
  self.assertGreater(backs,40)
