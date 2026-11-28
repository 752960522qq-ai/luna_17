"""Refresh the eleven named AI assets, the two player assets and both playable field scenes."""
import io, json, zipfile, gc
from pathlib import Path
from types import SimpleNamespace
from ...extra_campaign import file, Scene
from ...serialization import parse_complete
from ...unity_assets import pp
from ...enemy_prefabs import create, ALL_DONORS
from ...enemy_visuals import read_model
from ...enemy_verify import verify as verify_ai
from ...bt7.integrate import reg
from ..bundle import append_members
from .. import layout
from . import SIDES
from .release import Members,dumps,digest
from .roster import stage,perspective
from .lanes import Lanes
from .buildscene import make
from .verify import verify

def context(pack):
    get=lambda n:file(pack.read(n))
    names={p:o.read_typetree(check_read=False)["m_ClassName"] for p,o in get("globalgamemanagers.assets").objects.items() if o.type.name=="MonoScript"}
    res=get("resources.assets"); stock=get("level8")
    wanted={*ALL_DONORS.values(),"T34_76_Player","Panzer_38t_Player","Panzer_III_J_AI","Panzer_38t_AI"}
    named={t:p for p,o in res.objects.items() if o.type.name=="GameObject" and (t:=parse_complete(o)["m_Name"]) in wanted}
    a=SimpleNamespace(sf=res,files={"resources.assets":res,"level8":stock},scripts={("globalgamemanagers.assets",p):n for p,n in names.items()},templates={})
    for o in res.objects.values():a.templates.setdefault(o.type.name,o)
    for e in res.externals:
        if e.path in pack.members and e.path not in a.files:a.files[e.path]=get(e.path)
    return a,named,names

def assets(apk, kit, work, changed):
    work.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(apk) as apkz, zipfile.ZipFile(kit) as k:
        data=apkz.read("assets/bin/Data/data.unity3d"); pack=Members(data)
        catalog=json.loads(k.read("AI/Hatch-Enemy-AI-index.json"));a,named,names=context(pack)
        for e in catalog["prefabs"]:
            ident=e["id"];print("AI",ident,flush=True)
            blob=changed[ident].read_bytes() if ident in changed else apkz.read("assets/Hatch/mods/"+ident+".hatch")
            with zipfile.ZipFile(io.BytesIO(blob)) as m:
                out=create(a,named,m,work)
                h=json.loads(m.read("hatch.json"));_,ns,ims=read_model(m.read("runtime.bin"),h)
                out["validation"]=verify_ai(a,work/out["file"],out,(ns,ims,h))
                e.update(out)
                if ident in ("T26","Panzer_II_Ausf_F"):
                    pl=create(a,named,m,work,player=True)
                    (work/(ident+"-player.json")).write_bytes(dumps(pl))
            del ns,ims;gc.collect()
        assert len(catalog["prefabs"])==11
        (work/"ai-index.json").write_bytes(dumps(catalog))

def finish(apk,kit,work):
    from . import fire_relay
    from ...campaign_ugui import string
    with zipfile.ZipFile(apk) as z, zipfile.ZipFile(kit) as k:
        prior=z.read("assets/bin/Data/data.unity3d");pack=Members(prior);get=lambda n:file(pack.read(n))
        a,named,names=context(pack)
        catalog=json.loads((work/"ai-index.json").read_bytes()); idx={e["id"]:e for e in catalog["prefabs"]}
        mgr=pack.read("globalgamemanagers")
        flag={}
        for e in idx.values():
            unit=e["id"].lower(); nation={"USSR":"so","Germany":"ge","UK":"uk","USA":"us"}[e["country"]]
            key="unit/"+nation+"/"+unit+"/"+unit
            e.setdefault("resource_path",key+"_ai"); e.setdefault("profile_resource_path",key+"_profile")
            print("register",e["id"],flush=True)
            mgr,_=reg(a,mgr,work/e["file"],e,refresh=True)
            if e["file"] not in pack.members:flag[e["file"]]="resources.assets"
        catalog["use"]="All eleven AI roots and their profiles are registered in Unity Resources."
        (work/"ai-index.json").write_bytes(dumps(catalog))
        (work/"registry-ai").write_bytes(mgr)
        relay,mgr=fire_relay.build(pack.read("level8"),mgr);flag[fire_relay.FILE]="resources.assets"
        (work/fire_relay.FILE).write_bytes(relay);(work/"globalgamemanagers").write_bytes(mgr)
        models={}
        for ident in ("T26","BT7","Panzer_II_Ausf_F","Panzer_IV_Ausf_C"):
            e=idx[ident];n=e["file"];models[ident,False]=(n,file((work/n).read_bytes()),e["root_path_id"])
        player_files=[]
        for ident in ("T26","Panzer_II_Ausf_F"):
            e=json.loads((work/(ident+"-player.json")).read_bytes());n=e["file"];player_files.append(n)
            models[ident,True]=(n,file((work/n).read_bytes()),e["root_path_id"])
        for ident in ("T34_76","Panzer_III_J","Panzer_38t"):
            models[ident,False]=("resources.assets",a.sf,named[ident+"_AI"])
        h=layout.heightgrid();props=layout.placements(h);dep=stage(h,props,legacy=True);Lanes(h,props).bake(dep)
        spec=json.loads(k.read("mission.json")); obj=spec["objective_position"]
        home=Scene(get("level0"),names); master=next(g for g,go in home.go.items() if go["m_Name"]=="Barbarossa 01 - Gates of Hell")
        txt,=[g for g in home.children(master) if "Text" in home.part[g]];raw=home.sf.objects[home.part[txt]["Text"]].get_raw_data()
        # The title is now bound to a local subset. Use the original project's
        # external stock font for the cloned template; buildscene subsequently binds the subset.
        stock_ui=get("level1"); orig=Scene(stock_ui,names)
        from ...extra_campaign import EMPTY_TEXT
        base=stock_ui.objects[orig.part[EMPTY_TEXT]["Text"]].get_raw_data()
        from ...campaign_ugui import PTR
        hdr=bytearray(raw[:144]); hdr[12]=1; hdr[88:100]=base[88:100]
        f,p=PTR.unpack_from(base,88);e=stock_ui.externals[f-1]
        fi=next(i for i,x in enumerate(home.sf.externals,1) if x.path==e.path);PTR.pack_into(hdr,88,fi,p)
        ui=(home,txt,bytes(hdr)+string("")); env=get("level21"); gui=get("sharedassets1.assets");fonts=get("sharedassets0.assets")
        for side in SIDES:
            print("scene",side.code,flush=True)
            rows=perspective(dep,side);cfg,b=make(get("level8"),env,models,rows,names,ui,obj,gui,fonts,h,props,side)
            spec["sides"][side.code].update(units=rows,**cfg);(work/side.member).write_bytes(b)
        spec["message_output"]="GameUiManager.SetMessageBox";(work/"mission.json").write_bytes(dumps(spec))
        members=["globalgamemanagers","level22","level23",fire_relay.FILE,*player_files,*[e["file"] for e in idx.values()]]
        print("encode",flush=True)
        del a,models,home,env,gui,fonts;gc.collect()
        result=append_members(prior,[(n,(work/n).read_bytes()) for n in members],flag)
        (work/"data.unity3d").write_bytes(result)
        info=json.loads(k.read("integration.json"));head,first,last=info["header_bytes"],info["retain_start"],info["retain_end"]
        assert head==first and prior[first:last]==result[first:last]
        overlay=result[:head]+result[last:];(work/info["overlay_file"]).write_bytes(overlay)
        info.update(prior_result_sha256=digest(prior),result_sha256=digest(result),overlay_sha256=digest(overlay));(work/"integration.json").write_bytes(dumps(info))
        print("reopen",flush=True)
        report=verify(result,prior,spec,names,refreshed=set(e["file"] for e in idx.values()))
        report["ai_nameplates"]=verify_plates(result,catalog,names)
        (work/"verification.json").write_bytes(dumps(report))

def verify_plates(bundle,catalog,names):
    import struct
    from .codec import cname
    pack=Members(bundle);r={}
    for e in catalog["prefabs"]:
        sf=file(pack.read(e["file"])); ids=[p for p,o in sf.objects.items() if o.type.name=="MonoBehaviour" and cname(o,names)=="UnitDisplay"]
        assert len(ids)==1,(e["id"],ids)
        rr=sf.objects[ids[0]].get_raw_data();go=struct.unpack_from("<iq",rr)[1]
        parts=[sf.objects[v["component"]["m_PathID"]] for v in parse_complete(sf.objects[go])["m_Component"]]
        tx,=[o for o in parts if o.type.name=="TextMesh"];mr,=[o for o in parts if o.type.name=="MeshRenderer"]
        label=parse_complete(tx)["m_Text"];render=parse_complete(mr)
        assert label.strip() and render["m_Enabled"] and render["m_Materials"] and struct.pack("<iq",0,tx.path_id) in rr,(e["id"],label)
        r[e["id"]]=label
    return r
