"""Small forked sky flashes, with no physics or per-frame allocation."""
import numpy as np
from ...serialization import parse_complete as val,encode_complete
from ...unity_assets import pp
from ..native import Scene as MapScene
from ..mission.codec import part
from .events import fixture,add_component

def sky_bolts(l,anchor,side):
    sf=l.sf;mat=next(o for o in sf.objects.values() if o.type.name=='Material' and o.peek_name()=='Polesie_Weathered_Timber')
    old=val(mat);old.update(m_Name='Storm Sky Discharge',m_LightmapFlags=0,m_ValidKeywords=['_EMISSION'],m_InvalidKeywords=[])
    for key,v in old['m_SavedProperties']['m_TexEnvs']:v['m_Texture']=pp()
    for key,v in old['m_SavedProperties']['m_Colors']:
        if key in ('_Color','_EmissionColor'):v.update(r=1.15,g=1.30,b=1.55,a=1.)
    material=l.alloc();l.add(mat,material,encode_complete(mat,old))
    source=next(o for o in sf.objects.values() if o.type.name=='Mesh' and o.peek_name()=='barn_LOD1')
    class Model:
        def baseval(self,k):return val(source)
        def put(self,k,t):
            i=l.alloc();l.add(source,i,encode_complete(source,t));return i
    rend=next(o for o in sf.objects.values() if o.type.name=='MeshRenderer' and val(o)['m_Materials']==[pp(mat.path_id)])
    rv=val(rend);mf=sf.objects[part(sf,rv['m_GameObject']['m_PathID'],'MeshFilter')]
    points=[[0,124,0],[7,107,2],[3,99,3],[15,80,8],[10,70,9],[22,55,13],[14,49,13],[21,29,16],[16,20,17],[23,0,22]]
    branches=[(points,1.),([points[3],[-1,76,15],[-7,63,17],[-19,59,19]],.52),([points[5],[30,51,5],[33,44,0],[43,38,-4]],.42)]
    locations=[(-387,32,392),(-130,34,-235),(30,37,112)]
    out=[]
    for j,(x,y,z) in enumerate(locations):
        vertices=[];norms=[];uv=[];tri=[]
        for path,width in branches:
            arr=np.array(path,dtype=float);arr[:,0]*=1 if j!=1 else -1;arr[:,2]*=(j+1)*.63
            arr[:,1]*=(.86,1.,1.15)[j];arr[:,0]+=np.sin(arr[:,1]*.09+j)*j*2.2
            for i,(a,b) in enumerate(zip(arr,arr[1:])):
                direction=b-a;direction/=np.linalg.norm(direction);n=np.cross(direction,[1.,0.,0.]);n/=np.linalg.norm(n);v=np.cross(direction,n)
                ring=[np.cos(k*2*np.pi/5)*n+np.sin(k*2*np.pi/5)*v for k in range(5)]
                for k,normal in enumerate(ring):
                    other=ring[(k+1)%5];idx=len(vertices);r1=width*(1.-i/(len(path)*1.7));r2=width*(1.-(i+1)/(len(path)*1.7))
                    vertices.extend((a+r1*normal,a+r1*other,b+r2*other,b+r2*normal));norms.extend((normal,other,other,normal));uv.extend([(0,0),(1,0),(1,1),(0,1)])
                    tri.extend((idx,idx+1,idx+2,idx,idx+2,idx+3))
        mesh=MapScene.mesh(Model(),'Storm Fork '+str(j+1),tuple(np.array(q) for q in (vertices,norms,uv,tri)))
        go,_=fixture(l,anchor,'Hatch Storm Bolt '+str(j+1),False,(x,y,z))
        f=l.alloc();l.add(mf,f,encode_complete(mf,dict(val(mf),m_GameObject=pp(go),m_Mesh=pp(mesh))));add_component(sf,go,f)
        r=l.alloc();l.add(rend,r,encode_complete(rend,dict(rv,m_GameObject=pp(go),m_Materials=[pp(material)],m_Enabled=True,m_CastShadows=0,m_ReceiveShadows=False,m_DynamicOccludee=False,m_LightProbeUsage=0,m_ReflectionProbeUsage=0)));add_component(sf,go,r)
        out.append(dict(root=go,mesh=mesh,renderer=r))
    return out if side.code=='SO' else [out[1],out[0],out[2]]
