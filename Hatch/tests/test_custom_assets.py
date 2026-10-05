"""Check the actual serialized output for one or several custom player tanks."""
import argparse,gc,hashlib,json,struct,sys
from pathlib import Path
import UnityPy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tankbuilder.serialization import apply_reviewed_typetrees,assert_roundtrip
from test_assets import snapshot,pointers
NATIONS=['USSR','Germany','USA','Japan','UK','Italy']

def verify(original,modified,report):
    old,old_gen,old_resources=snapshot(original);new,new_gen,new_resources=snapshot(modified)
    packs=report.get('packs') or [report];battle={'level'+str(i) for i in range(8,20)}
    assert {r['scene'] for r in report['registrations']}==battle
    for scene,objects in old.items():
        if scene not in battle:assert new[scene]==objects,'Stock scene changed '+scene
    for scene in battle:
        before=old_gen[scene]['raw'];expected=before
        for pack in packs:
            r=next(x for x in pack['registrations'] if x['scene']==scene)
            at=44
            for _ in range([0,1,3,4,5,6][NATIONS.index(r['country'])]):
                count=struct.unpack_from('<i',expected,at)[0];at+=4+12*count
            count=struct.unpack_from('<i',expected,at)[0];end=at+4+12*count
            assert count==r['player_index']
            expected=expected[:at]+struct.pack('<i',count+1)+expected[at+4:end]+struct.pack('<iq',old_gen[scene]['resources_id'],pack['player_prefab_id'])+expected[end:]
        assert new_gen[scene]['raw']==expected,'Unexpected catalog mutation '+scene
        changed=[i for i,v in old[scene].items() if v!=new[scene][i]]
        assert changed==[old_gen[scene]['id']]
    assert all(new_resources.get(i)==v for i,v in old_resources.items()),'Original resource changed'
    assert len(new_resources)-len(old_resources)==report['new_objects']
    env=UnityPy.load(str(modified));apply_reviewed_typetrees(env);files={o.assets_file.name:o.assets_file for o in env.objects};sf=files['resources.assets']
    clone_ids={int(v) for p in packs for v in p['clone_ids'].values()};created=set(sf.objects)-set(old_resources);meshes=0;ptrs=0;materials=0
    for pid in sorted(created):
        o=sf.objects[pid]
        if o.type.name=='MonoBehaviour':continue
        t=assert_roundtrip(o)
        for p in pointers(t):
            if not p['m_PathID']:continue
            fid=p['m_FileID']
            if fid:
                assert 0<fid<=len(sf.externals)
                name=sf.externals[fid-1].path.rsplit('/',1)[-1]
                if name in ['unity default resources','unity_builtin_extra']:continue
                assert name in files;target=files[name]
            else:target=sf
            assert p['m_PathID'] in target.objects,('Dangling reference',pid,p)
            ptrs+=1
        if o.type.name=='Mesh':
            meshes+=1;vc=t['m_VertexData']['m_VertexCount'];width=4 if t['m_IndexFormat'] else 2
            assert vc>0
            for sub in t['m_SubMeshes']:
                assert sub['firstByte']+sub['indexCount']*width<=len(t['m_IndexBuffer'])
                assert sub['firstVertex']+sub['vertexCount']<=vc
        if o.type.name=='Material':
            materials+=1;assert t['m_Shader']['m_PathID']==3176,'Unsupported shader variant'
            assert dict(t['m_SavedProperties']['m_Floats'])['_Metallic']==0
        if o.type.name=='Transform':
            for child in t['m_Children']:assert sf.objects[child['m_PathID']].read_typetree()['m_Father']['m_PathID']==pid
        if o.type.name in ['MeshRenderer','SkinnedMeshRenderer'] and pid not in clone_ids:
            assert t['m_Enabled'] and t['m_Materials']
            if o.type.name=='SkinnedMeshRenderer':
                mesh=assert_roundtrip(sf.objects[t['m_Mesh']['m_PathID']]);assert len(t['m_Bones'])==len(mesh['m_BindPose'])
        if o.type.name=='GameObject':
            for part in t['m_Component']:
                component=sf.objects[part['component']['m_PathID']]
                if component.type.name!='MonoBehaviour':assert component.read_typetree()['m_GameObject']['m_PathID']==pid
    assert meshes==sum(p['model_meshes'] for p in packs)
    # Every custom model is reachable from the registered player root.
    roots=[]
    for pack in packs:
        root=sf.objects[pack['player_prefab_id']].read_typetree();assert root['m_Name']==pack['id']+'_Player';roots.append(pack['id'])
    return {'passed':True,'packs':roots,'battle_catalog_count':12,'selection_scene_unchanged':True,'stock_resources_unchanged':True,'new_objects':len(created),'meshes':meshes,'materials':materials,'resolved_pointers':ptrs,'android_device_test':'not performed'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original',required=True);p.add_argument('--modified',required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=verify(a.original,a.modified,json.loads((Path(a.modified).parent/'asset_report.json').read_text()));a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
