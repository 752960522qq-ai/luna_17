"""Compile a validated tank project into an external runtime package (not an APK)."""
import argparse,hashlib,json,math,struct,tempfile,zipfile,io
from pathlib import Path
import numpy as np
from tankbuilder.project import validate_project,read_documents,FILES
from tankbuilder.modelrig import Model
from tankbuilder.tankpack import extract_reviewed_pack
MAGIC=b'HATCH01\0'
CFG=struct.Struct('<64s128s128sI31i9f18f9f')
NODE=struct.Struct('<iI10fIIii4f96s')
NATIONS=['USSR','Germany','USA','Japan','UK','Italy']
def name(s,n):
 b=s.encode('utf-8')
 if len(b)>=n:raise ValueError('名称 UTF-8 字节长度超出上限')
 return b+b'\0'*(n-len(b))
def compile_project(directory):
 d=Path(directory);v=validate_project(d)
 if not v['valid']:raise ValueError('; '.join(v['errors']))
 doc=read_documents(d);m,t,w,a,r=[doc[k] for k in ['manifest','tank','weapon','armor','rig']];model=Model(d/'model.glb');g=model.g
 if any(n.matrix for n in g.nodes):raise ValueError('Hatch 0.1 要求节点使用 TRS 变换，请先将矩阵变换烘焙为 TRS')
 if any(p.mode not in (None,4) for mesh in g.meshes for p in mesh.primitives):raise ValueError('Hatch 0.1 仅支持三角形网格')
 r=dict(r);kind=t.get('vehicleKind','tank')
 if kind!='tank':r['turret']=r.get('mount',r.get('turret',{}))
 wheels=[x for x in r['wheels'] if x['roadWheel']];sus=r['suspension']
 ints=[w['shells']['AP']['penetrationMm'],w['caliber'],w['muzzleVelocity'],math.ceil(w['reload']),t['enginePower'],t['maxForwardSpeed'],t['turretRotation'],t['gunElevation'],abs(t['gunDepression']),t['crew'],m['tier']]+[a[k][f] for k in ['body','turret'] for f in ['front','side','side','rear']]+[w['ammo'].get(k,0) for k in ['AP','HEAT','APCR','WP','HE']]+[w['machineGun']['ammo']]+[w['shells'].get(k,{}).get('penetrationMm',0) for k in ['AP','HEAT','APCR','WP','HE']]+[len(wheels)]
 floats=[w['reload']-math.ceil(w['reload']),t['maxReverseSpeed']/3.6,t['weightTonnes'],sus['travel'],sus['restCompression'],sus['springPerWheel'],sus['damperPerWheel'],sum(x['radius'] for x in wheels)/len(wheels),r.get('trackLoopMeters',t['dimensionsMeters']['length']*.62)]
 boxes=[v for k in ['hull','turret','unit'] for f in ['size','center'] for v in r['colliders'][k][f]]
 pivots=r['gun']['pivot']+r['muzzle']['position']+r['coaxMuzzle']['position']
 cfg=CFG.pack(name(m['id'],64),name(m['displayName'],128),name(w['name'],128),NATIONS.index(m['country']),*map(int,ints),*floats,*boxes,*pivots)
 parents=model.parents();flags={};canonical={'Hull':1,('Turret' if kind=='tank' else 'GunMount'):2,'Gun':4,'Barrel_Recoil':8}
 for i,n in enumerate(g.nodes):flags[i]=canonical.get(n.name,0)
 for wh in r['wheels']:
  flags[wh['node']]|=(16 if wh['roadWheel'] else 512)|(128 if wh['side']=='left' else 256)
  if wh['roadWheel']:flags[wh['suspensionNode']]|=32
 for n in r['tracks']:flags[[x.name for x in g.nodes].index(n)]|=64
 records=[]
 def rec(parent,flag,n,verts=None,idx=None,material=None):
  pos=list(n.translation or [0,0,0]);rot=list(n.rotation or [0,0,0,1]);scale=n.scale or [1,1,1];pos[2]*=-1;rot[0]*=-1;rot[1]*=-1
  color,normal=-1,-1;factor=[1,1,1,1]
  if material is not None:
   p=material.pbrMetallicRoughness
   if p:
    factor=p.baseColorFactor or factor
    if p.baseColorTexture:color=g.textures[p.baseColorTexture.index].source
   if material.normalTexture:normal=g.textures[material.normalTexture.index].source
  return NODE.pack(parent,flag,*(pos+rot+list(scale)),len(verts) if verts is not None else 0,len(idx) if idx is not None else 0,color,normal,*factor,name(n.name or 'node',96))+(verts.astype('<f4').tobytes()+idx.astype('<u4').tobytes() if verts is not None else b'')
 for i,n in enumerate(g.nodes):records.append(rec(parents.get(i,-1),flags[i],n))
 for i,n in enumerate(g.nodes):
  if n.mesh is None:continue
  for pi,p in enumerate(g.meshes[n.mesh].primitives):
   v=model.array(p.attributes.POSITION).astype('<f4');normal=model.array(p.attributes.NORMAL).astype('<f4') if p.attributes.NORMAL is not None else np.tile([0,1,0],(len(v),1));uv=model.array(p.attributes.TEXCOORD_0) if p.attributes.TEXCOORD_0 is not None else np.zeros((len(v),2));idx=model.array(p.indices).reshape(-1).copy() if p.indices is not None else np.arange(len(v),dtype=np.uint32)
   if len(v)>65535 or len(idx)>600000:raise ValueError('单网格超过加载器容量；请拆分为不超过 65535 顶点的网格')
   v[:,2]*=-1;normal[:,2]*=-1;idx=idx.reshape(-1,3)[:,[0,2,1]].reshape(-1)
   from pygltflib import Node
   records.append(rec(i,0,Node(name=f'mesh_{i}_{pi}'),np.column_stack([v,normal,uv]),idx,g.materials[p.material] if p.material is not None else None))
 images=[]
 for image in g.images:
  bv=g.bufferViews[image.bufferView];b=bytes(model.blob[bv.byteOffset:bv.byteOffset+bv.byteLength])
  from PIL import Image
  with Image.open(io.BytesIO(b)) as im:
   if im.format not in ('PNG','JPEG') or max(im.size)>4096 or min(im.size)<1:raise ValueError('贴图须为 PNG/JPEG，边长不超过 4096')
   im.verify()
  if len(b)>16*1024*1024:raise ValueError('贴图超过 16 MB')
  images.append(struct.pack('<I',len(b))+b)
 if len(records)>2048 or len(images)>128:raise ValueError('模型或贴图数量超限')
 options=b''
 if kind!='tank':
  options=struct.pack('<8sIIfIi',b'HATCHOPT',28,1 if w.get('ballistics')=='stock-t34-85' else 0,t['turretRotation'],1 if kind=='tank-destroyer' else 2,t['gunTraverseHalfAngle'])
 elif w.get('ballistics','physical')!='physical' or int(t['turretRotation'])!=t['turretRotation']:
  options=struct.pack('<8sIIf',b'HATCHOPT',20,1 if w.get('ballistics')=='stock-t34-85' else 0,t['turretRotation'])
 payload=cfg+b''.join(records)+b''.join(images)+options;header=struct.pack('<8sIIII',MAGIC,1,24+len(payload),len(records),len(images));blob=header+payload
 if len(blob)>256*1024*1024:raise ValueError('运行时文件超过 256 MB')
 info={'id':m['id'],'name':m['displayName'],'nodes':len(records),'textures':len(images),'runtime_bytes':len(blob),'format':2,'loader':'Hatch','loader_version':'0.3','game_version':'5.1.0','abi':'arm64-v8a','animated_skinning':False,'type':'tank','requires':{'tankinvincible3000':'1.0'}}
 if options:info['runtime_options']=dict(version=2 if kind!='tank' else 1,ballistics=w.get('ballistics','physical'),turret_speed=t['turretRotation'])
 info['vehicle_kind']=kind
 if kind!='tank':info['horizontal_half_angle']=t['gunTraverseHalfAngle']
 if 'magazine' in w:info['magazine']=w['magazine']
 return blob,info
def pack_project(directory,output):
 data,info=compile_project(directory);out=Path(output);out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp')
 info['runtime_sha256']=hashlib.sha256(data).hexdigest()
 try:
  with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
   z.writestr('hatch.json',json.dumps(info,ensure_ascii=False,indent=2));z.writestr('runtime.bin',data)
   for filename in FILES:z.write(Path(directory)/filename,filename)
  tmp.replace(out)
 finally:tmp.unlink(missing_ok=True)
 return info
def main():
 p=argparse.ArgumentParser(description='Hatch 舱盖 0.3：将坦克项目/Tank Pack 转为可外置加载的 .hatch');p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.input.is_dir():result=pack_project(a.input,a.output)
 else:
  with tempfile.TemporaryDirectory() as temp:result=pack_project(extract_reviewed_pack(a.input,Path(temp)/'tank'),a.output)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()



