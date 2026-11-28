"""Scene-owned scaled clocks. Reserves are visible, counted and damageable from the opening frame."""
import struct
from ...campaign_ugui import PTR,read_string
from ...serialization import parse_complete as val,encode_complete
from ...unity_assets import pp,xyz
from ..mission.codec import part,update,cname
from ..mission.interface import events,event
from ..mission.scope_flight import world_root_call
from . import RESERVES

BEHAVIOUR='UnityEngine.Behaviour, UnityEngine.CoreModule'
GAMEOBJECT='UnityEngine.GameObject, UnityEngine.CoreModule'
def active(go,on):return event(go,GAMEOBJECT,'SetActive',6,flag=on)

def fixture(l,par,name,enabled=True,pos=(0,0,0)):
    sf=l.sf;g,t=l.alloc(),l.alloc();src=sf.objects[791];tr=sf.objects[part(sf,791,'Transform')]
    gv=dict(val(src),m_Name=name,m_IsActive=enabled,m_Tag=0,m_Layer=0,m_Component=[{'component':pp(t)}]);l.add(src,g,encode_complete(src,gv))
    tv=dict(val(tr),m_GameObject=pp(g),m_Father=pp(par),m_Children=[],m_LocalPosition=xyz(pos),m_LocalScale=xyz((1,1,1)),m_LocalRotation=dict(x=0.,y=0.,z=0.,w=1.));l.add(tr,t,encode_complete(tr,tv))
    update(sf,par,m_Children=[*val(sf.objects[par])['m_Children'],pp(t)])
    return g,t

def add_component(sf,g,component):update(sf,g,m_Component=[*val(sf.objects[g])['m_Component'],{'component':pp(component)}])

def timer(l,owner,sec,actions,donor):
    assert actions and cname(donor,l.names)=='TimedEvent';raw=bytearray(donor.get_raw_data()[:32]);PTR.pack_into(raw,0,0,owner)
    f,p=PTR.unpack_from(raw,16);e=donor.assets_file.externals[f-1];PTR.pack_into(raw,16,l.external(e.path,e),p)
    ident=l.alloc();l.add(donor,ident,bytes(raw)+struct.pack('<fi',sec,1)+events(actions));add_component(l.sf,owner,ident);return ident

def orders(l,side,rows,base,donor):
    sf=l.sf;owner=side.scenario;anchor=part(sf,base,'Transform');early={}
    # A tank's arrival never awards victory here. Retain the stock NoEnemy result; death and time use GameControl.
    end=sf.objects[side.objective_control];b=bytearray(end.get_raw_data());_,a=read_string(b,56);_,c=read_string(b,a+12);struct.pack_into('<3i',b,a,1,0,0);struct.pack_into('<2i',b,c,0,0);b[12]=1;l.add(end,end.path_id,bytes(b));update(sf,part(sf,base,'SphereCollider'),m_Enabled=False)
    for nation in ('GE','SO'):
        reserve=[r for r in rows if r['nation']==nation and r['echelon']==2];assert reserve and all(r['team']!='player' for r in reserve)
        actions=[];pids=[]
        for row in reserve:
            pid=row['controllers']['AIControl'];o=sf.objects[pid];b=bytearray(o.get_raw_data());assert b[12]==1;b[12]=0;l.add(o,pid,bytes(b))
            actions.append(event(pid,BEHAVIOUR,'set_enabled',6,flag=True));pids.append(pid)
        marker,_=fixture(l,anchor,'Hatch Storm Reserve '+nation,False);actions.append(active(marker,True))
        early[nation]=dict(seconds=RESERVES[nation],ai=pids,marker=marker,timer=timer(l,owner,RESERVES[nation],actions,donor))
    # Keep the camera's selected hero in the player factory. All spawned AI can detach from the temporary scene group.
    trs=[r['transform'] for r in rows if r['team']!='player'];release=timer(l,owner,.25,[world_root_call(t) for t in trs],donor)
    return dict(reserves=early,release=release,transforms=trs)

def sight_press(l):
    # Keep the stock button and callback intact; record only this specific scope press.
    from ...campaign_ugui import button_event,write_calls
    sf=l.sf;button=sf.objects[157147];b=button.get_raw_data();_,at,calls=button_event(b)
    assert len(calls)==1 and calls[0][2]=='ButtonZoomInOut'
    marker,_=fixture(l,part(sf,10454,'RectTransform'),'Hatch F Aim Press',False)
    l.add(button,button.path_id,b[:at]+struct.pack('<i',2)+write_calls([(marker,True)])[4:]+b[at+4:])
    return marker
