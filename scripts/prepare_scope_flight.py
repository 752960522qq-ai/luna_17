"""Apply a small field-only repair to a cumulative battleflow package and verify its actual bytes."""
import argparse,io,json,zipfile
from pathlib import Path
from prepare_battleflow import replace
from tankbuilder.barbarossa.mission.release import Members,dumps,digest
from tankbuilder.barbarossa.mission.codec import Linker
from tankbuilder.barbarossa.mission import SIDES
from tankbuilder.barbarossa.mission.scope_flight import primary,optics,verify_optics,actor_roots,verify_actor_roots,IMPORTED
from tankbuilder.barbarossa.mission.battleflow import check_pool
from tankbuilder.extra_campaign import file
from tankbuilder.unity_assets import pp,read_mb

def main(apk,kit,assets,out):
    assets.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(apk) as z,zipfile.ZipFile(kit) as k:
        base=z.read('assets/bin/Data/data.unity3d');pack=Members(base);field8=file(pack.read('level8'))
        names={p:o.read_typetree(check_read=False)['m_ClassName'] for p,o in file(pack.read('globalgamemanagers.assets')).objects.items() if o.type.name=='MonoScript'}
        spec,doc,rep=[json.loads(k.read(n+'.json')) for n in ('integration','mission','verification')]
        assert digest(base)==spec['result_sha256'];changed={};summary={}
        declared={}
        for tank in IMPORTED:
            blob=z.read('assets/Hatch/mods/'+tank+'.hatch')
            with zipfile.ZipFile(io.BytesIO(blob)) as h:
                w=json.loads(h.read('weapon.json')); assert w['ballistics']=='physical';declared[tank]=w
            if tank in ('T26','Panzer_II_Ausf_F'):(out/(tank+'.hatch')).write_bytes(blob)
        for side in SIDES:
            s=doc['sides'][side.code];raw=pack.read(side.member);sf=file(raw);link=Linker(sf,names)
            hero=next(u for u in s['units'] if u['team']=='player')
            rows=[(u,u['tank']) for u in s['units']]+[(s['factory'],hero['tank'])]
            count=sum(primary(link,u,tank) for u,tank in rows)
            s['vehicle_roots']=actor_roots(link,s)
            if side.code=='GE':s['optics']=optics(link,field8,s['primary_button'])
            baked=sf.save(); del link,sf
            final=file(baked); old=file(raw)
            verify_actor_roots(final,old,s)
            for row,tank in rows:
                la,st=[row['controllers'][k] for k in ('Launcher','UnitStatus')]
                new=read_mb('Launcher',final.objects[la].get_raw_data())
                prev=read_mb('Launcher',old.objects[la].get_raw_data())
                assert new==dict(prev,weaponName='') and new['uStatus']==pp(st)
                assert old.objects[st].get_raw_data()==final.objects[st].get_raw_data()
                if tank in declared:
                    w=declared[tank];stdata=read_mb('UnitStatus',final.objects[st].get_raw_data())
                    assert w['muzzleVelocity']==new['initSpeed'] and w['name']==stdata['mainGunName']
                else:assert final.objects[la].get_raw_data()==old.objects[la].get_raw_data()
            if side.code=='GE':verify_optics(final,field8,s['optics'],s['primary_button'],names)
            else:assert final.objects[157147].get_raw_data()==field8.objects[157147].get_raw_data()
            counts=[check_pool(final,u['controllers']['Launcher'],names) for u in [hero,s['factory']]]
            changed[side.member]=baked
            summary[side.code]={'imported_main_guns':count,'untouched_stock_main_guns':len(rows)-count,'player_and_retry_shell_pool':counts,'separate_ai_roots':sum(len(ev['transforms']) for ev in s['vehicle_roots'].values())}
            assert count==14 and len(rows)==22
            for d in (rep,):
                def fix(o):
                    if isinstance(o,dict):
                        if o.get('retry_scene_index')==s['index']:o['scene_sha256']=digest(baked)
                        for x in o.values():fix(x)
                    elif isinstance(o,list):
                        for x in o:fix(x)
                fix(d)
            print(side.member,summary[side.code],flush=True)
            del old,final
        result=replace(base,spec,changed);read=Members(result)
        assert set(read.members)==set(pack.members)
        for n in read.members:assert read.read(n)==(changed[n] if n in changed else pack.read(n)),n
        delta=result[:spec['header_bytes']]+result[spec['retain_end']:]
        assert result[spec['retain_start']:spec['retain_end']]==base[spec['retain_start']:spec['retain_end']]
        spec.update(prior_result_sha256=digest(base),result_sha256=digest(result),overlay_sha256=digest(delta))
        rep['scope_flight']={'sides':summary,'normal_field_unchanged':True,'changed_members':list(changed),'checked_members':len(read.members),'android_device_test':False}
        for n,val in [(spec['overlay_file'],delta),('data.unity3d',result),('ai-index.json',k.read('AI/Hatch-Enemy-AI-index.json'))]: (assets/n).write_bytes(val)
        for n,val in [('integration',spec),('mission',doc),('verification',rep)]: (assets/(n+'.json')).write_bytes(dumps(val))
        print('all members and real shell pools verified',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('apk','kit','assets','out'):p.add_argument('--'+n,type=Path,required=True)
    main(**vars(p.parse_args()))
