"""A nonvisual, stock UGUI click latch for short taps between Unity frame callbacks."""
import copy
from ...extra_campaign import file
from ...bt7.integrate import reg_object
from ...serialization import parse_complete,encode_complete
from ...campaign_ugui import clone_component,button_event
from ...unity_assets import pp
from .codec import part

KEY="hatch/controls/autocannonrelay"
FILE="HatchAutocannonRelay.assets"

def build(field,manager):
    sf=file(field)
    root,child,button=4057,4030,155466
    tr,ct=[part(sf,g,"RectTransform") for g in (root,child)]
    def put(pid,**changes):
        o=sf.objects[pid]; v=parse_complete(o);v.update(changes);o.set_raw_data(encode_complete(o,v))
    for g,t,n,active in ((root,tr,"Hatch Autocannon Relay",True),(child,ct,"Shot Requested",False)):
        put(g,m_Name=n,m_IsActive=active,m_Component=[{"component":pp(i)} for i in ([t,button] if g==root else [t])])
        put(t,m_GameObject=pp(g),m_Father=pp(tr if g==child else 0),m_Children=[pp(ct)] if g==root else [])
    btn=sf.objects[button]; raw=clone_component("Button",btn.get_raw_data(),lambda f,p:(f,p) if f or p==root else (0,0),clicks=[(child,True)])
    btn.set_raw_data(raw)
    assert button_event(raw)[2][0][2]=="SetActive"
    sf.objects={i:sf.objects[i] for i in (root,child,tr,ct,button)}
    # No scene-local MonoScript IDs; the type's script reference remains to the stock UI assembly.
    from ...campaign_ugui import PTR
    script_f,script_p=PTR.unpack_from(raw,16)
    assert script_f and script_p
    binary=sf.save(); reread=file(binary)
    assert len(reread.objects)==5 and not parse_complete(reread.objects[child])["m_IsActive"]
    mg=file(manager);o=reg_object(mg);v=parse_complete(o); names={e.path:i for i,e in enumerate(mg.externals,1)}
    assert FILE not in names and KEY not in dict(v["m_Container"])
    ext=copy.copy(mg.externals[names["resources.assets"]-1]);ext.path=FILE;mg.externals.append(ext)
    me=len(mg.externals);script_name=sf.externals[script_f-1].path
    if script_name not in names:
        mg.externals.append(copy.copy(sf.externals[script_f-1]));names[script_name]=len(mg.externals)
    v["m_Container"]=sorted([*v["m_Container"],(KEY,pp(root,me))],key=lambda x:x[0])
    for p,deps in ((root,[pp(tr,me),pp(button,me)]),(tr,[pp(root,me),pp(ct,me)]),(ct,[pp(child,me),pp(tr,me)]),(child,[pp(ct,me)]),(button,[pp(root,me),pp(child,me),pp(script_p,names[script_name])])):
        v["m_DependentAssets"].append({"m_Object":pp(p,me),"m_Dependencies":deps})
    o.set_raw_data(encode_complete(o,v));result=mg.save()
    assert dict(parse_complete(reg_object(file(result)))["m_Container"])[KEY]==pp(root,me)
    return binary,result
