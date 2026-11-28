"""Update the latest cumulative signed APK and overlay (no game executable changes)."""
import argparse,io,json,struct,zipfile
from pathlib import Path
import lz4.block
from tankbuilder.barbarossa.mission.release import Members,dumps,digest
from tankbuilder.barbarossa.mission import SIDES,battleflow
from tankbuilder.barbarossa.mission.codec import Linker,cname,part
from tankbuilder.barbarossa.mission.compact import encode
from tankbuilder.barbarossa.mission.objectives import decode
from tankbuilder.barbarossa.bundle import metadata
from tankbuilder.extra_campaign import file
from tankbuilder.serialization import parse_complete as v
from tankbuilder.autocannon_config import update

def replace(prior, spec, changed):
    hdr,start,_,old,entries=metadata(prior);end=spec['retain_end']
    oldblocks={};phys=start;addr=0;blocks=[];parts=[];entries2={};q=0
    for n,c,m in old:
        oldblocks[addr]=(phys,n,c,m)
        if phys<end:
            assert phys+c<=end;blocks.append((n,c,m));q+=n
        addr+=n;phys+=c
    base=q
    for name,(a,n,fl) in sorted(entries.items(),key=lambda o:o[1][0]):
        if a+n<=base:
            assert name not in changed;entries2[name]=(a,n,fl);continue
        pad=-q%16
        if pad:blocks.append((pad,pad,0));parts.append(bytes(pad));q+=pad
        if name in changed:
            data=changed[name];entries2[name]=(q,len(data),fl)
            for pos in range(0,len(data),4<<20):
                b=data[pos:pos+(4<<20)];packed=encode(b);mode=1
                if len(packed)>=len(b):packed=b;mode=0
                blocks.append((len(b),len(packed),mode));parts.append(packed);q+=len(b)
        else:
            entries2[name]=(q,n,fl);nleft=n
            while nleft:
                p,raw,count,mode=oldblocks[a];assert raw<=nleft
                blocks.append((raw,count,mode));parts.append(memoryview(prior)[p:p+count]);a+=raw;nleft-=raw;q+=raw
    d=io.BytesIO();d.write(bytes(16)+struct.pack('>I',len(blocks)))
    for b in blocks:d.write(struct.pack('>IIH',*b))
    d.write(struct.pack('>I',len(entries)))
    for name in entries:d.write(struct.pack('>qqI',*entries2[name])+name.encode()+bytes(1))
    bare=d.getvalue();directory=lz4.block.compress(bare,store_size=False);head=bytearray(prior[:start])
    struct.pack_into('>QIII',head,hdr,end+sum(map(len,parts))+len(directory),len(directory),len(bare),0xc2)
    return b''.join([head,memoryview(prior)[start:end],*parts,directory])

def main(apk,kit,assets,out):
    assets.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(apk) as z,zipfile.ZipFile(kit) as k:
        prior=z.read("assets/bin/Data/data.unity3d");bundle=Members(prior)
        (assets/'old_pz.hatch').write_bytes(z.read('assets/Hatch/mods/Panzer_II_Ausf_F.hatch'))
        update(assets/'old_pz.hatch',out/'Panzer_II_Ausf_F.hatch')
        (out/'T26.hatch').write_bytes(z.read('assets/Hatch/mods/T26.hatch'))
        names={p:o.read_typetree(check_read=False)['m_ClassName'] for p,o in file(bundle.read('globalgamemanagers.assets')).objects.items() if o.type.name=='MonoScript'}
        doc=json.loads(k.read('mission.json'));spec=json.loads(k.read('integration.json'));rep=json.loads(k.read('verification.json'))
        assert spec['result_sha256']==digest(prior);changed={};counts={}
        (assets/'ai-index.json').write_bytes(k.read('AI/Hatch-Enemy-AI-index.json'))
        for side in SIDES:
            name=side.member;field=file(bundle.read(name));s=doc['sides'][side.code];link=Linker(field,names)
            battleflow.rule_gate(field,side,s,link)
            pcs=[next(x for x in s['units'] if x['team']=='player')['controllers'],s['factory']['controllers']]
            if side.code=='GE':
                for p in pcs:battleflow.pool(link,p['Launcher'])
                s['primary_button']=battleflow.bind_trigger(link)
            changed[name]=field.save()
            # Test baked player AND the replacement instantiated by the original field factory.
            scene=file(changed[name]);
            if side.code=='GE':battleflow.check_trigger(scene,s['primary_button'])
            counts[side.code]=[battleflow.check_pool(scene,p['Launcher'],names) for p in pcs]
            assert side.code!='GE' or counts[side.code]==[12,12]
            assert v(scene.objects[part(scene,s['base'],'SphereCollider')])['m_Enabled']
            pid=s['opening_objective_control'];assert scene.objects[pid].get_raw_data()[12]
            assert not scene.objects[s['objective_control']].get_raw_data()[12]
            _,wins,_,loss,_=decode(scene.objects[pid].get_raw_data());assert wins[0]==loss[0]==0 and (wins[1] if side.code=='GE' else loss[1])
            for key in ('wave2','relief'):
                ev=s['schedule']['events'][key];raw=scene.objects[ev['timer']].get_raw_data()
                assert struct.unpack_from('<i',raw,40)[0]==len(ev['targets'])+(2 if key=='wave2' else 0)
            for u in s['units']:
                la=u['controllers']['Launcher'];g=battleflow.read_mb('Launcher',scene.objects[la].get_raw_data())
                assert part(scene,battleflow.PTR.unpack_from(scene.objects[la].get_raw_data())[1],'Transform')==g['thisTrf']['m_PathID']
            print('checked',name,counts[side.code],flush=True)
        # Packaged Resources prefab may be used by alternate entry or retry.
        name='Panzer_II_Ausf_F_Player.assets';pref=file(bundle.read(name));link=Linker(pref,names)
        launch,=[p for p,o in pref.objects.items() if o.type.name=='MonoBehaviour' and cname(o,names)=='Launcher']
        battleflow.pool(link,launch);changed[name]=pref.save();assert battleflow.check_pool(file(changed[name]),launch,names)==12
        print('encoding three changed members',flush=True)
        result=replace(prior,spec,changed);read=Members(result);assert set(read.members)==set(bundle.members)
        for path in read.members:assert read.read(path)==(changed[path] if path in changed else bundle.read(path)),path
        (assets/'data.unity3d').write_bytes(result);delta=result[:spec['header_bytes']]+result[spec['retain_end']:]
        assert result[spec['retain_start']:spec['retain_end']]==prior[spec['retain_start']:spec['retain_end']]
        spec.update(prior_result_sha256=digest(prior),result_sha256=digest(result),overlay_sha256=digest(delta))
        (assets/spec['overlay_file']).write_bytes(delta)
        doc['result_flow']='stock GameControl/GameUiManager; capture from start, reserve elimination after wave2'
        rep['battleflow']={'muzzle_and_spawn_pool':counts,'verified_members':len(read.members),'changed_members':list(changed),'target_device_test':False}
        # Refresh previously published scene hashes without retaining stale values.
        for key,val in doc['sides'].items():
            def fix(o):
                if isinstance(o,dict):
                    if o.get('retry_scene_index')==val['index']:o['scene_sha256']=digest(changed['level'+str(val['index'])])
                    for x in o.values():fix(x)
                elif isinstance(o,list):
                    for x in o:fix(x)
            fix(rep)
        for n,x in [('integration',spec),('mission',doc),('verification',rep)]:(assets/(n+'.json')).write_bytes(dumps(x))
        print('all UnityFS members verified',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('apk','kit','assets','out'):p.add_argument('--'+k,type=Path,required=True)
    main(**vars(p.parse_args()))
