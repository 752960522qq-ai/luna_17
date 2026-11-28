"""Extend the native campaign page with a second row; retain the original focus and back actions."""
import struct
from ...extra_campaign import Scene, PAGE_NAME
from ...campaign_ugui import PTR, clone_component, button_event, text_value, string
from ...enemy_assets import refs
from ...serialization import parse_complete as val, encode_complete
from ...unity_assets import pp
from ..mission.codec import Linker,part,kids,cname,update
from ..mission.interface import navigate,click,event,start,TIME
from ..mission.font import bind
from ..mission.lettering import install,check
from . import SIDES, TITLE
from .events import fixture,active

def second_row(sf,names,fonts,field8,gui):
    s=Scene(sf,names);lk=Linker(sf,names)
    page=next(g for g,t in s.go.items() if t['m_Name']==PAGE_NAME)
    _,_,slots,back=s.children(page); old=s.children(slots); par=s.rect[slots]
    assert [s.go[g]['m_Name'] for g in old]==['Barbarossa 01 - Gates of Hell','Gates of Hell - GE','Gates of Hell - SO']
    sides={x.code:x for x in SIDES}; ordered=[None,sides['GE'],sides['SO']]
    fresh=[];buttons=[]
    def layout(pid,x,y,w,h):update(sf,pid,m_AnchoredPosition=dict(x=x,y=y),m_SizeDelta=dict(x=w,y=h))
    for j,(root,side) in enumerate(zip(old,ordered)):
        units=[];skip=set()
        def walk(g):
            units.append(g)
            for c in s.children(g):
                if s.go[c]['m_Name']=='Fixed lettering':skip.add(s.rect[c]);continue
                walk(c)
        walk(root)
        ids={p:lk.alloc() for g in units for p in (g,*s.part[g].values())}
        ref=lambda f,p:(f,ids.get(p,p) if not f else p)
        def typed(v):return pp(*reversed(ref(v['m_FileID'],v['m_PathID'])))
        label=side.label if side else TITLE
        for g in units:
            src=sf.objects[g];tree=refs(val(src),typed)
            if g==root:tree['m_Name']='Stormbreak - '+side.code if side else 'Barbarossa 02 - Stormbreak'
            if s.go[g]['m_Name'].startswith('Hatch Start '):tree['m_Name']='Hatch Storm Start '+side.code
            lk.add(src,ids[g],encode_complete(src,tree))
            for kind,p in s.part[g].items():
                o=sf.objects[p]
                if o.type.name=='MonoBehaviour':
                    clicks=None
                    if kind=='Button':
                        calls=button_event(o.get_raw_data())[2];assert len(calls)==1 and calls[0][2]=='SetActive';clicks=[(ids[calls[0][0][1]],True)]
                    raw=clone_component(kind,o.get_raw_data(),ref,label=label,clicks=clicks)
                else:
                    t=val(o)
                    if 'm_Children' in t:t['m_Children']=[c for c in t['m_Children'] if c['m_PathID'] not in skip]
                    raw=encode_complete(o,refs(t,typed))
                lk.add(o,ids[p],raw)
        x=0 if not side else (-117 if side.code=='GE' else 117)
        layout(s.rect[root],x,100 if not side else 44,440 if not side else 218,42 if not side else 62)
        layout(ids[s.rect[root]],x,-39 if not side else -95,440 if not side else 218,42 if not side else 62)
        fresh.append(pp(ids[s.rect[root]]))
        if side:buttons.append((s.part[root]['Button'],ids[s.part[root]['Button']]))
    update(sf,par,m_Children=[*val(sf.objects[par])['m_Children'],*fresh]);back=s.part[back]['Button']
    (ag,bg),(az,bz)=buttons
    navigate(sf.objects[ag],right=az,down=bg);navigate(sf.objects[az],left=ag,down=bz)
    navigate(sf.objects[bg],right=bz,up=ag,down=back);navigate(sf.objects[bz],left=bg,up=az,down=back)
    navigate(sf.objects[back],up=bz)
    labels={TITLE,*[s.label for s in SIDES]};bind(lk,fonts,labels);install(lk,field8.objects[159011],gui.objects[121],labels)
    return sf.save()

def first_next(sf, normal, names, dest, fonts, gui):
    # Identify the stock Next button by its original action, not the shared Title action in the patched scene.
    hits=[]
    for p,o in normal.objects.items():
        if o.type.name!='MonoBehaviour' or cname(o,names)!='Button':continue
        if any(c[2]=='ButtonFunc' and c[3]==3 and c[6]==3 for c in button_event(o.get_raw_data())[2]):hits.append(p)
    assert set(hits)=={157146,161903,161932}
    lk=Linker(sf,names);labels=0
    mark=transfer(lk,'Hatch Storm Continue')
    for hit in hits:
        btn=sf.objects[hit];root=PTR.unpack_from(btn.get_raw_data())[1]
        btn=lk.add(btn,btn.path_id,btn.get_raw_data());click(btn,[active(mark,True)])
        todo=list(kids(sf,root))
        while todo:
            gid=todo.pop();todo+=kids(sf,gid)
            for c in val(sf.objects[gid])['m_Component']:
                o=sf.objects[c['component']['m_PathID']]
                if o.type.name=='MonoBehaviour' and cname(o,names)=='Text':
                    b=o.get_raw_data(); old=text_value(b);lk.add(o,o.path_id,b[:144]+string('Next' if old=='Title' else '下一关'));labels+=1
    assert labels
    if any(o.type.name=='MonoBehaviour' and cname(o,names)=='Text' and text_value(o.data or o.get_raw_data())=='下一关' for o in sf.objects.values()):
        bind(lk,fonts,{'下一关'});install(lk,normal.objects[159011],gui.objects[121],{'下一关'})
    return sorted(hits)

def transfer(l,name):
    root=next(o.path_id for o in l.sf.objects.values() if o.type.name=='GameObject' and o.peek_name()=='Barbarossa_Polesie_Summer')
    g,_=fixture(l,part(l.sf,root,'Transform'),name,False)
    return g

def retry(l,index):
    mark=transfer(l,'Hatch Campaign Retry')
    for i in [157017,164841]:
        ob=l.sf.objects[i];raw=ob.get_raw_data();calls=button_event(raw)[2]
        assert [x[2] for x in calls]==['set_timeScale','LoadScene'] and calls[1][6]==index
        obj=l.add(ob,i,raw);click(obj,[active(mark,True)])
    return mark
