"""Audit Unity methods against decrypted 5.1.0 metadata and shipped native tables.
This checks retention/name/arity/native entries, not scene or GPU execution.
"""
import argparse,json,struct
from pathlib import Path
from elftools.elf.elffile import ELFFile

def audit(library,decoded):
 b=(decoded/'section3.dat').read_bytes();s=(decoded/'section4.dat').read_bytes()
 with library.open('rb') as f:
  e=ELFFile(f);segs=[(x['p_vaddr'],x.data()) for x in e.iter_segments() if x['p_filesz']];rel={r['r_offset']:r['r_addend'] for r in e.get_section_by_name('.rela.dyn').iter_relocations() if r['r_info_type']==1027}
 def read(a,n):return next(v[a-k:a-k+n] for k,v in segs if k<=a<a+n<=k+len(v))
 def ptr(a):return rel.get(a,struct.unpack('<Q',read(a,8))[0])
 tables={}
 for name in ['CoreModule','PhysicsModule','ImageConversionModule']:
  needle=('UnityEngine.'+name+'.dll\0').encode();hits=[]
  for start,v in segs:
   pos=v.find(needle)
   if pos>=0:hits.extend(a for a,value in rel.items() if value==start+pos)
  assert len(hits)==1,(name,hits);tables[name]=ptr(hits[0]+16)
 methods=[]
 for p in range(0,len(b),30):
  off=struct.unpack_from('<I',b,p)[0]
  methods.append((struct.unpack_from('<H',b,p+4)[0],s[off:s.index(0,off)].decode(),struct.unpack_from('<H',b,p+28)[0],struct.unpack_from('<I',b,p+18)[0]))
 core={
 'GameObject':(0x17ca,[('.ctor',1),('get_transform',0),('GetComponentsInternal',6),('GetComponentInChildren',2),('AddComponent',1)]),
 'Texture2D':(0x1755,[('.ctor',2)]),
 'Mesh':(0x1752,[('.ctor',0),('set_vertices',1),('set_normals',1),('set_uv',1),('set_triangles',1),('RecalculateBounds',0)]),
 'Material':(0x1724,[('.ctor',1),('set_color',1),('set_mainTexture',1),('SetTexture',2)]),
 'Renderer':(0x1721,[('get_sharedMaterial',0),('set_sharedMaterial',1),('set_enabled',1)]),
 'MeshFilter':(0x172e,[('set_sharedMesh',1)]),
 'Component':(0x17bc,[('get_transform',0),('get_gameObject',0)]),
 'Transform':(0x1812,[('set_parent',1),('set_localPosition',1),('set_localRotation',1),('set_localScale',1),('TransformPoint',1),('InverseTransformPoint',1)]),
 'Object':(0x17eb,[('set_name',1),('get_name',0)])}
 physics={'BoxCollider':(0x289e,[('set_size',1),('set_center',1)]),'Rigidbody':(0x28b7,[('set_mass',1)])}
 result=[]
 for module,classes in [('CoreModule',core),('PhysicsModule',physics),('ImageConversionModule',{'ImageConversion':(0x2bcd,[('LoadImage',2)])})]:
  for klass,(index,apis) in classes.items():
   for name,count in apis:
    tokens=[tok for k,n,c,tok in methods if k==index and n==name and c==count]
    assert tokens,(klass,name,count,'stripped')
    addresses=[ptr(tables[module]+((tok&0xffffff)-1)*8) for tok in tokens]
    assert all(addresses),(klass,name,'no native entry')
    result.append({'class':klass,'method':name,'parameters':count,'native_entries':[hex(a) for a in addresses]})
 assert not any(k==0x1752 and n=='set_indexFormat' for k,n,c,tok in methods)
 return {'passed':True,'apis_checked':len(result),'native_entries_verified':True,'stripped_index_format_setter_avoided':True,'methods':result}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--game-library',type=Path,required=True);p.add_argument('--decoded',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();r=audit(a.game_library,a.decoded);a.report.write_text(json.dumps(r,indent=2)+'\n');print('Retained Unity APIs verified:',r['apis_checked'])
