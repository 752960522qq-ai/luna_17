"""Validate the released native fields and sound banks after reopening the cumulative game resource."""
import argparse,gc,io,json,struct,wave
from collections import Counter
from pathlib import Path
from itertools import combinations
from math import dist
from UnityPy.export.AudioClipConverter import dump_samples
from ...campaign_ugui import PTR,button_event,text_value,write_calls
from ...extra_campaign import file,Scene,PAGE_NAME
from ...serialization import parse_complete as val
from ...unity_assets import read_mb,pp
from ...enemy_assets import subtree
from ..mission.codec import kids,part,cname
from ..mission.release import Members,digest,dumps
from ..mission.font import covers
from ..mission.lettering import check
from ..mission.battleflow import check_pool
from ..mission.scope_flight import world_root_call
from ..mission.verify import camera_target
from ..mission.objectives import decode
from ..mission.interface import event,events
from ..mission.lanes import Lanes
from .. import layout
from . import SIDES,PZ3,PZ4,PZ2,DEADLINE
from .deployment import measure
from .events import BEHAVIOUR,active
from .sound import sounds

def one(it):
    item,=it
    return item

def mark(sf,button,name):
    call=one(button_event(sf.objects[button].get_raw_data())[2]);f,g=call[0]
    assert not f and call[2]=='SetActive' and call[9:]==(1,2)
    assert val(sf.objects[g])['m_Name']==name and not val(sf.objects[g])['m_IsActive']
    return g

def collider(sf):
    return {k:digest(one(o.get_raw_data() for o in sf.objects.values() if o.type.name==k)) for k in ('Terrain','TerrainData','TerrainCollider')}

def validate(out,staged,legacy,recordings=None):
    prior=Members((staged/'assets/bin/Data/data.unity3d').read_bytes()); pack=Members((out/'data.unity3d').read_bytes())
    get=lambda n:file(pack.read(n));names={o.path_id:o.read_typetree(check_read=False)['m_ClassName'] for o in get('globalgamemanagers.assets').objects.values() if o.type.name=='MonoScript'}
    source=json.loads(legacy.read_bytes());doc=json.loads((out/'campaign.json').read_bytes());base=file(prior.read('globalgamemanagers'));m=get('globalgamemanagers')
    typ=lambda sf,k:val(one(o for o in sf.objects.values() if o.type.name==k))
    sc=typ(m,'BuildSettings')['scenes'];assert sc[:-2]==typ(base,'BuildSettings')['scenes'] and sc[-2:]==[s.scene for s in SIDES]
    assert (doc.get('weatherAudio') == 'field-recordings') == (recordings is not None)
    stock=get('level8');oldreg=dict(typ(base,'ResourceManager')['m_Container']);reg=dict(typ(m,'ResourceManager')['m_Container'])
    assert all(reg[k]==v for k,v in oldreg.items()) and set(reg)-set(oldreg)=={'unit/so/bt7/bt7_player','unit/so/bt7/bt7_player_profile'}
    r=reg['unit/so/bt7/bt7_player'];assert m.externals[r['m_FileID']-1].path=='BT7_Player.assets'
    camera_target(get('BT7_Player.assets'),r['m_PathID'],names)
    title=Scene(get('level0'),names);page=one(g for g,x in title.go.items() if x['m_Name']==PAGE_NAME)
    _,_,grp,back=title.children(page);rows=title.children(grp);assert len(rows)==6
    ranges=[]
    for j,go in enumerate(rows):
        txt=one(title.sf.objects[title.part[t]['Text']] for t in title.children(go) if 'Text' in title.part[t]);label=text_value(txt.get_raw_data())
        if j in (0,3):assert label==('炼狱之门' if j==0 else '暴风骤雨') and 'Button' not in title.part[go]
        else:
            side='GE' if j%3==1 else 'SO';key='Hatch Start ' if j<3 else 'Hatch Storm Start '
            marker=mark(title.sf,title.part[go]['Button'],key+side);assert marker in title.children(go)
            game=doc['first' if j<3 else 'second']['sides'][side];assert sc[game['index']]==game['scene'] and ((side=='GE')==(game['index']%2==1))
            labelkey={'GE':('二号 F 型','三号 F 型'),'SO':('T26','BT-7')};assert label.endswith(labelkey[side][j>=3])
            rect=title.transform(go);x,y=rect['m_AnchoredPosition'].values();w,h=rect['m_SizeDelta'].values();ranges.append((x-w/2,x+w/2,y-h/2,y+h/2))
        fi,font=PTR.unpack_from(txt.get_raw_data(),88);assert fi==0 and covers(val(title.sf.objects[font])['m_FontData'],label)
        check(title.sf,names,txt)
    assert all(a[1]<b[0] or b[1]<a[0] or a[3]<b[2] or b[3]<a[2] for a,b in combinations(ranges,2))
    h=layout.heightgrid();nav=Lanes(h,layout.placements(h));report={'missions':{},'pickerCaptions':6,'buttons':4,'gameplayLimitSeconds':DEADLINE,'androidDevicePlaytest':False}
    stream=(out/'StormWeather.resource').read_bytes();samples=sounds(recordings);terrain=collider(file(prior.read('level22')))
    exp={'SO':{'GE':{PZ3:4,PZ4:2,PZ2:6},'SO':{'T28':1,'BT7':4,'T26':5}},'GE':{'GE':{PZ3:3,PZ4:2,PZ2:5},'SO':{'T28':1,'BT7':6,'T26':6}}}
    for side in SIDES:
        sect=side.code;old=source['sides'][sect];first=doc['first']['sides'][sect];a=get('level'+str(side.index-2));ao=file(prior.read('level'+str(side.index-2)))
        assert len(first['units'])==len(old['units'])==21 and collider(a)==terrain
        for nxt in first['next_button']:mark(a,nxt,'Hatch Storm Continue')
        for btn in (157017,164841): assert mark(a,btn,'Hatch Campaign Retry')==first['retry']
        swapped=[]
        for prev,cur in zip(old['units'],first['units']):
            if prev['tank']!='Panzer_III_J':assert prev==cur;continue
            assert cur['tank']==PZ3 and cur['source']==PZ3+'_AI.assets'
            assert all(prev[k]==cur[k] for k in ('pos','route','lane','transform','root','phase','nation','team','yaw'))
            assert cur['phase']=='wave2' and not val(a.objects[cur['root']])['m_IsActive'] and cur['root'] in first['schedule']['events']['wave2']['targets']
            assert val(a.objects[cur['transform']])['m_LocalPosition']==val(ao.objects[prev['transform']])['m_LocalPosition']
            assert read_mb('UnitStatus',a.objects[cur['controllers']['UnitStatus']].get_raw_data())['unitName']==PZ3
            assert world_root_call(cur['transform']) in a.objects[first['vehicle_roots']['wave2']['timer']].get_raw_data()
            assert check_pool(a,cur['controllers']['Launcher'],names)>0;swapped.append(cur['id'])
        assert len(swapped)==3
        for ev in old['schedule']['events']:
            expected=old['schedule']['events'][ev];assert expected==first['schedule']['events'][ev]
            i=expected['timer'];assert a.objects[i].get_raw_data()[:40]==ao.objects[i].get_raw_data()[:40]
        del a,ao;gc.collect()
        sf=get(side.member);cfg=doc['second']['sides'][sect];rows=cfg['units'];groups=cfg['groups'];assert collider(sf)==terrain
        assert not val(sf.objects[5328])['m_IsActive'] and kids(sf,5328)[side.nation*5]==side.scenario
        assert all(not kids(sf,k) for k in kids(sf,5328) if k!=side.scenario)
        assert {r['tank'] for r in rows if r['team']=='player'}=={side.vehicle}
        assert {n:dict(Counter(r['tank'] for r in rows if r['nation']==n)) for n in ('SO','GE')}==exp[sect]
        assert all({(r['lane'],r['echelon']) for r in rows if r['nation']==n}=={(l,k) for l in ('west','east') for k in (1,2)} for n in ('SO','GE'))
        for btn in (157017,164841): assert mark(sf,btn,'Hatch Campaign Retry')==cfg['retry']
        assert sf.objects[155469].get_raw_data()==stock.objects[155469].get_raw_data() and sf.objects[155487].get_raw_data()==stock.objects[155487].get_raw_data()
        assert not val(sf.objects[cfg['ui']['opening']])['m_IsActive']
        assert button_event(sf.objects[157147].get_raw_data())[2][0][0]==(0,cfg['sight_press'])
        assert button_event(sf.objects[157147].get_raw_data())[2][1:]==button_event(stock.objects[157147].get_raw_data())[2]
        assert not val(sf.objects[cfg['base']])['m_IsActive'] or not val(sf.objects[part(sf,cfg['base'],'SphereCollider')])['m_Enabled']
        rules=decode(sf.objects[side.objective_control].get_raw_data());assert rules[1]==(1,0,0) and rules[3]==(0,0)
        assert len(set(r['root'] for r in rows))==len(rows) and sum(r['team']=='player' for r in rows)==1
        tech=0;nseg=0;actual=[]
        for team,g in groups.items():assert set(kids(sf,g))=={r['root'] for r in rows if r['team']==team}
        for row in rows:
            n=row['nation'];team=row['team'];tank=row['tank'];u=row['controllers'];rt=val(sf.objects[row['transform']]);go=val(sf.objects[row['root']])
            assert go['m_IsActive'] and go['m_Name'].startswith(tank+'_') and ((team=='enemy')==(n!=sect)) and rt['m_Father']==pp(part(sf,groups[team],'Transform'))
            pos=[rt['m_LocalPosition'][k] for k in 'xyz'];assert dist(pos,row['pos'])<.001 and abs(float(layout.ground(h,pos[0],pos[2]))+.35-pos[1])<.001
            p=pos[::2];assert nav.clear(p,p);actual.append(dict(row,pos=pos))
            us=read_mb('UnitStatus',sf.objects[u['UnitStatus']].get_raw_data());gun=read_mb('Launcher',sf.objects[u['Launcher']].get_raw_data())
            assert us['unitName']==tank and us['iFFNum']=={'player':0,'friend':1,'enemy':2}[team] and gun['weaponName']=='' and us['mainGunName']
            assert gun['uStatus']==pp(u['UnitStatus']) and gun['initSpeed']>0;tech+=check_pool(sf,u['Launcher'],names)
            if team=='player':camera_target(sf,row['root'],names);assert not row['route'] and 'AIControl' not in u and row['echelon']==1
            else:
                b=sf.objects[u['AIControl']].get_raw_data();num=struct.unpack_from('<i',b,200)[0];assert num==len(row['route'])>0 and bool(b[12])==(row['echelon']==1)
                for i,q in enumerate(row['route']):
                    actual_q=struct.unpack_from('<3f',b,204+12*i);assert dist(actual_q,q)<.001 and nav.clear(p,actual_q[::2]);p=actual_q[::2];nseg+=1
        assert measure(actual)==cfg['spacing'];assert 575<=cfg['spacing']['nearestEnemyM']<=625 and cfg['spacing']['minimumFriendlyM']>=36
        factory=cfg['factory'];camera_target(sf,factory['root'],names);assert not val(sf.objects[factory['garage']])['m_IsActive'] and val(sf.objects[factory['root']])['m_IsActive']
        b=sf.objects[155556].get_raw_data();orig=stock.objects[155556].get_raw_data();p=44
        for ti in range(3):
            n=struct.unpack_from('<i',b,p)[0];p+=4
            for i in range(n):
                a0=PTR.unpack_from(orig,p);an=PTR.unpack_from(b,p);selected=ti==side.nation or (sect=='GE' and ti==2)
                assert an==((0,factory['root']) if selected and a0[1] else a0);p+=12
        def timed(pid,seconds,actions):
            o=sf.objects[pid];b=o.get_raw_data();assert cname(o,names)=='TimedEvent' and PTR.unpack_from(b)==(0,side.scenario)
            assert abs(struct.unpack_from('<f',b,32)[0]-seconds)<.0001 and struct.unpack_from('<i',b,36)[0]==1 and b[40:]==events(actions)
        sched=cfg['schedule']
        for n,t in [('GE',312),('SO',432)]:
            r=sched['reserves'][n];ids=[r['controllers']['AIControl'] for r in rows if r['nation']==n and r['echelon']==2]
            assert set(ids)==set(r['ai']) and r['seconds']==t and not val(sf.objects[r['marker']])['m_IsActive']
            timed(r['timer'],t,[event(c,BEHAVIOUR,'set_enabled',6,flag=True) for c in ids]+[active(r['marker'],True)])
        trs=[r['transform'] for r in rows if r['team']!='player'];assert sched['transforms']==trs;timed(sched['release'],.25,[world_root_call(t) for t in trs])
        w=cfg['weather'];parts=val(sf.objects[w['particles']]);render=val(sf.objects[w['renderer']]);rs=typ(sf,'RenderSettings')
        assert parts['m_GameObject']==pp(w['rain']) and parts['looping'] and parts['prewarm'] and parts['moveWithTransform']==1 and not parts['useUnscaledTime']
        assert 0<parts['EmissionModule']['rateOverTime']['scalar']<=1000 and parts['InitialModule']['maxNumParticles']<=1000 and parts['VelocityModule']['y']['scalar']<0
        assert rs['m_Fog'] and rs['m_SkyboxMaterial']==w['sky'] and rs['m_FogDensity']<.002 and render['m_RenderMode']==1 and len(render['m_Materials'])==1
        assert len(w['strikes'])>=8 and not val(sf.objects[w['flash']])['m_IsActive'];assert sorted({s['sample'] for s in w['strikes']})==['crack','roll']
        for bolt in w['bolts']:
            assert not val(sf.objects[bolt['root']])['m_IsActive']
            assert {sf.objects[q['component']['m_PathID']].type.name for q in val(sf.objects[bolt['root']])['m_Component']}=={'Transform','MeshFilter','MeshRenderer'}
            assert val(sf.objects[bolt['mesh']])['m_VertexData']['m_VertexCount']>100
        assert {r['bolt'] for r in w['strikes']}=={r['root'] for r in w['bolts']}
        for j,row in enumerate(w['strikes']):
            sec,d,delay,sa=row['second'],row['flashSeconds'],row['thunderDelay'],row['sample']
            assert .19<d<.5 and 1<=delay<=4 and sec+delay<780 and (not j or 41<=sec-w['strikes'][j-1]['second']<=76)
            t1,t2,t3=row['timers'];timed(t1,sec,[active(w['flash'],True),active(row['bolt'],True)]);timed(t2,sec+d,[active(w['flash'],False),active(row['bolt'],False)])
            timed(t3,sec+delay,[event(w['ambient'][sa],'UnityEngine.AudioSource, UnityEngine.AudioModule','Play')])
        for key,pid in w['clips'].items():
            clip=sf.objects[pid];c=val(clip);v=c['m_Resource'];blob=stream[v['m_Offset']:v['m_Offset']+v['m_Size']]
            assert v['m_Source']=='StormWeather.resource' and c['m_Frequency']==24000 and blob[:4]==b'FSB5'
            src=val(sf.objects[w['ambient'][key]]);assert src['m_audioClip']==pp(pid) and src['Loop']==(key=='rain') and src['m_PlayOnAwake']==(key=='rain') and 0<src['m_Volume']<1
            rendered=one(dump_samples(clip.read(),blob).values())
            with wave.open(io.BytesIO(rendered)) as f:assert f.getframerate()==24000 and f.getsampwidth()==2 and f.readframes(f.getnframes())==samples[key].tobytes()
        report['missions'][sect]={'firstReplacements':swapped,'counts':exp[sect],'player':side.vehicle,'spacing':cfg['spacing'],'traversableRouteSegments':nseg,'projectilePoolInstances':tech,'audibleBanksDecoded':3,'stormStrikes':len(w['strikes']),'reserveTimesSeconds':[312,432]}
        del sf;gc.collect()
    report['terrainSHA256']=terrain;report['matchesResourceSHA256']=digest(pack.raw);report['status']='passed';(out/'verification.json').write_bytes(dumps(report));return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('out','staged','legacy'):p.add_argument('--'+k,required=True,type=Path)
    p.add_argument('--recordings',type=Path)
    print(json.dumps(validate(**vars(p.parse_args())),ensure_ascii=False,indent=2))
