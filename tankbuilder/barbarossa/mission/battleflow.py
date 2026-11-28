"""Upgrade the cumulative mission without regenerating unrelated vehicle meshes."""
import struct, io
from ...campaign_ugui import PTR, read_string, write_calls
from ...enemy_assets import refs,subtree
from ...serialization import parse_complete as v,encode_complete
from ...unity_assets import read_mb,write_mb,pp
from .codec import Linker,update,part,cname
from .interface import event
from .objectives import decode

def pool(link, launcher, size=12):
    sf=link.sf;o=sf.objects[launcher];gun=read_mb("Launcher",o.get_raw_data());a=gun["shellApGos"]
    if len(a)>=size:return len(a)
    seed=a[0]["m_PathID"];nodes=list(subtree(sf,seed));roottr=nodes[0][2]
    ids=[i for go,parts,tr in nodes for i in (go,*parts)]
    mount=gun["thisTrf"]["m_PathID"];children=v(sf.objects[mount])["m_Children"].copy()
    assert v(sf.objects[roottr])["m_Father"]==pp(mount) and not v(sf.objects[seed])["m_IsActive"]
    while len(a)<size:
        to={i:link.alloc() for i in ids}
        def remap(ref):return pp(to[ref["m_PathID"]]) if not ref["m_FileID"] and ref["m_PathID"] in to else ref
        for i in ids:
            src=sf.objects[i]
            raw=(link.behaviour(src,remap) if src.type.name=="MonoBehaviour" else encode_complete(src,refs(v(src),remap)))
            link.add(src,to[i],raw)
        children.append(pp(to[roottr]));a.append(pp(to[seed]))
    update(sf,mount,m_Children=children)
    # install an editable reader: downstream release checks re-open these very bytes.
    edit=link.add(o,launcher,o.get_raw_data());write_mb(edit,"Launcher",gun)
    return len(a)

def rule_gate(sf,side,spec,link):
    base=spec["base"];pid=spec["objective_control"];o=sf.objects[pid];raw=bytearray(o.get_raw_data())
    _,pos=read_string(raw,56);_,los=read_string(raw,pos+12)
    early=bytearray(raw);early[12]=1
    struct.pack_into('<i',early,pos,0);struct.pack_into('<i',early,los,0)
    # Reserve waves cannot be lost before they exist; arrivals always count.
    copy=link.alloc();link.add(o,copy,bytes(early))
    update(sf,base,m_Component=v(sf.objects[base])["m_Component"]+[{"component":pp(copy)}])
    raw[12]=0;link.add(o,pid,bytes(raw));update(sf,part(sf,base,"SphereCollider"),m_Enabled=True)
    for name in ("wave2","relief"):
        row=spec["schedule"]["events"][name];clock=sf.objects[row["timer"]];b=clock.get_raw_data()
        tail=write_calls([(x,True) for x in row["targets"]])
        if name=="wave2":
            tail=struct.pack('<i',len(row["targets"])+2)+tail[4:]+event(copy,"UnityEngine.Behaviour, UnityEngine.CoreModule","set_enabled",6,flag=False)+event(pid,"UnityEngine.Behaviour, UnityEngine.CoreModule","set_enabled",6,flag=True)
        link.add(clock,clock.path_id,b[:40]+tail)
    spec["opening_objective_control"]=copy
    return copy

def check_pool(sf, launcher,names):
    gun=read_mb("Launcher",sf.objects[launcher].get_raw_data());mount=gun["thisTrf"];n=0
    assert part(sf,PTR.unpack_from(sf.objects[launcher].get_raw_data())[1],"Transform")==mount["m_PathID"]
    ids=set()
    for p in gun["shellApGos"]+gun["shellHeGos"]:
        go=p["m_PathID"];assert go not in ids;ids.add(go)
        tr=v(sf.objects[part(sf,go,"Transform")])
        shot=next(o for e in v(sf.objects[go])["m_Component"] if (o:=sf.objects[e["component"]["m_PathID"]]).type.name=="MonoBehaviour" and cname(o,names)=="ShellMove")
        assert PTR.unpack_from(shot.get_raw_data(),44)==(0,mount["m_PathID"]) and tr["m_Father"]==mount
        assert max(abs(x) for x in tr["m_LocalPosition"].values())<.0001 and tuple(tr["m_LocalRotation"].values())==(0.,0.,0.,1.)
        n+=1
    return n

def bind_trigger(link):
    """Reuse stock button art, placement, current control layout and Unity pointer events.
    The visibility wrapper has no hit area: the Luchs touch poller and the actual
    button can never both submit a shot for the same finger in this scene."""
    from ...campaign_ugui import button_event,clone_component
    sf=link.sf; stock=4057;rt=part(sf,stock,'RectTransform');root=sf.objects[stock];rect=sf.objects[rt]
    rectv=v(rect);gv=v(root);assert gv['m_Name']=='Button Fire' and rectv['m_AnchorMin']==rectv['m_AnchorMax']
    center={'x':.5,'y':.5};zero={'x':0.,'y':0.}
    def child(name,parent,dimensions,active):
        go=link.alloc();tr=link.alloc()
        link.add(root,go,encode_complete(root,dict(gv,m_Name=name,m_IsActive=active,m_Component=[{'component':pp(tr)}])))
        rv=dict(rectv,m_GameObject=pp(go),m_Father=pp(parent),m_Children=[],m_AnchorMin=center,m_AnchorMax=center,m_AnchoredPosition=zero,m_SizeDelta=dimensions)
        link.add(rect,tr,encode_complete(rect,rv));return go,tr
    button,t=child('Hatch F Trigger',rt,rectv['m_SizeDelta'],True)
    held,ht=child('Hatch F Held',t,zero,False);tap,tt=child('Hatch F Down',t,zero,False)
    template=sf.objects[158445];br=template.get_raw_data();assert cname(template,link.names)=='EventTrigger' and struct.unpack_from('<iii',br,32)==(2,2,1)
    def action(code,items):return struct.pack('<i',code)+write_calls(items)
    header=bytearray(br[:32]);PTR.pack_into(header,0,0,button);ev=link.alloc()
    link.add(template,ev,bytes(header)+struct.pack('<i',5)+action(2,[(held,True),(tap,True)])+action(3,[(held,False)])+action(1,[(held,False)])+action(16,[(held,False)])+action(15,[(tap,True)]))
    comps=gv['m_Component'][1:]
    for ref in comps:
        pid=ref['component']['m_PathID'];src=sf.objects[pid]
        if src.type.name=='MonoBehaviour':
            b=bytearray(src.get_raw_data())
            if cname(src,link.names)=='Button':
                assert button_event(b)[2][0][2]=='ButtonFire'
                b=bytearray(clone_component('Button',bytes(b),lambda f,p:(f,p),clicks=[]))
            PTR.pack_into(b,0,0,button);link.add(src,pid,bytes(b))
        else:update(sf,pid,m_GameObject=pp(button))
    update(sf,button,m_Component=[{'component':pp(t)},*comps,{'component':pp(ev)}])
    children=rectv['m_Children']
    for ch in children:update(sf,ch['m_PathID'],m_Father=pp(t))
    update(sf,t,m_Children=[*children,pp(ht),pp(tt)])
    update(sf,stock,m_Component=[{'component':pp(rt)}]);update(sf,rt,m_Children=[pp(t)],m_SizeDelta=zero)
    return dict(button=button,events=ev,held=held,down=tap,wrapper=stock)

def check_trigger(sf,info):
    from ...campaign_ugui import button_event
    h,d=info['held'],info['down']
    tail=struct.pack('<i',5)+b''.join(struct.pack('<i',k)+write_calls(x) for k,x in ((2,[(h,True),(d,True)]),(3,[(h,False)]),(1,[(h,False)]),(16,[(h,False)]),(15,[(d,True)])))
    assert sf.objects[info['events']].get_raw_data()[32:]==tail
    assert button_event(sf.objects[155466].get_raw_data())[2]==[]
    assert v(sf.objects[153814])['m_SizeDelta']=={'x':0.,'y':0.}
    assert v(sf.objects[part(sf,info['button'],'RectTransform')])['m_SizeDelta']=={'x':100.,'y':100.}
    assert not v(sf.objects[h])['m_IsActive'] and not v(sf.objects[d])['m_IsActive']
