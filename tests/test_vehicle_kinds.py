"""Build small complete projects and execute the production parser and binder."""
import copy, json, struct, subprocess, tempfile, unittest
from pathlib import Path
from PIL import Image
from pygltflib import *
from hatch.pack import compile_project, pack_project
from hatch.package import validate
from tankbuilder.project import read_documents, validate_project, ROOT

def fixture(directory, kind):
    directory.mkdir(parents=True, exist_ok=True)
    docs=read_documents(ROOT/'tanks/T54_1949')
    docs['manifest'].update(id='CHECK_'+kind.replace('-','_'), displayName='Binding fixture',
        basePrefab={'tank':'T34_85_Player','tank-destroyer':'SU_85_Player','towed-gun':'ZiS_3_Player'}[kind])
    docs['tank'].update(vehicleKind=kind, gunTraverseHalfAngle=15, turretRotation=12,
        dimensionsMeters={'length':4,'width':2,'height':2})
    docs['weapon']['machineGun']['ammo']=0 if kind!='tank' else 30
    if kind=='towed-gun':
        docs['tank'].update(maxForwardSpeed=0,maxReverseSpeed=0,enginePower=0)
    mount='Turret' if kind=='tank' else 'GunMount'
    nodes=[Node(name='Hull',mesh=0,children=[1]),Node(name=mount,children=[2]),
        Node(name='Gun',mesh=0,children=[3]),Node(name='Barrel_Recoil',mesh=0)]
    wheels=[]
    for side in ('left','right'):
        for number in range(1 if kind=='towed-gun' else 2):
            i=len(nodes);nodes.append(Node(name=f'{side}_{number}',mesh=0))
            nodes[0].children.append(i)
            wheels.append(dict(node=i,suspensionNode=i,side=side,radius=.3,roadWheel=True))
    tracks=[]
    if kind!='towed-gun':
        for side in ('left','right'):
            i=len(nodes);name='Track_'+side;nodes.append(Node(name=name,mesh=0));nodes[0].children.append(i);tracks.append(name)
    import io
    image=io.BytesIO();Image.new('RGB',(2,2),'green').save(image,format='PNG')
    geometry=struct.pack('<9f3I',0,0,0,1,0,0,0,1,0,0,1,2)
    raw=geometry+image.getvalue()
    glb=GLTF2(asset=Asset(version='2.0'),scene=0,scenes=[Scene(nodes=[0])],nodes=nodes,
        buffers=[Buffer(byteLength=len(raw))],bufferViews=[BufferView(buffer=0,byteOffset=0,byteLength=36),BufferView(buffer=0,byteOffset=36,byteLength=12),BufferView(buffer=0,byteOffset=48,byteLength=len(image.getvalue()))],
        accessors=[Accessor(bufferView=0,componentType=5126,count=3,type='VEC3',min=[0,0,0],max=[1,1,0]),Accessor(bufferView=1,componentType=5125,count=3,type='SCALAR')],
        images=[ImageEntry(bufferView=2,mimeType='image/png')],textures=[Texture(source=0)],
        materials=[Material(pbrMetallicRoughness=PbrMetallicRoughness(baseColorTexture=TextureInfo(index=0)))],
        meshes=[Mesh(primitives=[Primitive(attributes=Attributes(POSITION=0),indices=1,material=0)])])
    glb.set_binary_blob(raw);glb.save_binary(directory/'model.glb')
    docs['rig']={'format':1,'forward':'-Z','turret' if kind=='tank' else 'mount':{'node':1,'pivot':[0,0,0]},
        'gun':{'node':2,'pivot':[0,0,0]},'muzzle':{'position':[0,0,-1]},'coaxMuzzle':{'position':[0,0,-1]},
        'wheels':wheels,'tracks':tracks,'colliders':{k:{'size':[1,1,1],'center':[0,0,0]} for k in ['hull','turret','unit']},
        'suspension':{'travel':.2,'restCompression':.1,'springPerWheel':50000,'damperPerWheel':18000}}
    for key,value in docs.items():(directory/(key+'.json')).write_text(json.dumps(value))
    Image.new('RGB',(8,8),'green').save(directory/'thumbnail.png')
    return docs

# Avoid the GLTF image class shadowing Pillow.
from pygltflib import Image as ImageEntry
from PIL import Image

class Vehicles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.base=Path(cls.temp.name)
        cls.binder=cls.base/'binder'
        subprocess.run(['gcc','-O2',str(ROOT/'tests/hatch_pipeline.c'),'-ldl','-lm','-o',str(cls.binder)],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_all_vehicle_types_compile_and_bind(self):
        for kind in ('tank','tank-destroyer','towed-gun'):
            with self.subTest(kind=kind):
                d=self.base/kind;fixture(d,kind)
                checked=validate_project(d);self.assertTrue(checked['valid'],checked['errors'])
                blob,doc=compile_project(d);runtime=d/'runtime.bin';runtime.write_bytes(blob)
                package=d/'vehicle.hatch';pack_project(d,package);self.assertEqual(validate(package)['loader_version'],'0.3')
                subprocess.run([str(self.binder),str(runtime)],check=True,capture_output=True,text=True)
                if kind!='tank':self.assertEqual(struct.unpack_from('<Ii',blob,len(blob)-8),(1 if kind=='tank-destroyer' else 2,15))
    def test_towed_gun_rejects_engine_and_tracks(self):
        d=self.base/'bad-gun';docs=fixture(d,'towed-gun');docs['tank']['enginePower']=1
        (d/'tank.json').write_text(json.dumps(docs['tank']))
        self.assertFalse(validate_project(d)['valid'])
        docs['tank']['enginePower']=0;(d/'tank.json').write_text(json.dumps(docs['tank']))
        docs['rig']['tracks']=['left_0'];(d/'rig.json').write_text(json.dumps(docs['rig']))
        self.assertFalse(validate_project(d)['valid'])
    def test_mount_must_not_contain_fixed_hull_mesh(self):
        d=self.base/'bad-mount';fixture(d,'tank-destroyer');g=GLTF2().load(d/'model.glb');g.nodes[1].mesh=0;g.save_binary(d/'model.glb')
        self.assertFalse(validate_project(d)['valid'])
    def test_horizontal_range_is_required(self):
        d=self.base/'bad-angle';docs=fixture(d,'tank-destroyer')
        for angle in (0,181,15.5,float('nan')):
            docs['tank']['gunTraverseHalfAngle']=angle;(d/'tank.json').write_text(json.dumps(docs['tank']))
            self.assertFalse(validate_project(d)['valid'])

if __name__=='__main__':unittest.main()
