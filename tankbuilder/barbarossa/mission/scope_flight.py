"""Preserve the stock primary-launcher and gun-sight contracts in the two extra fields."""
import struct
from ...campaign_ugui import PTR, button_event, write_calls
from ...serialization import parse_complete as value, encode_complete
from ...unity_assets import pp, read_mb, write_mb
from .codec import part, cname, update

IMPORTED = {'T26', 'BT7', 'Panzer_II_Ausf_F', 'Panzer_IV_Ausf_C'}
SCOPE_PRESS = 'Hatch F Aim Press'

def primary(link, row, tank):
    """Launcher.Init copies the name and speed from UnitStatus only for an empty weaponName."""
    sf=link.sf; ids=row['controllers']; ident=ids['Launcher']; o=sf.objects[ident]
    gun=read_mb('Launcher',o.get_raw_data()); st=read_mb('UnitStatus',sf.objects[ids['UnitStatus']].get_raw_data())
    assert gun['uStatus']==pp(ids['UnitStatus'])
    if tank not in IMPORTED:
        assert gun['weaponName']==''  # untouched stock main gun
        return False
    assert st['unitName']==tank and st['mainGunName'] and gun['initSpeed']>0
    assert gun['weaponName'] in ('',st['mainGunName'])
    if gun['weaponName']:
        gun['weaponName']=''
        write_mb(link.add(o,ident,o.get_raw_data()),'Launcher',gun)
    return True

def optics(link,normal,trigger):
    sf=link.sf;wrap=trigger['wrapper'];visible=trigger['button']
    # The legacy hold poller reads the wrapper's rect; the actual UGUI pointer surface
    # stays on its full-size child. The vanilla display setter calls GetComponent<Button>
    # on the wrapper before touching the camera, including when closing the scope.
    wrect=part(sf,wrap,'RectTransform');vr=part(sf,visible,'RectTransform')
    assert value(sf.objects[wrect])['m_SizeDelta']==dict(x=0.,y=0.)
    std=value(normal.objects[wrap])['m_Component'];canvas,img,button=[x['component']['m_PathID'] for x in std[1:]]
    assert cname(sf.objects[img],link.names)=='Image' and cname(sf.objects[button],link.names)=='Button'
    assert PTR.unpack_from(sf.objects[button].get_raw_data())==(0,visible)
    current=value(sf.objects[visible])['m_Component'];present=[a['component']['m_PathID'] for a in current]
    assert present==[vr,canvas,img,button,trigger['events']]
    # Keep the real sprite/renderer on the pointer surface (including any references
    # held by the HUD). The restored root Selectable tints that same visible graphic.
    rc,ri=link.alloc(),link.alloc()
    cr=normal.objects[canvas];link.add(cr,rc,encode_complete(cr,dict(value(cr),m_GameObject=pp(wrap))))
    ir=normal.objects[img];link.add(ir,ri,ir.get_raw_data())
    b=sf.objects[button];br=bytearray(b.get_raw_data());PTR.pack_into(br,0,0,wrap)
    graphic,_,calls=button_event(br);assert not calls and PTR.unpack_from(br,graphic)==(0,img)
    link.add(b,button,bytes(br))
    update(sf,wrap,m_Component=[{'component':pp(k)} for k in (wrect,rc,ri,button)])
    update(sf,visible,m_Component=[a for a in current if a['component']['m_PathID']!=button])
    # Keep the original synchronous ButtonZoomInOut call. A single marker records
    # this exact press so only its 1x commander detent can advance to a gunner sight.
    aim=10454;atr=part(sf,aim,'RectTransform');go=link.alloc();tr=link.alloc()
    template=sf.objects[trigger['held']];rect=sf.objects[part(sf,trigger['held'],'RectTransform')]
    link.add(template,go,encode_complete(template,dict(value(template),m_Name=SCOPE_PRESS,m_Component=[{'component':pp(tr)}],m_IsActive=False)))
    link.add(rect,tr,encode_complete(rect,dict(value(rect),m_GameObject=pp(go),m_Father=pp(atr),m_Children=[])))
    update(sf,atr,m_Children=[*value(sf.objects[atr])['m_Children'],pp(tr)])
    ab=sf.objects[157147];raw=ab.get_raw_data();_,at,calls=button_event(raw)
    assert len(calls)==1 and calls[0][0]==(0,155487) and calls[0][2]=='ButtonZoomInOut'
    link.add(ab,ab.path_id,raw[:at]+struct.pack('<i',2)+write_calls([(go,True)])[4:]+raw[at+4:])
    return {'button':aim,'press':go,'hud_button':button,'visible':visible,'root':wrap,'graphic':img}

def verify_optics(sf,normal,info,trigger,names):
    wrap=info['root'];visible=info['visible'];go=info['press']
    def types(f,g):
        return [cname(o,names) if o.type.name=='MonoBehaviour' else o.type.name
                for e in value(f.objects[g])['m_Component'] for o in [f.objects[e['component']['m_PathID']]]]
    assert types(sf,wrap)==types(normal,wrap)==['RectTransform','CanvasRenderer','Image','Button']
    for ref in value(sf.objects[wrap])['m_Component']:
        assert PTR.unpack_from(sf.objects[ref['component']['m_PathID']].get_raw_data())==(0,wrap)
    assert types(sf,visible)==['RectTransform','CanvasRenderer','Image','EventTrigger']
    rb=sf.objects[info['hud_button']].get_raw_data();graphic,_,calls=button_event(rb)
    assert calls==[] and PTR.unpack_from(rb,graphic)==(0,info['graphic'])
    assert value(sf.objects[part(sf,visible,'RectTransform')])['m_SizeDelta']=={'x':100.,'y':100.}
    assert value(sf.objects[go])['m_Name']==SCOPE_PRESS and not value(sf.objects[go])['m_IsActive']
    callbacks=button_event(sf.objects[157147].get_raw_data())[2]
    assert len(callbacks)==2 and callbacks[0][0:3:2]==((0,go),'SetActive') and callbacks[0][9]==1
    assert callbacks[1:]==button_event(normal.objects[157147].get_raw_data())[2]
    for ident in (155487,154686,155486):assert sf.objects[ident].get_raw_data()==normal.objects[ident].get_raw_data()
    from .battleflow import check_trigger
    check_trigger(sf,trigger)

# A pooled main shell excludes the firing Transform.root. Scenario activation
# groups are not vehicles. Release each imported AI after the group has served
# its stock startup purpose; reserve timers still target those same GameObjects.
TRANSFORM = 'UnityEngine.Transform, UnityEngine.CoreModule'
def world_root_call(tr):
    from ...campaign_ugui import string
    return (PTR.pack(0,tr)+string(TRANSFORM)+string('set_parent')+struct.pack('<i',2)
            +PTR.pack(0,0)+string(TRANSFORM)+struct.pack('<if',0,0.)+string('')+struct.pack('<ii',0,2))

def actor_roots(link,side):
    sf=link.sf;schedule=side['schedule']['events'];target=side['scenario']
    emitted={}
    for phase in ('opening','wave2','relief'):
        rows=[u for u in side['units'] if u['phase']==phase and u['team']!='player' and u['tank'] in IMPORTED]
        if not rows:continue
        calls=b''.join(world_root_call(u['transform']) for u in rows)
        if phase=='opening':
            prev=sf.objects[schedule['wave2']['timer']];pid=link.alloc()
            assert cname(prev,link.names)=='TimedEvent'
            header=prev.get_raw_data()[:32];assert PTR.unpack_from(header)==(0,target)
            link.add(prev,pid,header+struct.pack('<fii',.25,1,len(rows))+calls)
            update(sf,target,m_Component=[*value(sf.objects[target])['m_Component'],{'component':pp(pid)}])
        else:
            pid=schedule[phase]['timer'];prev=sf.objects[pid];raw=bytearray(prev.get_raw_data())
            struct.pack_into('<i',raw,40,struct.unpack_from('<i',raw,40)[0]+len(rows))
            link.add(prev,pid,bytes(raw)+calls)
        emitted[phase]={'timer':pid,'transforms':[u['transform'] for u in rows]}
    return emitted

def verify_actor_roots(new,old,s):
    roots=s['vehicle_roots'];seen=set()
    for phase,ev in roots.items():
        trs=ev['transforms'];pid=ev['timer'];raw=new.objects[pid].get_raw_data()
        tail=b''.join(world_root_call(t) for t in trs)
        assert len(set(trs))==len(trs) and seen.isdisjoint(trs);seen.update(trs)
        if phase=='opening':
            assert struct.unpack_from('<fii',raw,32)==(.25,1,len(trs)) and raw[44:]==tail
        else:
            prev=old.objects[pid].get_raw_data();assert raw[:40]==prev[:40] and raw[44:]==prev[44:]+tail
            assert struct.unpack_from('<i',raw,40)[0]==struct.unpack_from('<i',prev,40)[0]+len(trs)
    targets={u['transform'] for u in s['units'] if u['team']!='player' and u['tank'] in IMPORTED}
    assert seen==targets
    for u in s['units']:
        assert value(new.objects[u['root']])['m_IsActive']==value(old.objects[u['root']])['m_IsActive']
        if u['transform'] not in seen:continue
        # Unity Transform.parent=null preserves the old world transform. The
        # logical unit/team and timer references remain the original IDs.
        assert value(new.objects[u['transform']])==value(old.objects[u['transform']])
        if u['phase']!='opening':assert u['root'] in s['schedule']['events'][u['phase']]['targets']
