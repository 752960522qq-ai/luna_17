"""Reviewed r10 player controls and geometry repairs; no APK packaging."""
import copy
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from pygltflib import Node
from .modelrig import Model
from .serialization import assert_roundtrip as serialized_roundtrip, encode_complete
from .unity_assets import Adapter, pp, xyz, aabb, read_mb, write_mb, remap

R9_SHA = 'f950c94a5445ff84c501875181e674e214ae595f747fe7ff3dd6289bd11b0646'

def assert_roundtrip(obj, raw=None):
    # UnityPy ObjectReader.get_raw_data reads the original serialized bytes;
    # set_raw_data stores edits in .data. Subsequent appends must see edits,
    # otherwise the second child silently replaces the first one.
    if raw is None: raw = obj.data or obj.get_raw_data()
    return serialized_roundtrip(obj, raw)

def store(obj, tree):
    assert_roundtrip(obj)
    raw = encode_complete(obj, tree)
    assert_roundtrip(obj, raw)
    obj.set_raw_data(raw)

def pointers(value):
    if isinstance(value,dict):
        if set(value)=={'m_FileID','m_PathID'}: yield value
        else:
            for child in value.values(): yield from pointers(child)
    elif isinstance(value,(list,tuple)):
        for child in value: yield from pointers(child)

def attachment_triangles(vertices, indices):
    """Classify complete disconnected parts, refusing any ambiguous bridge.

    Reviewed details_73 has a clear gap: hull parts end below 1.18 m,
    turret parts start above 1.56 m. Never cut a triangle across the ring.
    """
    indices = np.asarray(indices).reshape(-1, 3)
    parent = np.arange(len(vertices))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b, c in indices:
        root = find(a); parent[find(b)] = root; parent[find(c)] = root
    groups = {}
    for i, triangle in enumerate(indices): groups.setdefault(find(triangle[0]), []).append(i)
    turret = np.zeros(len(indices), dtype=bool)
    for triangles in groups.values():
        ys = vertices[np.unique(indices[triangles]), 1]
        if ys.min() > 1.5: turret[triangles] = True
        elif ys.max() >= 1.5: raise ValueError('Ambiguous detail component crosses turret/hull boundary')
    if not turret.any() or turret.all(): raise ValueError('Expected mixed turret and hull detail geometry')
    return turret

def repair_model(model):
    names = {n.name: i for i, n in enumerate(model.g.nodes)}
    hull, turret = names['Hull'], names['Turret']
    antenna = names['antenna_79']
    if model.parents().get(antenna) == hull:
        world = model.translation(antenna)
        model.g.nodes[hull].children.remove(antenna)
        model.g.nodes[turret].children.append(antenna)
        model.g.nodes[antenna].translation = (world-model.translation(turret)).tolist()
    if 'details_73_turret' in names: return model
    node = names['details_73']; source = model.g.nodes[node]
    mesh = model.g.meshes[source.mesh]
    if len(mesh.primitives) != 1: raise ValueError('Unexpected T54 detail mesh layout')
    primitive = mesh.primitives[0]
    vertices = model.array(primitive.attributes.POSITION)+model.translation(node)
    indices = model.array(primitive.indices).reshape(-1, 3)
    mask = attachment_triangles(vertices, indices)
    split = copy.deepcopy(mesh); split.name = 'details_turret'
    split.primitives[0].indices = model.add_array(indices[mask].reshape(-1, 1), 'SCALAR', 5125)
    primitive.indices = model.add_array(indices[~mask].reshape(-1, 1), 'SCALAR', 5125)
    mesh_index = len(model.g.meshes); model.g.meshes.append(split)
    ni = len(model.g.nodes)
    model.g.nodes.append(Node(name='details_73_turret', mesh=mesh_index,
        translation=(model.translation(node)-model.translation(turret)).tolist()))
    model.g.nodes[turret].children.append(ni)
    return model

def verify_model(original, repaired):
    """Verify bind pose, full vertex attributes and exact triangle coverage."""
    old = {n.name:i for i,n in enumerate(original.g.nodes)}
    new = {n.name:i for i,n in enumerate(repaired.g.nodes)}
    assert repaired.parents()[new['antenna_79']] == new['Turret']
    assert repaired.parents()[new['details_73_turret']] == new['Turret']
    assert repaired.parents()[new['details_73']] == new['Hull']
    for name,index in old.items():
        np.testing.assert_allclose(original.translation(index),repaired.translation(new[name]),atol=1e-6)
    source = original.g.meshes[original.g.nodes[old['details_73']].mesh].primitives[0]
    pieces = [repaired.g.meshes[repaired.g.nodes[new[name]].mesh].primitives[0]
              for name in ['details_73','details_73_turret']]
    triangles = original.array(source.indices).reshape(-1,3)
    rows = np.concatenate([repaired.array(p.indices).reshape(-1,3) for p in pieces])
    assert sorted(map(tuple,triangles.tolist())) == sorted(map(tuple,rows.tolist()))
    for p in pieces:
        assert vars(p.attributes) == vars(source.attributes) and p.material == source.material
        for index in vars(source.attributes).values():
            if index is not None: np.testing.assert_array_equal(original.array(index),repaired.array(index))
    np.testing.assert_allclose(repaired.translation(new['details_73_turret']),
                               original.translation(old['details_73']),atol=1e-6)
    assert original.g.images == repaired.g.images and original.g.materials == repaired.g.materials
    return dict(bind_pose_preserved=True,triangle_winding_coverage_preserved=True,
                turret_attachment_parentage_valid=True,vertex_attributes_materials_preserved=True)

from .weapon_assets import clone_he_pool

def repair_resources(source, model_path, destination):
    source, destination = Path(source), Path(destination)
    if hashlib.sha256(source.read_bytes()).hexdigest() != R9_SHA:
        raise ValueError('Expected exact reviewed r9 data.unity3d')
    adapter = Adapter(source); sf = adapter.sf
    before = {(o.assets_file.name,o.path_id): hashlib.sha256(o.get_raw_data()).hexdigest() for o in adapter.env.objects}
    # Preserve all r9 materials/textures, colliders, physics and scene state.
    gun_go = sf.objects[140370]; gt = assert_roundtrip(gun_go)
    if gt['m_Name'] != 'T54_Gun': raise ValueError('Unexpected T54 hierarchy')
    gt['m_Name'] = 'Gun'; store(gun_go, gt)
    model = Model(model_path); repaired = repair_model(model)
    detail_go = sf.objects[140518]; detail_tr = sf.objects[140519]
    mesh = sf.objects[140779]; original = assert_roundtrip(mesh)
    if original['m_IndexFormat'] != 1 or len(original['m_SubMeshes']) != 1: raise ValueError('Unexpected detail indices')
    vd = original['m_VertexData']; channels = vd['m_Channels']
    stride = max(c['offset']+c['dimension']*4 for c in channels if c['stream']==0)
    if stride != 48: raise ValueError('Expected r9 tangents and full vertex layout')
    vertices = np.ndarray((vd['m_VertexCount'],3), dtype='<f4', buffer=vd['m_DataSize'], strides=(stride,4)).copy()
    indices = np.frombuffer(bytes(original['m_IndexBuffer']),dtype='<u4').reshape(-1,3)
    mask = attachment_triangles(vertices, indices)
    def mesh_tree(name, selection):
        t = copy.deepcopy(original); t['m_Name'] = name
        used = np.unique(selection); bounds = aabb(vertices[used])
        t['m_IndexBuffer'] = selection.astype('<u4').tobytes(); t['m_LocalAABB'] = bounds
        t['m_SubMeshes'][0].update(firstByte=0,indexCount=selection.size,firstVertex=0,vertexCount=vd['m_VertexCount'],localAABB=bounds)
        t['m_MeshLodInfo']['m_SubMeshes'][0]['m_Levels'] = [{'m_IndexStart':0,'m_IndexCount':selection.size}]
        return t
    store(mesh, mesh_tree('T54_1949_details_hull',indices[~mask]))
    split_mesh = adapter.new(mesh, raw=encode_complete(mesh, mesh_tree('T54_1949_details_turret',indices[mask])))
    parts = [sf.objects[c['component']['m_PathID']] for c in assert_roundtrip(detail_go)['m_Component']]
    nodes = [detail_go]+parts; ids = {o.path_id:adapter.new(o).path_id for o in nodes}
    for old in nodes: store(sf.objects[ids[old.path_id]],remap(assert_roundtrip(old),ids))
    split_go, split_tr = sf.objects[ids[140518]], sf.objects[ids[140519]]
    gt = assert_roundtrip(split_go); gt['m_Name'] = 'T54_details_73_turret'; store(split_go,gt)
    mf = sf.objects[ids[140781]]; ft = assert_roundtrip(mf); ft['m_Mesh'] = pp(split_mesh.path_id); store(mf,ft)
    # Source vertices are in hull coordinates. Keep the bind pose unchanged.
    turret = sf.objects[140369]; pivot = assert_roundtrip(turret)['m_LocalPosition']
    st = assert_roundtrip(split_tr); st['m_Father'] = pp(turret.path_id); st['m_Children'] = []
    st['m_LocalPosition'] = {k:-v for k,v in pivot.items()}; store(split_tr,st)
    tt = assert_roundtrip(turret); tt['m_Children'].append(pp(split_tr.path_id)); store(turret,tt)
    antenna = sf.objects[140531]; at = assert_roundtrip(antenna); hull = sf.objects[at['m_Father']['m_PathID']]
    ht = assert_roundtrip(hull); ht['m_Children'] = [p for p in ht['m_Children'] if p['m_PathID']!=antenna.path_id]; store(hull,ht)
    at['m_Father'] = pp(turret.path_id); at['m_LocalPosition'] = {k:at['m_LocalPosition'][k]-pivot[k] for k in pivot}; store(antenna,at)
    tt = assert_roundtrip(turret); tt['m_Children'].append(pp(antenna.path_id)); store(turret,tt)
    pool = clone_he_pool(adapter,sf.objects[139434],sf.objects[139377])
    destination.mkdir(parents=True,exist_ok=True)
    output = destination/'data.unity3d'; bundle = next(f for f in adapter.env.files.values() if hasattr(f,'save_fs'))
    output.write_bytes(bundle.save(packer='lz4')); repaired.save(destination/'T54_1949-r10.glb')
    model_checks = verify_model(Model(model_path),Model(destination/'T54_1949-r10.glb'))
    saved = Adapter(output); after = {(o.assets_file.name,o.path_id):hashlib.sha256(o.get_raw_data()).hexdigest() for o in saved.env.objects}
    changed = [k for k in before if before[k]!=after[k]]
    forbidden = [k for k in changed if saved.files[k[0]].objects[k[1]].type.name in ['Material','Texture2D','Rigidbody','Collider','BoxCollider','WheelCollider']]
    if forbidden: raise AssertionError('Material/physics preservation failed: '+repr(forbidden))
    pc = read_mb('PlayerControl',saved.sf.objects[139382].get_raw_data())
    tr = assert_roundtrip(saved.sf.objects[pc['turretTrf']['m_PathID']])
    child_names = [assert_roundtrip(saved.sf.objects[assert_roundtrip(saved.sf.objects[c['m_PathID']])['m_GameObject']['m_PathID']])['m_Name'] for c in tr['m_Children']]
    assert 'Gun' in child_names
    lv = read_mb('Launcher',saved.sf.objects[139434].get_raw_data()); assert len(lv['shellHeGos'])==2
    for ref in lv['shellHeGos']: assert not assert_roundtrip(saved.sf.objects[ref['m_PathID']])['m_IsActive']
    assert assert_roundtrip(saved.sf.objects[140531])['m_Father']==pp(turret.path_id)
    assert assert_roundtrip(saved.sf.objects[split_mesh.path_id])['m_VertexData']==original['m_VertexData']
    assert assert_roundtrip(saved.sf.objects[140779])['m_VertexData']==original['m_VertexData']
    assert sorted(map(tuple,np.concatenate([indices[mask],indices[~mask]]).tolist())) == sorted(map(tuple,indices.tolist()))
    # All new native references must resolve; every Transform must have a
    # reciprocal parent/child link after saving and reloading the bundle.
    for pid in adapter.created:
        obj=saved.sf.objects[pid]
        if obj.type.name=='MonoBehaviour': continue # full raw donor clone
        tree=assert_roundtrip(obj)
        for p in pointers(tree):
            if not p['m_PathID']: continue
            name=saved.sf.name if not p['m_FileID'] else saved.sf.externals[p['m_FileID']-1].path.rsplit('/',1)[-1]
            if name in ['unity default resources','unity_builtin_extra']: continue
            file=saved.files[name]
            assert p['m_PathID'] in file.objects
        if obj.type.name=='Transform':
            for child in tree['m_Children']:
                assert assert_roundtrip(saved.sf.objects[child['m_PathID']])['m_Father']==pp(pid)
            parent_id=tree['m_Father']['m_PathID']
            if parent_id: assert pp(pid) in assert_roundtrip(saved.sf.objects[parent_id])['m_Children']
    report = dict(passed=True,input_sha256=R9_SHA,output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        turret_triangles=int(mask.sum()),hull_triangles=int((~mask).sum()),he_pool=pool,
        all_r9_materials_textures_physics_preserved=True,vertex_normals_uv_tangents_preserved=True,
        changed_existing_objects=[dict(file=f,id=pid) for f,pid in changed],created_objects=adapter.created,
        model_checks=model_checks,created_native_references_valid=True,
        model_sha256=hashlib.sha256((destination/'T54_1949-r10.glb').read_bytes()).hexdigest(),android_device_test='not performed')
    (destination/'asset-repair-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report

