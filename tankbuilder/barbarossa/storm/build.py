"""Build two faction-specific fields against the staged T-28 game. No APK rebuild or signing."""
import argparse,gc,io,json,struct,zipfile
from pathlib import Path
from ...extra_campaign import file,Scene,EMPTY_TEXT
from ...serialization import parse_complete as val, encode_complete
from ...campaign_ugui import PTR,string
from ...unity_assets import pp
from ...enemy_prefabs import create
from ...bt7.integrate import reg
from ..mission.refit import context
from ..mission.release import Members,digest,dumps
from ..mission.codec import Linker,part,kids,update
from ..mission.buildscene import make,attach,erase
from ..mission.scope_flight import world_root_call,primary
from .. import layout
from ..bundle import append_members,metadata
from . import SIDES, PZ3,PZ2,PZ4,DEADLINE
from .deployment import deployment
from .menu import second_row,first_next,retry
from .weather import install as weather
from .sound import write_banks
from .events import sight_press

def first(sf,doc,model,names,stock,side,fonts,gui):
    l=Linker(sf,names);cfg=doc['sides'][side.code];rows=[x for x in cfg['units'] if x['tank']=='Panzer_III_J'];assert len(rows)==3
    extra=[]
    for row in rows:
        root,tr=row['root'],row['transform'];r=val(sf.objects[tr]);parent=r['m_Father']['m_PathID'];was=val(sf.objects[root])['m_IsActive'];assert row['phase']=='wave2' and not was
        orig=val(sf.objects[parent])['m_Children'];update(sf,parent,m_Children=[p for p in orig if p!=pp(tr)]);erase(sf,root)
        row['id']=row['id'].replace('Panzer_III_J',PZ3);row['tank']=PZ3;fn,src,g=model
        attach(l,src,fn,g,parent,row,keep_roots=(root,tr));update(sf,root,m_IsActive=was);update(sf,parent,m_Children=orig)
        assert val(sf.objects[tr])['m_Father']==r['m_Father'];extra.append(tr)
    ev=cfg['vehicle_roots']['wave2'];o=sf.objects[ev['timer']];b=bytearray(o.get_raw_data());struct.pack_into('<i',b,40,struct.unpack_from('<i',b,40)[0]+3);l.add(o,o.path_id,bytes(b)+b''.join(world_root_call(t) for t in extra));ev['transforms']+=extra
    cfg['next_button']=first_next(sf,stock,names,side,fonts,gui);cfg['retry']=retry(Linker(sf,names),side.index-2);return sf.save()

def build(staged,apk,mission,out,recordings=None):
    out.mkdir(parents=True,exist_ok=True);cache=out/'members';cache.mkdir(exist_ok=True);t=json.loads((staged/'T28-Integration.json').read_text());raw=(staged/'assets/bin/Data/data.unity3d').read_bytes();assert digest(raw)==t['resultResourceSha256']
    p=Members(raw);get=lambda n:file(p.read(n));a,named,names=context(p);stock=a.files['level8'];ai={x['id']:x for x in t['aiIndex']['prefabs']};models={}
    with zipfile.ZipFile(apk) as zp:
        original=zp.read('assets/bin/Data/data.unity3d');assert digest(original)==t['baseResourceSha256'];bt=zp.read('assets/Hatch/mods/BT7.hatch')
    with zipfile.ZipFile(io.BytesIO(bt)) as mod:e=create(a,named,mod,cache,player=True)
    e.update(resource_path='unit/so/bt7/bt7_player',profile_resource_path='unit/so/bt7/bt7_player_profile');mgr,_=reg(a,p.read('globalgamemanagers'),cache/e['file'],e)
    for k in ('BT7','T26','T28',PZ2,PZ3,PZ4):
        n=ai[k];models[k,False]=(n['file'],get(n['file']),n['root_path_id'])
    models['BT7',True]=(e['file'],file((cache/e['file']).read_bytes()),e['root_path_id']);pz=t['requiredVehicles'];assert PZ3+'.hatch' in pz
    f=PZ3+'_Player.assets';pf=get(f);g,=[o.path_id for o in pf.objects.values() if o.type.name=='GameObject' and o.peek_name()==PZ3+'_Player'];models[PZ3,True]=(f,pf,g)
    env=get('level21');gui=get('sharedassets1.assets');fonts=get('sharedassets0.assets');home=get('level0');m0=second_row(home,names,fonts,stock,gui);(cache/'level0').write_bytes(m0)
    g=file(mgr);bs=next(o for o in g.objects.values() if o.type.name=='BuildSettings');b=val(bs);assert len(b['scenes'])==24 and b['scenes'][21].endswith('Barbarossa_Polesie_Summer.unity');b['scenes'] += [side.scene for side in SIDES];bs.set_raw_data(encode_complete(bs,b));(cache/'globalgamemanagers').write_bytes(g.save())
    home=Scene(get('level0'),names);title=next(go for go,v in home.go.items() if v['m_Name']=='Barbarossa 01 - Gates of Hell');txt,=kids(home.sf,title);hdr=bytearray(home.sf.objects[home.part[txt]['Text']].get_raw_data()[:144]);hdr[12]=1
    orig=Scene(get('level1'),names);f,pid=PTR.unpack_from(orig.sf.objects[orig.part[EMPTY_TEXT]['Text']].get_raw_data(),88);ext=orig.sf.externals[f-1].path;f=next(i for i,x in enumerate(home.sf.externals,1) if x.path==ext);PTR.pack_into(hdr,88,f,pid);ui=home,txt,bytes(hdr)+string('')
    hh=layout.heightgrid();props=layout.placements(hh);old=json.loads(mission.read_bytes());new=dict(title='暴风骤雨',environment=old['environment'],timeLimitSeconds=DEADLINE,sides={});clips=write_banks(out/'StormWeather.resource',recordings)
    for side in SIDES:
        prev='level'+str(side.index-2);print('First field:',prev,flush=True);(cache/prev).write_bytes(first(get(prev),old,models[PZ3,False],names,stock,side,fonts,gui));gc.collect()
        print('Storm field:',side.code,flush=True);rows,metrics=deployment(hh,props,side);cfg,rawscene=make(get('level8'),env,models,rows,names,ui,old['objective_position'],gui,fonts,hh,props,side,second=True);sf=file(rawscene);del rawscene;l=Linker(sf,names);cfg['retry']=retry(l,side.index);cfg['sight_press']=sight_press(l);cfg['weather']=weather(l,stock,fonts,gui,side,clips,home.sf.objects[2382]);(cache/side.member).write_bytes(sf.save());new['sides'][side.code]=dict(player=side.vehicle,scene=side.scene,index=side.index,briefing=side.briefing,units=rows,spacing=metrics,**cfg);del sf,l;gc.collect()
    doc={'campaign':'巴巴罗萨行动','first':old,'second':new,'weatherBanks':clips,**({'weatherAudio':'field-recordings','weatherCredits':'assets/Hatch/licenses/Storm-Recordings.txt'} if recordings else {})};(out/'campaign.json').write_bytes(dumps(doc));print('Serializing cumulative game data',flush=True)
    ns=['globalgamemanagers','level0','level22','level23','level24','level25',e['file']];changes=[(n,(cache/n).read_bytes()) for n in ns];result=append_members(raw,changes,{'level24':'level22','level25':'level23',e['file']:'resources.assets'});final=Members(result);assert all(final.read(n)==data for n,data in changes);assert all(v==final.members[n] for n,v in p.members.items() if n not in ns)
    _,start,end,_,_=metadata(original); _,rstart,_,_,_=metadata(result);assert result[rstart:rstart+end-start]==original[start:end];delta=result[:rstart]+result[rstart+end-start:];(out/'Barbarossa-Storm.overlay').write_bytes(delta)
    spec={'base_sha256':digest(original),'result_sha256':digest(result),'overlay_sha256':digest(delta),'header_bytes':rstart,'retain_start':start,'retain_end':end,'overlay_file':'Barbarossa-Storm.overlay','stock_apk_unchanged':True};(out/'integration.json').write_bytes(dumps(spec));(out/'data.unity3d').write_bytes(result);print(spec,flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for k in ['staged','apk','mission','out']:ap.add_argument('--'+k,required=True,type=Path)
    ap.add_argument('--recordings', type=Path, help='Directory with the three credited Ogg downloads')
    build(**vars(ap.parse_args()))
