"""Reviewed player-prefab adapter for Attack on Tank 5.1.0.

Only derived Unity resources are written. No APK, signing or deployment occurs
in prepare_assets. Keep UnityPy pinned to the version used for round-trip QA.
"""
import copy,hashlib,io,json,struct,zipfile
from pathlib import Path
import numpy as np
import UnityPy
from PIL import Image
from UnityPy.files.ObjectReader import ObjectReader
from UnityPy.streams import EndianBinaryReader
from .modelrig import Model

ROOT=Path(__file__).resolve().parents[1]
BATTLE_PLAYER_SCENES=frozenset('level'+str(i) for i in range(8,20))
SCHEMA=json.loads((ROOT/'profiles/adapters/t54-5.1.0-serialization.json').read_text())['classes']
PRIMS={'bool':'?', 'u1':'B','i4':'i','u4':'I','f4':'f'}
class EditableObject(ObjectReader):
    def set_raw_data(self,data):
        super().set_raw_data(data)
        self.reader=EndianBinaryReader(data,endian='<');self.byte_start=0;self.byte_size=len(data)
    def save_typetree(self,tree,nodes=None,writer=None):
        # Unity 6000 adds fields beyond some UnityPy fallback type trees.
        # Preserve that opaque suffix, including its remapped references.
        old=self.get_raw_data();self.read_typetree(check_read=False)
        tail=old[self.Position-self.byte_start:]
        data=super().save_typetree(tree,nodes,writer)
        if tail:self.set_raw_data(data+tail)
        return self.data
def pp(pid=0,file=0):return {'m_FileID':file,'m_PathID':pid}
def xyz(v):return dict(zip('xyz',map(float,v)))
def aabb(v):return {'m_Center':xyz((v.min(0)+v.max(0))/2),'m_Extent':xyz((v.max(0)-v.min(0))/2)}
def decode_value(t,raw,off):
    k=t['type_name']
    if k=='array':
        n=struct.unpack_from('<i',raw,off)[0]
        if n<0 or n>2048:raise ValueError('Invalid serialized array')
        off+=4;v=[]
        for _ in range(n):x,off=decode_value(t['element'],raw,off);v.append(x)
        return v,off
    if k=='string':
        n=struct.unpack_from('<i',raw,off)[0]
        if n<0 or n>512:raise ValueError('Invalid serialized string')
        off+=4;return raw[off:off+n].decode('utf-8'),(off+n+3)&~3
    if t['kind']==0x12:return pp(struct.unpack_from('<q',raw,off+4)[0],struct.unpack_from('<i',raw,off)[0]),off+12
    if k in ('Vector3','Vector2'):
        n=3 if k=='Vector3' else 2;return list(struct.unpack_from('<'+'f'*n,raw,off)),off+n*4
    f=PRIMS.get(k,'i');return struct.unpack_from('<'+f,raw,off)[0],(off+struct.calcsize(f)+3)&~3

def encode_value(t,value):
    k=t['type_name']
    if k=='array':return struct.pack('<i',len(value))+b''.join(encode_value(t['element'],x) for x in value)
    if k=='string':
        raw=value.encode('utf-8');raw=struct.pack('<i',len(raw))+raw;return raw+b'\0'*((-len(raw))%4)
    if t['kind']==0x12:return struct.pack('<iq',value['m_FileID'],value['m_PathID'])
    if k in ('Vector3','Vector2'):return struct.pack('<'+'f'*len(value),*value)
    raw=struct.pack('<'+PRIMS.get(k,'i'),value);return raw+b'\0'*((-len(raw))%4)

def read_mb(cls,raw):
    values={};off=32
    for field in SCHEMA[cls]:values[field['name']],off=decode_value(field,raw,off)
    if off!=len(raw):raise ValueError(f'{cls} schema consumed {off}/{len(raw)} bytes')
    return values

def write_mb(obj,cls,values):
    raw=obj.get_raw_data()[:32]+b''.join(encode_value(t,values[t['name']]) for t in SCHEMA[cls])
    obj.set_raw_data(raw);read_mb(cls,raw)

def remap(tree,ids):
    if isinstance(tree,dict):
        if set(tree)=={'m_FileID','m_PathID'} and tree['m_FileID']==0:return pp(ids.get(tree['m_PathID'],tree['m_PathID']))
        return {k:remap(v,ids) for k,v in tree.items()}
    if isinstance(tree,list):return [remap(v,ids) for v in tree]
    return tree

class Adapter:
    def __init__(self,original):
        self.env=UnityPy.load(str(original));self.files={o.assets_file.name:o.assets_file for o in self.env.objects}
        self.sf=self.files['resources.assets'];self.next_id=max(self.sf.objects)+1
        self.templates={}
        for kind in ('Mesh','MeshFilter','MeshRenderer','SkinnedMeshRenderer','Texture2D','Material','GameObject','Transform'):
            obj=next((o for o in self.sf.objects.values() if o.type.name==kind),None)
            if not obj:obj=next(o for o in self.env.objects if o.type.name==kind)
            self.templates[kind]=obj
        self.scripts={(name,o.path_id):o.read_typetree(check_read=False)['m_ClassName'] for name,af in self.files.items() for o in af.objects.values() if o.type.name=='MonoScript'}
        self.created=[]
    def new(self,template,tree=None,raw=None):
        obj=object.__new__(EditableObject);obj.__dict__.update(template.__dict__);obj.assets_file=self.sf;obj.path_id=self.next_id;self.next_id+=1
        if template.assets_file is not self.sf:
            t=template.serialized_type
            index=next((i for i,x in enumerate(self.sf.types) if x.class_id==t.class_id),None)
            if index is None:index=len(self.sf.types);self.sf.types.append(copy.deepcopy(t))
            obj.type_id=index;obj.serialized_type=self.sf.types[index]
        obj.set_raw_data(raw if raw is not None else template.get_raw_data())
        self.sf.objects[obj.path_id]=obj;self.created.append(obj.path_id)
        if tree is not None:obj.save_typetree(tree)
        return obj
    def create(self,kind,tree):return self.new(self.templates[kind],tree=tree)
    def clone_player(self,root=3413):
        nodes=[]
        def visit(pid):
            go=self.sf.objects[pid];t=go.read_typetree(check_read=False);parts=[self.sf.objects[c['component']['m_PathID']] for c in t['m_Component']]
            tr=next(p for p in parts if p.type.name=='Transform');nodes.append((go,parts))
            for child in tr.read_typetree(check_read=False)['m_Children']:
                visit(self.sf.objects[child['m_PathID']].read_typetree(check_read=False)['m_GameObject']['m_PathID'])
        visit(root);ids={o.path_id:self.new(o).path_id for go,parts in nodes for o in [go]+parts}
        by_class={};by_name={}
        for go,parts in nodes:
            for old in [go]+parts:
                obj=self.sf.objects[ids[old.path_id]]
                if old.type.name=='MonoBehaviour':
                    raw=bytearray(old.get_raw_data())
                    for offset in range(0,len(raw)-11,4):
                        fid,pid=struct.unpack_from('<iq',raw,offset)
                        if fid==0 and pid in ids:struct.pack_into('<q',raw,offset+4,ids[pid])
                    obj.set_raw_data(bytes(raw));t=old.read_typetree(check_read=False);sp=t['m_Script'];script_file=self.sf if sp['m_FileID']==0 else self.files[self.sf.externals[sp['m_FileID']-1].path.rsplit('/',1)[-1]];cls=self.scripts.get((script_file.name,sp['m_PathID']))
                    by_class.setdefault(cls,[]).append(obj)
                else:
                    raw=bytearray(old.get_raw_data())
                    for offset in range(0,len(raw)-11,4):
                        fid,pid=struct.unpack_from('<iq',raw,offset)
                        if fid==0 and pid in ids:struct.pack_into('<q',raw,offset+4,ids[pid])
                    obj.set_raw_data(bytes(raw))
                    t=remap(old.read_typetree(check_read=False),ids)
                    if old.type.name=='MeshRenderer':t['m_Enabled']=False
                    if old.type.name=='LODGroup':t['m_Enabled']=False
                    obj.save_typetree(t)
            by_name[go.read_typetree(check_read=False)['m_Name']]=self.sf.objects[ids[go.path_id]]
        return ids,by_class,by_name
    def transform(self,go):
        return next(self.sf.objects[c['component']['m_PathID']] for c in go.read_typetree(check_read=False)['m_Component'] if self.sf.objects[c['component']['m_PathID']].type.name=='Transform')
    def reparent(self,tr,parent,translation):
        tree=tr.read_typetree(check_read=False);old=tree['m_Father']['m_PathID']
        if old:
            oldp=self.sf.objects[old];t=oldp.read_typetree(check_read=False);t['m_Children']=[p for p in t['m_Children'] if p['m_PathID']!=tr.path_id];oldp.save_typetree(t)
        tree.update(m_Father=pp(parent.path_id),m_LocalPosition=xyz(translation),m_LocalRotation=dict(x=0.,y=0.,z=0.,w=1.),m_LocalScale=xyz([1,1,1]));tr.save_typetree(tree)
        pt=parent.read_typetree(check_read=False);pt['m_Children'].append(pp(tr.path_id));parent.save_typetree(pt)
    def texture(self,model,index):
        image=model.g.images[index];view=model.g.bufferViews[image.bufferView]
        im=Image.open(io.BytesIO(bytes(model.blob[view.byteOffset:view.byteOffset+view.byteLength]))).convert('RGBA')
        im.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        # Unity image rows are bottom-up. UVs below reflect V to match glTF.
        data=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
        t=copy.deepcopy(self.templates['Texture2D'].read_typetree(check_read=False));t.update(m_Name='T54_1949_texture_'+str(index),m_Width=im.width,m_Height=im.height,m_TextureFormat=4,m_MipCount=1,m_CompleteImageSize=len(data),m_IsReadable=True,m_StreamingMipmaps=False)
        t['image data']=data;t['m_StreamData']={'offset':0,'size':0,'path':''};return self.create('Texture2D',t)
    def materials(self,model):
        textures={i:self.texture(model,i) for i in range(len(model.g.images))};materials=[]
        for i,mat in enumerate(model.g.materials):
            t=copy.deepcopy(self.templates['Material'].read_typetree(check_read=False));t['m_Name']='T54_1949_'+(mat.name or str(i));t['m_ValidKeywords']=[];t['m_InvalidKeywords']=[]
            p=mat.pbrMetallicRoughness;texture=model.g.textures[p.baseColorTexture.index].source if p and p.baseColorTexture else None
            for k,v in t['m_SavedProperties']['m_TexEnvs']:v['m_Texture']=pp(textures[texture].path_id) if k=='_MainTex' and texture is not None else pp()
            factor=p.baseColorFactor if p and p.baseColorFactor else [1,1,1,1]
            for k,v in t['m_SavedProperties']['m_Colors']:
                if k=='_Color':v.update(dict(zip('rgba',factor)))
            floats=dict(t['m_SavedProperties']['m_Floats']);floats['_Metallic']=float(p.metallicFactor or 0) if p else 0;floats['_Glossiness']=1-float(p.roughnessFactor or .8) if p else .2
            t['m_SavedProperties']['m_Floats']=[[k,v] for k,v in floats.items()];materials.append(self.create('Material',t))
        return materials
    def mesh(self,model,index,node):
        t=copy.deepcopy(self.templates['Mesh'].read_typetree(check_read=False));parts=model.g.meshes[index].primitives
        vertices=[];normals=[];uvs=[];weights=[];joints=[];indices=[];subs=[];start=0;first_byte=0;skinned=node.skin is not None
        for p in parts:
            v=model.array(p.attributes.POSITION);v[:,2]*=-1;n=model.array(p.attributes.NORMAL) if p.attributes.NORMAL is not None else np.tile([0,1,0],(len(v),1));n[:,2]*=-1
            uv=model.array(p.attributes.TEXCOORD_0) if p.attributes.TEXCOORD_0 is not None else np.zeros((len(v),2));uv[:,1]=1-uv[:,1]
            idx=model.array(p.indices).ravel().astype('<u4').reshape(-1,3)[:,[0,2,1]].ravel()+start
            vertices.append(v);normals.append(n);uvs.append(uv);indices.append(idx)
            subs.append({'firstByte':first_byte,'indexCount':len(idx),'topology':0,'baseVertex':0,'firstVertex':start,'vertexCount':len(v),'localAABB':aabb(v)})
            if skinned:weights.append(model.array(p.attributes.WEIGHTS_0));joints.append(model.array(p.attributes.JOINTS_0))
            start+=len(v);first_byte+=len(idx)*4
        vs=np.concatenate(vertices);channels=[dict(stream=0,offset=0,format=0,dimension=0) for _ in range(14)]
        for ch,offset,dim in [(0,0,3),(1,12,3),(4,24,2)]:channels[ch].update(offset=offset,dimension=dim)
        data=np.column_stack([vs,np.concatenate(normals),np.concatenate(uvs)]).astype('<f4').tobytes()
        if skinned:
            channels[12].update(stream=1,offset=0,dimension=4);channels[13].update(stream=1,offset=16,format=10,dimension=4)
            data+=b'\0'*((-len(data))%16)
            data+=b''.join(struct.pack('<4f4I',*w,*j) for w,j in zip(np.concatenate(weights),np.concatenate(joints)))
            mats=model.array(model.g.skins[node.skin].inverseBindMatrices).reshape(-1,4,4).transpose(0,2,1);reflect=np.diag([1,1,-1,1]);mats=reflect@mats@reflect
            t['m_BindPose']=[{f'e{r}{c}':float(mat[r,c]) for r in range(4) for c in range(4)} for mat in mats]
            t['m_BoneNameHashes']=[0]*len(mats);t['m_BonesAABB']=[{'m_Min':xyz(vs.min(0)),'m_Max':xyz(vs.max(0))}]*len(mats)
        else:t['m_BindPose']=[];t['m_BoneNameHashes']=[];t['m_BonesAABB']=[]
        t.update(m_Name='T54_1949_'+model.g.meshes[index].name,m_SubMeshes=subs,m_MeshCompression=0,m_IsReadable=True,m_IndexFormat=1,m_IndexBuffer=np.concatenate(indices).astype('<u4').tobytes(),m_VertexData={'m_VertexCount':len(vs),'m_Channels':channels,'m_DataSize':data},m_LocalAABB=aabb(vs),m_BakedConvexCollisionMesh=b'',m_BakedTriangleCollisionMesh=b'')
        t['m_StreamData']={'offset':0,'size':0,'path':''};return self.create('Mesh',t)
    def model(self,model,parent):
        node_gos={};node_trs={};renders={};materials=self.materials(model);parents=model.parents()
        for i,node in enumerate(model.g.nodes):
            go_t=copy.deepcopy(self.templates['GameObject'].read_typetree(check_read=False));go_t.update(m_Name='T54_'+node.name,m_Component=[],m_IsActive=True,m_Layer=0)
            go=self.create('GameObject',go_t);tr_t=copy.deepcopy(self.templates['Transform'].read_typetree(check_read=False));q=node.rotation or [0,0,0,1]
            tr_t.update(m_GameObject=pp(go.path_id),m_LocalPosition=xyz(np.array(node.translation or [0,0,0])*[1,1,-1]),m_LocalRotation=dict(zip('xyzw',[-q[0],-q[1],q[2],q[3]])),m_LocalScale=xyz(node.scale or [1,1,1]),m_Father=pp(),m_Children=[])
            tr=self.create('Transform',tr_t);go_t['m_Component']=[{'component':pp(tr.path_id)}];go.save_typetree(go_t);node_gos[i]=go;node_trs[i]=tr
        for i,node in enumerate(model.g.nodes):
            tr=node_trs[i];tree=tr.read_typetree(check_read=False);pt=node_trs[parents[i]] if i in parents else parent
            tree['m_Father']=pp(pt.path_id);tree['m_Children']=[pp(node_trs[x].path_id) for x in (node.children or [])];tr.save_typetree(tree)
            if i not in parents:t=parent.read_typetree(check_read=False);t['m_Children'].append(pp(tr.path_id));parent.save_typetree(t)
            if node.mesh is None:continue
            mesh=self.mesh(model,node.mesh,node);kind='SkinnedMeshRenderer' if node.skin is not None else 'MeshRenderer'
            rt=copy.deepcopy(self.templates[kind].read_typetree(check_read=False));rt.update(m_GameObject=pp(node_gos[i].path_id),m_Enabled=True,m_Materials=[pp(materials[p.material or 0].path_id) for p in model.g.meshes[node.mesh].primitives],m_LightmapIndex=65535,m_LightmapIndexDynamic=65535,m_StaticBatchRoot=pp(),m_LightmapTilingOffset=dict(x=1.,y=1.,z=0.,w=0.))
            if kind=='SkinnedMeshRenderer':
                skin=model.g.skins[node.skin];rt.update(m_Mesh=pp(mesh.path_id),m_Bones=[pp(node_trs[j].path_id) for j in skin.joints],m_RootBone=pp(node_trs[skin.skeleton].path_id),m_AABB=mesh.read_typetree(check_read=False)['m_LocalAABB'],m_UpdateWhenOffscreen=True)
            renderer=self.create(kind,rt);renders[i]=renderer
            gt=node_gos[i].read_typetree(check_read=False);gt['m_Component'].append({'component':pp(renderer.path_id)})
            if kind=='MeshRenderer':
                mf=self.create('MeshFilter',{'m_GameObject':pp(node_gos[i].path_id),'m_Mesh':pp(mesh.path_id)});gt['m_Component'].append({'component':pp(mf.path_id)})
            node_gos[i].save_typetree(gt)
        return node_gos,node_trs,renders

def prepare_assets(original,pack_directory,destination,log=print):
    original=Path(original);directory=Path(pack_directory);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    profile=json.loads((ROOT/'profiles/attack-on-tank-5.1.0.json').read_text())
    before=hashlib.sha256(original.read_bytes()).hexdigest()
    expected=profile.get('unity_data_sha256') or profile.get('data_sha256')
    if not expected:raise ValueError('Resource adapter requires an original data.unity3d SHA-256')
    if expected and before!=expected:raise ValueError('Unity resource fingerprint differs from the reviewed 5.1.0 adapter')
    manifest=json.loads((directory/'manifest.json').read_text());rig=json.loads((directory/'rig.json').read_text())
    if manifest.get('id')!='T54_1949' or manifest.get('role')!='player':raise ValueError('This adapter supports only the reviewed player T54_1949 pack')
    log('Loading original Unity data…');adapter=Adapter(original);sf=adapter.sf
    ids,classes,names=adapter.clone_player();root=sf.objects[ids[3413]];root_tr=adapter.transform(root)
    root_t=root.read_typetree(check_read=False);root_t['m_Name']='T54_1949_Player';root.save_typetree(root_t)
    model=Model(directory/'model.glb');ng,nt,renderers=adapter.model(model,root_tr);byname={n.name:i for i,n in enumerate(model.g.nodes)}
    turret=nt[byname['Turret']];gun=nt[byname['Gun']]
    # Keep the game's functional components and collision regions; move them
    # with the new rig and disable the inherited visual meshes.
    old_turret=sf.objects[ids[36511]];old_gun=sf.objects[ids[36457]]
    adapter.reparent(old_turret,turret,[0,0,0]);adapter.reparent(old_gun,gun,[0,0,0])
    fire=sf.objects[ids[36598]]
    muzzle_local=np.asarray(rig['muzzle']['position'])-np.asarray(rig['gun']['pivot']);muzzle_local[2]*=-1
    adapter.reparent(fire,nt[byname['Barrel_Recoil']],muzzle_local)
    machine=sf.objects[ids[48323]];coax_local=np.asarray(rig['coaxMuzzle']['position'])-np.asarray(rig['gun']['pivot']);coax_local[2]*=-1
    adapter.reparent(machine,gun,coax_local)
    # Original muzzle particle systems and AudioSources remain on FirePoint.
    pc=classes['PlayerControl'][0];v=read_mb('PlayerControl',pc.get_raw_data());v['turretTrf']=pp(turret.path_id);v['gunTrf']=pp(gun.path_id);write_mb(pc,'PlayerControl',v)
    tm=classes['TurretMove'][0];v=read_mb('TurretMove',tm.get_raw_data());v['thisTrf']=pp(turret.path_id);v['gunTrfs']=[pp(gun.path_id)];write_mb(tm,'TurretMove',v)
    status=classes['UnitStatus'][0];v=read_mb('UnitStatus',status.get_raw_data());v.update(unitName='T54_1949',mainGunName='D-10T',angleOfElevation=17,angleOfDip=4,weight=35.5,unitNation=0,rTrackMoves=[],sTrackMeshes=[],sTrackMeshFilters=[]);write_mb(status,'UnitStatus',v)
    bm=classes['BodyMove'][0];v=read_mb('BodyMove',bm.get_raw_data());road=[w for w in rig['wheels'] if w['roadWheel']]
    tracks=[byname[x] for x in rig['tracks']]
    v.update(partsTransforms=[],scrollLodRends=[pp(renderers[x].path_id) for x in tracks],smallWheelLodTrfs=[pp(nt[w['node']].path_id) for w in rig['wheels'] if not w['roadWheel']],largeWheelLodTrfs=[pp(nt[w['node']].path_id) for w in road],susWheelTrfs=[pp(nt[w['suspensionNode']].path_id) for w in road],susMaxAmp=.12,gearRatio=1.,CircumferenceRatio=1,trackNum=5,_currentTrack=1)
    # Real-track mesh GO is inherited but hidden; scroll-track mode drives the
    # new skinned meshes and independently rotates the left/right wheel arrays.
    v['scrollTrackGo']=pp(ng[byname['Hull']].path_id);v['realTrackGo']=pp(ids[v['realTrackGo']['m_PathID']]) if v['realTrackGo']['m_PathID'] in ids else v['realTrackGo']
    write_mb(bm,'BodyMove',v)
    for launcher in classes['Launcher']:
        v=read_mb('Launcher',launcher.get_raw_data());v.update(weaponName='D-10T',attackPower=212,initSpeed=895.,calibre=100,fireSize=2,barrelTrf=pp(nt[byname['Barrel_Recoil']].path_id));write_mb(launcher,'Launcher',v)
    rigid=sf.objects[ids[116152]];v=rigid.read_typetree(check_read=False);v['m_Mass']=35500.;rigid.save_typetree(v)
    hull_box=sf.objects[ids[116985]];v=hull_box.read_typetree(check_read=False);v['m_Size']=xyz([3.1,1.4,5.85]);v['m_Center']=xyz([0,.8,0]);hull_box.save_typetree(v)
    tur_box=sf.objects[ids[117038]];v=tur_box.read_typetree(check_read=False);v['m_Size']=xyz([2.45,.95,2.5]);v['m_Center']=xyz([0,.25,0]);tur_box.save_typetree(v)
    unit_box=sf.objects[ids[117214]];v=unit_box.read_typetree(check_read=False);v['m_Size']=xyz([3.4,2.8,6.4]);v['m_Center']=xyz([0,1.4,0]);unit_box.save_typetree(v)
    # Reuse the game's vehicle engine, turret drive, reload, 100 mm gun and
    # machine-gun samples. They are existing licensed game assets, not alleged
    # historic recordings supplied by this mod.
    clips={o.read_typetree(check_read=False)['m_Name']:o for o in sf.objects.values() if o.type.name=='AudioClip'}
    audio_report=[]
    for old_id,role,sample,loop,awake in (
        (117866,'engine acceleration','accel_t34',False,False),
        (118229,'engine loop','engine_loop_01_l',True,True),
        (117835,'main gun','fire_type5_g_02',False,False),
        (117919,'turret drive','turret_move_m',True,False),
        (117961,'coaxial machine gun','MG_02',False,False),
    ):
        o=sf.objects[ids[old_id]];t=o.read_typetree(check_read=False)
        clip=pp(clips[sample].path_id)
        # Unity 6000 stores its active clip in m_Resource; keep both fields
        # consistent for the engine's AudioSource.get_clip/PlayOneShot paths.
        t.update(m_audioClip=clip,m_Resource=clip,Loop=loop,m_PlayOnAwake=awake)
        o.save_typetree(t)
        audio_report.append({'source':o.path_id,'clip':sample,'clip_path_id':clip,'role':role,'reused_game_sample':True})
    audio_report.append({'role':'reload','clip':'loading_noise_02','binding':'original UnitMove.PlayLoadingNoise path','reused_game_sample':True})
    registrations=[]
    for filename,af in adapter.files.items():
        # level7 is the original selection screen: it instantiates every
        # catalog entry before a tank is selected. Custom vehicles belong to
        # the battle catalogs used by the mod menu, not its stock UI mapping.
        if filename not in BATTLE_PLAYER_SCENES:continue
        resources_id=next((i+1 for i,e in enumerate(af.externals) if e.path.rsplit('/',1)[-1]=='resources.assets'),None)
        if not resources_id:continue
        for obj in list(af.objects.values()):
            if obj.type.name!='MonoBehaviour':continue
            t=obj.read_typetree(check_read=False);sp=t['m_Script']
            scfile=af if sp['m_FileID']==0 else adapter.files[af.externals[sp['m_FileID']-1].path.rsplit('/',1)[-1]]
            script=scfile.objects.get(sp['m_PathID'])
            if not script or script.type.name!='MonoScript' or script.read_typetree(check_read=False)['m_ClassName']!='TankGenManager':continue
            raw=obj.get_raw_data();n=struct.unpack_from('<i',raw,44)[0]
            if n<1 or n>128:raise ValueError('TankGenManager player array schema differs')
            at=48+12*n;changed=raw[:44]+struct.pack('<i',n+1)+raw[48:at]+struct.pack('<iq',resources_id,root.path_id)+raw[at:]
            obj.set_raw_data(changed);registrations.append({'scene':filename,'generator':obj.path_id,'player_index':n,'new_count':n+1,'ai_arrays_unchanged':True})
    if len(registrations)!=12:raise ValueError('Expected the 12 reviewed battle player catalogs')
    log('Writing derived Unity bundle…')
    bundle=next(f for f in adapter.env.files.values() if hasattr(f,'save_fs'));output=destination/'data.unity3d';output.write_bytes(bundle.save(packer='lz4'))
    if hashlib.sha256(original.read_bytes()).hexdigest()!=before:raise AssertionError('Original resources changed')
    report={'adapter':'aot-5.1.0-arm64-v1','status':'assets_prepared','input_sha256':before,'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'output':str(output),'player_prefab_id':root.path_id,'new_objects':len(adapter.created),'model_nodes':len(model.g.nodes),'model_meshes':len(model.g.meshes),'skinned_tracks':2,'suspension_contacts':10,'registrations':registrations,'audio':audio_report,'apk_packaged':False,'android_device_test':'not performed'}
    (destination/'asset_report.json').write_text(json.dumps(report,indent=2)+'\n');log('Prepared '+str(output));return report
