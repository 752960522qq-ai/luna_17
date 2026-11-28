"""Check actual exported deck geometry, firing input, and inline battle nameplates."""
import json, math, zipfile
import numpy as np
from ...enemy_visuals import read_model
from ...extra_campaign import file
from ...serialization import parse_complete
from ...enemy_assets import subtree
from ...campaign_ugui import button_event, PTR
from ...t26_hull_hatch import HATCH
from .codec import cname
from .release import Members
from .fire_relay import KEY,FILE
from ...bt7.integrate import reg_object
from ...unity_assets import pp

def rig(before,after):
    def nodes(path):
        with zipfile.ZipFile(path) as z:return read_model(z.read('runtime.bin'),json.loads(z.read('hatch.json')))[1]
    old,new=nodes(before),nodes(after)
    assert len(new)==len(old)+3 and [n.name for n in old]==[n.name for n in new[:len(old)]]
    assert all((x.parent,x.trs)==(y.parent,y.trs) for x,y in zip(old,new))
    def ancestry(nodes,i):
        result=[]
        while i>=0:
            assert i not in result
            result.append(i);i=nodes[i].parent
        return result
    axis=next(i for i,n in enumerate(new) if n.name=='Turret')
    def posed(nodes,i,angle):
        p=nodes[i].vertices[nodes[i].indices.astype(int),:3].copy().astype(float)
        for j in ancestry(nodes,i):
            t=nodes[j].trs
            assert np.allclose(t[3:7],(0,0,0,1)) and np.allclose(t[7:10],(1,1,1))
            if j==axis:
                a=math.radians(angle);c,s=math.cos(a),math.sin(a)
                p=p@np.array([[c,0,-s],[0,1,0],[s,0,c]])
            p+=t[:3]
        return p
    def multiset(p):
        # Preserve winding and every triangle vertex; sort only across triangles.
        return sorted(np.round(p.reshape(-1,9),5).astype('<f8').view('|V72').ravel().tolist())
    for back in (False,True):
        i=next(j for j,n in enumerate(old) if n.name==('mesh_5_0_back' if back else 'mesh_5_0'))
        added=next(j for j,n in enumerate(new) if n.name==HATCH+('_Back' if back else '_Face'))
        assert axis not in ancestry(new,added) and axis in ancestry(new,i)
        lid=posed(new,added,0);rest=posed(new,i,0)
        assert len(lid)==3*174 and multiset(posed(old,i,0))==multiset(np.vstack((rest,lid)))
        for yaw in (-90,90,180):
            assert np.array_equal(lid,posed(new,added,yaw)) and not np.allclose(rest,posed(new,i,yaw))
    return {"deck_triangles_each_side":174,"hull_rotation_checks_degrees":[-90,90,180],"previous_rig_indices_preserved":len(old)}

def packaged(bundle,spec,catalog,names):
    game=Members(bundle);e={x["id"]:x for x in catalog["prefabs"]};matches={}
    registry=file(game.read('globalgamemanagers'));keys=dict(parse_complete(reg_object(registry))['m_Container'])
    for ent in e.values():
        f=next(i for i,x in enumerate(registry.externals,1) if x.path==ent["file"])
        assert keys[ent["resource_path"]]==pp(ent["root_path_id"],f) and keys[ent["profile_resource_path"]]==pp(ent["profile_path_id"],f)
    relay=file(game.read(FILE));g=keys[KEY];assert registry.externals[g["m_FileID"]-1].path==FILE
    raw=next(o.get_raw_data() for o in relay.objects.values() if o.type.name=="MonoBehaviour")
    call,=button_event(raw)[2];assert call[2]=="SetActive" and call[9]==1
    latch=parse_complete(relay.objects[call[0][1]]);assert latch["m_Name"]=="Shot Requested" and not latch["m_IsActive"]
    for side,info in spec["sides"].items():
        sf=file(game.read("level"+str(info["index"])));k=0
        assert not parse_complete(sf.objects[info["ui"]["opening"]])["m_IsActive"]
        live=PTR.unpack_from(sf.objects[155487].get_raw_data(),1660)
        assert live==(0,155469)
        fire,=button_event(sf.objects[155466].get_raw_data())[2]
        assert fire[0]==(0,155487) and fire[2]=="ButtonFire" and fire[6]==0
        for unit in info["units"]:
            if unit["team"]=="player" or unit["tank"] not in e:continue
            plate,=[ps for gid,ps,_ in subtree(sf,unit["root"]) if parse_complete(sf.objects[gid])["m_Name"]=="Name Display"]
            objs=[sf.objects[i] for i in plate];text,=[o for o in objs if o.type.name=="TextMesh"];rend,=[o for o in objs if o.type.name=="MeshRenderer"];disp,=[o for o in objs if o.type.name=="MonoBehaviour" and cname(o,names)=="UnitDisplay"]
            assert parse_complete(text)["m_Text"]==e[unit["tank"]]["name"] and parse_complete(rend)["m_Enabled"] and PTR.pack(0,text.path_id) in disp.get_raw_data()
            k+=1
        matches[side]=k
    return matches
