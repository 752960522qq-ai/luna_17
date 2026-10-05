"""Verify real selection/battle catalog bytes in the serialized Unity bundles.

Run after prepare-assets. This checks resources, not Android/Unity execution.
"""
import argparse
import gc
import hashlib
import json
import struct
import sys
from collections import Counter
from pathlib import Path
import UnityPy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tankbuilder.serialization import apply_reviewed_typetrees,assert_roundtrip,encode_complete

RENDERERS={'MeshRenderer','ParticleSystemRenderer','SpriteRenderer','SkinnedMeshRenderer'}

def remap(tree,ids):
    if isinstance(tree,dict):
        if set(tree)=={'m_FileID','m_PathID'} and tree['m_FileID']==0:
            return dict(m_FileID=0,m_PathID=ids.get(tree['m_PathID'],tree['m_PathID']))
        return {k:remap(v,ids) for k,v in tree.items()}
    if isinstance(tree,list):return [remap(v,ids) for v in tree]
    if isinstance(tree,tuple):return tuple(remap(v,ids) for v in tree)
    return tree

def pointers(tree):
    if isinstance(tree,dict):
        if set(tree)=={'m_FileID','m_PathID'}:yield tree
        else:
            for value in tree.values():yield from pointers(value)
    elif isinstance(tree,(list,tuple)):
        for value in tree:yield from pointers(value)

def verify_serialization(original,modified,asset_report,original_ids):
    ids={int(a):int(b) for a,b in asset_report['clone_ids'].items()}
    env=UnityPy.load(str(original));apply_reviewed_typetrees(env)
    sf=next(o.assets_file for o in env.objects if o.assets_file.name=='resources.assets')
    inherited=[]
    def visit(pid):
        go=sf.objects[pid];tree=go.read_typetree();parts=[sf.objects[c['component']['m_PathID']] for c in tree['m_Component']]
        inherited.extend([go]+parts)
        tr=next(p for p in parts if p.type.name=='Transform')
        for child in tr.read_typetree()['m_Children']:
            visit(sf.objects[child['m_PathID']].read_typetree()['m_GameObject']['m_PathID'])
    visit(3413)
    assert set(ids)=={o.path_id for o in inherited},'Incomplete prefab clone map'
    expected_renderers={};baseline=Counter();builtin_refs=set()
    def remember_builtins(obj,tree):
        for pointer in pointers(tree):
            fid=pointer['m_FileID'];pid=pointer['m_PathID']
            if fid and pid:
                name=obj.assets_file.externals[fid-1].path.rsplit('/',1)[-1]
                if name in {'unity default resources','unity_builtin_extra'}:
                    builtin_refs.add((obj.type.name,name,pid))
    for obj in inherited:
        if obj.type.name=='MonoBehaviour':continue
        tree=assert_roundtrip(obj);baseline[obj.type.name]+=1
        remember_builtins(obj,tree)
        if obj.type.name in RENDERERS:
            tree=remap(tree,ids)
            if obj.type.name=='MeshRenderer':tree['m_Enabled']=False
            expected_renderers[ids[obj.path_id]]=encode_complete(obj,tree)
    for kind in ('Mesh','MeshFilter','MeshRenderer','SkinnedMeshRenderer','Texture2D','Material','GameObject','Transform'):
        template=next((o for o in sf.objects.values() if o.type.name==kind),None) or next(o for o in env.objects if o.type.name==kind)
        remember_builtins(template,assert_roundtrip(template))
    del sf,inherited,env;gc.collect()
    env=UnityPy.load(str(modified));schema=apply_reviewed_typetrees(env)
    files={o.assets_file.name:o.assets_file for o in env.objects}
    sf=files['resources.assets'];created=set(sf.objects)-set(original_ids)
    assert set(ids.values()).issubset(created)
    for pid,raw in expected_renderers.items():
        assert sf.objects[pid].get_raw_data()==raw,('Inherited renderer changed/truncated',pid)
    counts=Counter();checked_ptrs=0;builtin_count=0;meshes=0;tracks=0
    for pid in sorted(created):
        obj=sf.objects[pid]
        if obj.type.name=='MonoBehaviour':continue
        tree=assert_roundtrip(obj);counts[obj.type.name]+=1
        for pointer in pointers(tree):
            target_id=pointer['m_PathID'];fid=pointer['m_FileID']
            if not target_id:continue
            if fid:
                assert 0<fid<=len(sf.externals),(pid,pointer)
                name=sf.externals[fid-1].path.rsplit('/',1)[-1]
                if name not in files:
                    assert (obj.type.name,name,target_id) in builtin_refs,('Unknown external reference',pid,pointer)
                    builtin_count+=1;continue
                target=files[name]
            else:target=sf
            assert target_id in target.objects,('Dangling native pointer',pid,pointer)
            checked_ptrs+=1
        if obj.type.name=='Mesh':
            meshes+=1
            vertex_count=tree['m_VertexData']['m_VertexCount'];index_size=4 if tree['m_IndexFormat'] else 2
            assert vertex_count>0 and len(tree['m_IndexBuffer'])%index_size==0
            for sub in tree['m_SubMeshes']:
                assert sub['firstByte']+sub['indexCount']*index_size<=len(tree['m_IndexBuffer'])
                assert sub['firstVertex']+sub['vertexCount']<=vertex_count
            lod=tree['m_MeshLodInfo'];assert lod['m_NumLevels']==1
            assert len(lod['m_SubMeshes'])==len(tree['m_SubMeshes'])
            for sub,level in zip(tree['m_SubMeshes'],lod['m_SubMeshes']):
                assert level['m_Levels']==[{'m_IndexStart':sub['firstByte']//index_size,
                    'm_IndexCount':sub['indexCount']}]
        if obj.type.name in {'MeshRenderer','SkinnedMeshRenderer'} and pid not in ids.values():
            assert tree['m_Enabled'] and tree['m_Materials']
            assert tree['m_StaticBatchInfo']=={'firstSubMesh':0,'subMeshCount':0}
            if obj.type.name=='SkinnedMeshRenderer':
                tracks+=1;mesh=assert_roundtrip(sf.objects[tree['m_Mesh']['m_PathID']])
                assert len(tree['m_Bones'])==len(mesh['m_BindPose'])==11
        if obj.type.name=='GameObject':
            for c in tree['m_Component']:
                component=sf.objects[c['component']['m_PathID']]
                if component.type.name!='MonoBehaviour':
                    assert component.read_typetree()['m_GameObject']['m_PathID']==pid
        if obj.type.name=='Transform':
            for child in tree['m_Children']:
                assert sf.objects[child['m_PathID']].read_typetree()['m_Father']['m_PathID']==pid
    assert len(expected_renderers)==174 and meshes==80 and tracks==2
    return {'passed':True,'schema':schema,'inherited_native_baselines':dict(baseline),
        'inherited_native_baseline_count':sum(baseline.values()),
        'inherited_renderers_preserved':len(expected_renderers),'truncated_renderers':0,
        'new_native_object_roundtrips':dict(counts),'new_native_object_count':sum(counts.values()),
        'resolved_native_pointer_count':checked_ptrs,'original_unity_builtin_references':builtin_count,
        'new_meshes':meshes,'skinned_tracks':tracks}

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
    serialization=verify_serialization(original,modified,asset_report,old_resources)
    return {'passed':True,'stock_scene_objects_unchanged':untouched,
        'selection_scene':'level7','selection_catalog_unchanged':True,
        'battle_catalogs':registered,'battle_catalog_count':len(registered),
        'ai_and_other_national_arrays_unchanged':True,
        'original_resource_objects_unchanged':True,
        'new_objects':asset_report['new_objects'],
        'serialization':serialization,
        'prepared_unity_data_sha256':hashlib.sha256(Path(modified).read_bytes()).hexdigest(),
        'android_device_test':'not performed'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--original',type=Path,required=True)
    p.add_argument('--modified',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();assets=json.loads((a.modified.parent/'asset_report.json').read_text())
    result=verify(a.original,a.modified,assets)
    a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
