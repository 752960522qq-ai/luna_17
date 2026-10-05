"""Verify real selection/battle catalog bytes in the serialized Unity bundles.

Run after prepare-assets. This checks resources, not Android/Unity execution.
"""
import argparse
import gc
import hashlib
import json
import struct
from pathlib import Path
import UnityPy

def snapshot(path):
    env=UnityPy.load(str(path))
    files={o.assets_file.name:o.assets_file for o in env.objects}
    scenes={}
    for name,af in files.items():
        if name.startswith('level'):
            scenes[name]={i:(o.type.name,hashlib.sha256(o.get_raw_data()).hexdigest())
                          for i,o in af.objects.items()}
    scripts={(name,o.path_id):o.read_typetree(check_read=False)['m_ClassName']
             for name,af in files.items() for o in af.objects.values()
             if o.type.name=='MonoScript'}
    catalogs={}
    for name,af in files.items():
        if not name.startswith('level'):continue
        for o in af.objects.values():
            if o.type.name!='MonoBehaviour':continue
            t=o.read_typetree(check_read=False);sp=t['m_Script']
            file=name if not sp['m_FileID'] else af.externals[sp['m_FileID']-1].path.rsplit('/',1)[-1]
            if scripts.get((file,sp['m_PathID']))=='TankGenManager':
                catalogs[name]={'id':o.path_id,'raw':o.get_raw_data(),
                    'resources_id':next(i+1 for i,e in enumerate(af.externals)
                        if e.path.rsplit('/',1)[-1]=='resources.assets')}
    resources={i:(o.type.name,hashlib.sha256(o.get_raw_data()).hexdigest())
               for i,o in files['resources.assets'].objects.items()}
    del env,files;gc.collect()
    return scenes,catalogs,resources

def verify(original,modified,asset_report):
    old,old_gen,old_resources=snapshot(original)
    new,new_gen,new_resources=snapshot(modified)
    expected={'level'+str(i) for i in range(8,20)}
    assert {r['scene'] for r in asset_report['registrations']}==expected
    # All stock menu/selection scene objects must be byte-for-byte unchanged.
    untouched=[]
    for scene,objects in old.items():
        if scene not in expected:
            assert new[scene]==objects,scene+' changed outside battle catalogs'
            untouched.append(scene)
    registered=[]
    root=asset_report['player_prefab_id']
    for scene in sorted(expected,key=lambda x:int(x[5:])):
        a=old_gen[scene];b=new_gen[scene]
        assert a['id']==b['id']
        before,after=a['raw'],b['raw']
        n=struct.unpack_from('<i',before,44)[0]
        assert struct.unpack_from('<i',after,44)[0]==n+1
        split=48+n*12
        assert after[:44]==before[:44] and after[48:split]==before[48:split]
        assert struct.unpack_from('<iq',after,split)==(b['resources_id'],root)
        # Includes every other national player array and all AI arrays.
        assert after[split+12:]==before[split:]
        assert set(old[scene])==set(new[scene])
        changed=[i for i,v in old[scene].items() if v!=new[scene][i]]
        assert changed==[a['id']],(scene,changed)
        registered.append(scene)
    assert all(new_resources.get(i)==v for i,v in old_resources.items())
    assert len(new_resources)-len(old_resources)==asset_report['new_objects']
    return {'passed':True,'stock_scene_objects_unchanged':untouched,
        'selection_scene':'level7','selection_catalog_unchanged':True,
        'battle_catalogs':registered,'battle_catalog_count':len(registered),
        'ai_and_other_national_arrays_unchanged':True,
        'original_resource_objects_unchanged':True,
        'new_objects':asset_report['new_objects'],
        'prepared_unity_data_sha256':hashlib.sha256(Path(modified).read_bytes()).hexdigest(),
        'android_device_test':'not performed'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True)
    p.add_argument('--modified',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();assets=json.loads((a.modified.parent/'asset_report.json').read_text())
    result=verify(a.original,a.modified,assets)
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
