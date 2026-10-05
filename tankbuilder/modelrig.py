"""Prepare the supplied T-54 GLB without altering the source file.

GLB keeps metres, Y-up and forward -Z. The Unity adapter reflects Z and
reverses triangle winding. Animation clips are demonstrations; gameplay uses
the original turret controller and the native suspension solver.
"""
import copy,json,math,re
from pathlib import Path
import numpy as np
from pygltflib import (GLTF2, Node, BufferView, Accessor, Animation,
    AnimationChannel, AnimationChannelTarget, AnimationSampler, Skin)

DTYPES={5120:'i1',5121:'u1',5122:'<i2',5123:'<u2',5125:'<u4',5126:'<f4'}
DIMS={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}

class Model:
    def __init__(self,path):
        self.g=GLTF2().load(str(path));self.blob=bytearray(self.g.binary_blob())
    def array(self,index):
        a=self.g.accessors[index];v=self.g.bufferViews[a.bufferView]
        dtype=np.dtype(DTYPES[a.componentType]);n=DIMS[a.type]
        stride=v.byteStride or n*dtype.itemsize
        return np.ndarray((a.count,n),dtype=dtype,buffer=self.blob,
            offset=v.byteOffset+a.byteOffset,strides=(stride,dtype.itemsize)).copy()
    def write_array(self,index,value):
        a=self.g.accessors[index];v=self.g.bufferViews[a.bufferView]
        dtype=np.dtype(DTYPES[a.componentType]);n=DIMS[a.type]
        view=np.ndarray((a.count,n),dtype=dtype,buffer=self.blob,
            offset=v.byteOffset+a.byteOffset,strides=(v.byteStride or n*dtype.itemsize,dtype.itemsize))
        view[:]=value
        if a.type=='VEC3':a.min=np.min(value,axis=0).tolist();a.max=np.max(value,axis=0).tolist()
    def add_array(self,value,kind='VEC3',component=5126):
        value=np.asarray(value,dtype=DTYPES[component]).reshape((-1,DIMS[kind]))
        self.blob.extend(b'\0'*((-len(self.blob))%4));off=len(self.blob)
        self.blob.extend(value.tobytes());vi=len(self.g.bufferViews)
        self.g.bufferViews.append(BufferView(buffer=0,byteOffset=off,byteLength=value.nbytes))
        ai=len(self.g.accessors);self.g.accessors.append(Accessor(bufferView=vi,componentType=component,count=len(value),type=kind,
            min=value.min(0).tolist(),max=value.max(0).tolist()))
        return ai
    def parents(self):return {c:i for i,n in enumerate(self.g.nodes) for c in (n.children or [])}
    def translation(self,index):
        ps=self.parents();t=np.zeros(3);seen=set()
        while True:
            if index in seen:raise ValueError('模型层级存在循环')
            seen.add(index)
            t+=self.g.nodes[index].translation or [0,0,0]
            if index not in ps:return t
            index=ps[index]
    def bounds(self,index):
        n=self.g.nodes[index];v=np.concatenate([self.array(p.attributes.POSITION) for p in self.g.meshes[n.mesh].primitives])
        return v.min(0)+self.translation(index),v.max(0)+self.translation(index)
    def save(self,path):
        self.g.buffers[0].byteLength=len(self.blob);self.g.set_binary_blob(bytes(self.blob));self.g.save_binary(str(path))

def prepare(input_path,output_directory):
    out=Path(output_directory);out.mkdir(parents=True,exist_ok=True)
    m=Model(input_path);g=m.g
    all_bounds=[m.bounds(i) for i,n in enumerate(g.nodes) if n.mesh is not None]
    lo=np.min([b[0] for b in all_bounds],0);hi=np.max([b[1] for b in all_bounds],0)
    body_hi=max(m.bounds(i)[1][1] for i,n in enumerate(g.nodes) if n.mesh is not None and n.name.startswith(('bone_turret','@root','body_','hatch_')))
    scale=np.array([3.27/(hi[0]-lo[0]),2.40/(body_hi-lo[1]),9.00/(hi[2]-lo[2])])
    done=set()
    for mesh in g.meshes:
        for p in mesh.primitives:
            if p.attributes.POSITION not in done:
                m.write_array(p.attributes.POSITION,m.array(p.attributes.POSITION)*scale);done.add(p.attributes.POSITION)
            if p.attributes.NORMAL is not None:
                v=m.array(p.attributes.NORMAL)/scale;v/=np.maximum(np.linalg.norm(v,axis=1,keepdims=True),1e-9)
                m.write_array(p.attributes.NORMAL,v)
    for n in g.nodes:
        if n.translation:n.translation=(np.asarray(n.translation)*scale).tolist()
    g.nodes[0].translation=[0.,float(-lo[1]*scale[1]),0.]
    wheels=[]
    for i,n in enumerate(g.nodes.copy()):
        if n.mesh is None or not n.name.startswith('wheel_'):continue
        vv=np.concatenate([m.array(p.attributes.POSITION) for p in g.meshes[n.mesh].primitives])
        center=(vv.min(0)+vv.max(0))*.5
        for p in g.meshes[n.mesh].primitives:
            m.write_array(p.attributes.POSITION,m.array(p.attributes.POSITION)-center)
        n.translation=center.tolist();n.rotation=[0.,0.,0.,1.]
        wheel={'node':i,'name':n.name,'center':m.translation(i).tolist(),
            'radius':float((vv.max(0)[1]-vv.min(0)[1])*.5),
            'side':'left' if '_l_' in n.name else 'right','roadWheel':bool(re.match(r'wheel_[lr]_\d\d_',n.name))}
        wheels.append(wheel)
        if wheel['roadWheel']:
            parent=m.parents()[i];anchor=len(g.nodes)
            g.nodes.append(Node(name='SuspensionAnchor_'+n.name,translation=center.tolist(),children=[i]))
            g.nodes[parent].children=[anchor if c==i else c for c in g.nodes[parent].children]
            n.translation=[0.,0.,0.];wheel['suspensionNode']=anchor
            wheel['restLocalPosition']=center.tolist()
    name_map={n.name:i for i,n in enumerate(g.nodes)}
    joints=[name_map['Hull']]+[w['suspensionNode'] for w in wheels if w['roadWheel']]
    inverse=[]
    for j in joints:
        mat=np.eye(4);mat[:3,3]=-m.translation(j);inverse.append(mat.T.reshape(-1))
    skin=len(g.skins);g.skins.append(Skin(name='Track_Suspension',joints=joints,
        skeleton=name_map['Hull'],inverseBindMatrices=m.add_array(inverse,'MAT4')))
    for i,n in enumerate(g.nodes):
        if n.name not in ('track_l_77','track_r_78'):continue
        n.skin=skin
        candidates=[(j+1,w) for j,w in enumerate([w for w in wheels if w['roadWheel']]) if w['side']==('left' if '_l_' in n.name else 'right')]
        for p in g.meshes[n.mesh].primitives:
            vertices=m.array(p.attributes.POSITION)+m.translation(i)
            js=np.zeros((len(vertices),4),dtype='<u2');ws=np.zeros((len(vertices),4));ws[:,0]=1
            for row,v in enumerate(vertices):
                if v[1]>.64:continue
                nearest=sorted(candidates,key=lambda x:abs(v[2]-x[1]['center'][2]))[:2]
                distances=np.array([max(abs(v[2]-x[1]['center'][2]),.05) for x in nearest])
                weights=(1/distances)/sum(1/distances)
                js[row,:2]=[x[0] for x in nearest];ws[row,:2]=weights
            p.attributes.JOINTS_0=m.add_array(js,'VEC4',5123);p.attributes.WEIGHTS_0=m.add_array(ws,'VEC4')
    gun_i=name_map['Gun'];gun_world=m.translation(gun_i)
    recoil_node=len(g.nodes);barrel_children=[i for i,n in enumerate(g.nodes) if n.name.startswith('gun_barrel')]
    g.nodes.append(Node(name='Barrel_Recoil',translation=[0.,0.,0.],children=barrel_children))
    g.nodes[gun_i].children=[i for i in g.nodes[gun_i].children if i not in barrel_children]+[recoil_node]
    barrel=[i for i,n in enumerate(g.nodes) if n.name.startswith('gun_barrel')]
    muzzle_z=min(m.bounds(i)[0][2] for i in barrel)
    tip=(m.bounds(barrel[-1])[0]+m.bounds(barrel[-1])[1])*.5;tip[2]=muzzle_z-.01
    mg_i=name_map['bone_mg_gun_twin_26'];mg_lo,mg_hi=m.bounds(mg_i)
    mg_tip=(mg_lo+mg_hi)*.5;mg_tip[2]=mg_lo[2]-.01
    def marker(name,world):
        idx=len(g.nodes);g.nodes.append(Node(name=name,translation=(world-gun_world).tolist()))
        g.nodes[gun_i].children.append(idx);return idx
    muzzle=marker('Muzzle_Main',tip);flash=marker('MuzzleFlash_Main',tip);marker('Muzzle_Coax_SGMT',mg_tip)
    g.nodes[gun_i].children=[i for i in g.nodes[gun_i].children if i not in (muzzle,flash)]
    g.nodes[recoil_node].children.extend([muzzle,flash])
    g.nodes[gun_i].extras={'axis':'local X','elevationDegrees':17,'depressionDegrees':4,'recoilMeters':.18}
    g.nodes[name_map['Turret']].extras={'axis':'local Y','rotationDegreesPerSecond':7}
    for i,n in enumerate(g.nodes):
        if n.name in ['track_l_77','track_r_78']:
            n.extras={'animation':'runtime UV scroll and suspension contact deformation','directionFrom':'leftTrackSpeed' if '_l_' in n.name else 'rightTrackSpeed'}
    def clip(name,channels):
        a=Animation(name=name,channels=[],samplers=[])
        for node,path,times,values in channels:
            ii=m.add_array(np.asarray(times).reshape((-1,1)),'SCALAR');oi=m.add_array(values,'VEC4' if path=='rotation' else 'VEC3')
            si=len(a.samplers);a.samplers.append(AnimationSampler(input=ii,output=oi,interpolation='LINEAR'))
            a.channels.append(AnimationChannel(sampler=si,target=AnimationChannelTarget(node=node,path=path)))
        g.animations.append(a)
    def quat(axis,degs):
        return [[*(np.eye(3)[axis]*math.sin(math.radians(d)*.5)),math.cos(math.radians(d)*.5)] for d in degs]
    clip('Turret_7deg_s',[ (name_map['Turret'],'rotation',[0,5,10,15,20],quat(1,[0,35,0,-35,0])) ])
    clip('Gun_Elevation_Limits',[(gun_i,'rotation',[0,4.25,9.5,10.5],quat(0,[0,17,-4,0]))])
    p=np.array(g.nodes[recoil_node].translation)
    clip('D10T_Recoil',[(recoil_node,'translation',[0,.05,.12,.35,9.7],[p.tolist(),(p+[0,0,.18]).tolist(),(p+[0,0,.18]).tolist(),p.tolist(),p.tolist()])])
    times=np.linspace(0,4,49);drive=[];sus=[]
    for w in wheels:
        deg=np.degrees(times*2.0/max(w['radius'],.1));drive.append((w['node'],'rotation',times,quat(0,deg)))
        if w['roadWheel']:
            anchor=w['suspensionNode'];p=np.array(g.nodes[anchor].translation);vs=[]
            for t in times:vs.append((p+[0,.10*math.sin(t*math.pi*2+w['center'][2]*1.5),0]).tolist())
            sus.append((anchor,'translation',times,vs))
    clip('Drive_Wheels_2m_s',drive);clip('Suspension_Travel_Demo',sus)
    g.asset.extras={'tank':'T-54 (1949)','units':'metres','forward':'-Z','widthMeters':3.27,'lengthMeters':9.0,
        'heightMetersExcludingRoofGunAndAntenna':2.4,'role':'player only','runtimeSuspension':'ten raycast spring-damper contacts'}
    rig={'format':1,'forward':'-Z','dimensions':{'length':9.0,'width':3.27,'heightWithoutRoofGunAndAntenna':2.4},
        'turret':{'node':name_map['Turret'],'pivot':m.translation(name_map['Turret']).tolist(),'speedDegSec':7.0},
        'gun':{'node':gun_i,'pivot':gun_world.tolist(),'elevation':17,'depression':4,'recoil':.18,'recoilNode':recoil_node},
        'muzzle':{'node':muzzle,'position':tip.tolist()},'coaxMuzzle':{'position':mg_tip.tolist()},
        'wheels':wheels,'tracks':['track_l_77','track_r_78'],
        'suspension':{'travel':.24,'restCompression':.12,'springPerWheel':290213.,'damperPerWheel':18000.,
            'totalMassKg':35500,'contacts':10,'solver':'raycast spring-damper forces on the hull Rigidbody'},
        'normalizationScale':scale.tolist()}
    m.save(out/'model.glb');(out/'rig.json').write_text(json.dumps(rig,indent=2)+'\n')
    return rig

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('output');a=p.parse_args()
    print(json.dumps(prepare(a.input,a.output),indent=2))
