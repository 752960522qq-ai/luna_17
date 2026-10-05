#!/usr/bin/env python3
"""Repair the exact r8 resource snapshot, preserving its runtime/prefab.

Standard has no built metallic-map or normal-map variants in this game. Use
the stock T34/85 mobile shader and the supplied GLB's RGB normals instead.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import numpy as np
import UnityPy
from PIL import Image
from tankbuilder.modelrig import Model
from tankbuilder.serialization import apply_reviewed_typetrees, assert_roundtrip, encode_complete
from restore_t54_model import restore

R8_SHA = '8c8bb66ba92605fffaef56afca6ba7ca270b5362481d7d9ebdd37d8150ebb7b6'
R9_SHA = 'f950c94a5445ff84c501875181e674e214ae595f747fe7ff3dd6289bd11b0646'
MODEL_SHA = '6a702bfe0d291c99ea4a1d877aa8801843d2f866844c5fabe4c7c625011fa936'
TARGET_NAMES = frozenset({'mg_dt_rigid1', 'rifled_barrel_c_rigid4',
    'mg_dshkm_ammo_rigid5', 'mg_dshkm_rigid7', 'net_b_rigid8',
    'headlight_glass_rigid9', 'headlight_glass_rigid10', 't_54_1949_body_rigid11',
    'ussr_t_54_1951_track_skin1', 'ussr_t_54_1951_track_skin2'})

def sha(data): return hashlib.sha256(data).hexdigest()

def load(path):
    env = UnityPy.load(str(path)); apply_reviewed_typetrees(env)
    return env, next(o.assets_file for o in env.objects if o.assets_file.name == 'resources.assets')

def store_tree(obj, tree):
    assert_roundtrip(obj); raw = encode_complete(obj, tree)
    assert_roundtrip(obj, raw); obj.set_raw_data(raw)

def store_texture(obj, image, color_space):
    t = assert_roundtrip(obj)
    data = image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
    t.update(m_Width=image.width, m_Height=image.height, m_TextureFormat=4,
        m_MipCount=1, m_CompleteImageSize=len(data), m_IsReadable=True,
        m_StreamingMipmaps=False, m_ColorSpace=color_space)
    t['image data'] = data; t['m_StreamData'] = {'offset': 0, 'size': 0, 'path': ''}
    store_tree(obj, t)

def source_image(model, index):
    image = model.g.images[model.g.textures[index].source]
    v = model.g.bufferViews[image.bufferView]
    im = Image.open(io.BytesIO(bytes(model.blob[v.byteOffset:v.byteOffset + v.byteLength]))).convert('RGBA')
    im.thumbnail((1024, 1024), Image.Resampling.LANCZOS); return im

def repair(source, model_path, destination):
    if not model_path.exists(): restore(model_path)
    if sha(source.read_bytes()) != R8_SHA or sha(model_path.read_bytes()) != MODEL_SHA:
        raise ValueError('Expected reviewed r8 bundle and model; other versions need adaptation')
    env, sf = load(source); model = Model(model_path)
    before = {(o.assets_file.name, o.path_id): sha(o.get_raw_data()) for o in env.objects}
    template = assert_roundtrip(sf.objects[167])
    assert template['m_Name'] == 'T34_85_Body_09' and template['m_Shader']['m_PathID'] == 3176
    shader = sf.objects[3170].read_typetree(check_read=False)['m_ParsedForm']
    keywords = shader['m_KeywordNames']
    programs = [v for ss in shader['m_SubShaders'] for p in ss['m_Passes']
        for stage in ('progVertex', 'progFragment')
        for platform in p[stage]['m_PlayerSubPrograms'] for v in platform]
    assert not any(keywords.index('_METALLICGLOSSMAP') in v['m_KeywordIndices'] for v in programs)
    textures = {assert_roundtrip(o)['m_Name']: o for o in sf.objects.values() if o.type.name == 'Texture2D'}
    mats = {assert_roundtrip(o)['m_Name']: o for o in sf.objects.values() if o.type.name == 'Material'}
    allowed, expected, updates = set(), {}, []
    for mat in model.g.materials:
        if mat.name not in TARGET_NAMES: continue
        obj = mats['T54_1949_' + mat.name]; old = assert_roundtrip(obj)
        assert old['m_Shader']['m_PathID'] == 3170 and dict(old['m_SavedProperties']['m_Floats'])['_Metallic'] == 1.
        tex = dict(old['m_SavedProperties']['m_TexEnvs'])
        main = sf.objects[tex['_MainTex']['m_Texture']['m_PathID']]
        gloss = sf.objects[tex['_MetallicGlossMap']['m_Texture']['m_PathID']]
        pixels = np.array(main.read().image.convert('RGBA'))
        packed = np.asarray(gloss.read().image.convert('RGBA')); assert packed.shape == pixels.shape
        gain = 0.25 if ('track_' in mat.name or mat.name == 'net_b_rigid8') else 0.5
        pixels[:, :, 3] = np.rint(packed[:, :, 3].astype(float) * gain).astype('uint8')
        if main.path_id in expected: assert np.array_equal(expected[main.path_id][0], pixels)
        expected[main.path_id] = (pixels, 1); store_texture(main, Image.fromarray(pixels), 1)
        assert mat.normalTexture is not None
        normal = textures['T54_1949_texture_' + str(model.g.textures[mat.normalTexture.index].source)]
        ni = source_image(model, mat.normalTexture.index)
        expected[normal.path_id] = (np.array(ni), 0); store_texture(normal, ni, 0)
        t = copy.deepcopy(template); t['m_Name'] = old['m_Name']
        t['m_ValidKeywords'] = []; t['m_InvalidKeywords'] = []
        t['m_SavedProperties']['m_TexEnvs'] = [('_MainTex', copy.deepcopy(tex['_MainTex'])),
            ('_BumpMap', {'m_Texture': {'m_FileID': 0, 'm_PathID': normal.path_id},
             'm_Scale': copy.deepcopy(tex['_MainTex']['m_Scale']),
             'm_Offset': copy.deepcopy(tex['_MainTex']['m_Offset'])})]
        floats = dict(t['m_SavedProperties']['m_Floats']); floats.update(_Shininess=0.4, _Metallic=0., _Mode=0.)
        t['m_SavedProperties']['m_Floats'] = list(floats.items())
        colors = dict(t['m_SavedProperties']['m_Colors'])
        colors['_Color'] = dict(r=1., g=1., b=1., a=1.)
        colors['_EmissionColor'] = dict(r=0., g=0., b=0., a=1.)
        t['m_SavedProperties']['m_Colors'] = list(colors.items()); store_tree(obj, t)
        allowed.update([obj.path_id, main.path_id, normal.path_id])
        updates.append({'id': obj.path_id, 'name': mat.name, 'gloss_gain': gain})
    assert len(updates) == 10
    destination.mkdir(parents=True, exist_ok=True); output = destination / 'data.unity3d'
    bundle = next(f for f in env.files.values() if hasattr(f, 'save_fs'))
    output.write_bytes(bundle.save(packer='lz4'))
    assert sha(output.read_bytes()) == R9_SHA, 'Rebuilt resources differ from released r9'
    saved_env, saved = load(output)
    after = {(o.assets_file.name, o.path_id): sha(o.get_raw_data()) for o in saved_env.objects}
    assert set(before) == set(after)
    changed = [k for k in before if before[k] != after[k]]
    assert all(f == 'resources.assets' and pid in allowed for f, pid in changed)
    for pid, (pixels, space) in expected.items():
        assert assert_roundtrip(saved.objects[pid])['m_ColorSpace'] == space
        assert np.array_equal(np.asarray(saved.objects[pid].read().image.convert('RGBA')), pixels)
    for u in updates:
        t = assert_roundtrip(saved.objects[u['id']]); assert t['m_Shader']['m_PathID'] == 3176
        assert not t['m_ValidKeywords'] and dict(t['m_SavedProperties']['m_Floats'])['_Metallic'] == 0.
    report = {'passed': True, 'input_sha256': R8_SHA, 'output_sha256': R9_SHA,
        'repaired_materials': updates, 'texture_pixel_checks': len(expected),
        'changed_objects': [{'file': f, 'id': pid} for f, pid in changed],
        'all_non_material_texture_objects_byte_identical': True, 'android_device_test': 'not performed'}
    (destination / 'material-repair-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True); p.add_argument('--model', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True); a = p.parse_args()
    r = repair(a.source, a.model, a.output_dir)
    print(json.dumps({k: r[k] for k in ('passed', 'output_sha256', 'texture_pixel_checks')}, indent=2))
