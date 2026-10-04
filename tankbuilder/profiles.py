import copy
import io
import json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from .package import digest

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ('godmode', 'infinite_ammo', 'tank_swap')
DEPENDENCIES = {
    'godmode': ['UnitDamage.Damage', 'UnitDamage.SetDamage', 'UnitMove.HitEngine', 'GameControl.Update'],
    'infinite_ammo': ['PlayerControl.Update', 'GameControl.Update'],
    'tank_swap': ['PlayerControl.Update', 'GameControl.Update', 'TankGenManager._GenerateUnit'],
}

def load_profiles(directory=None):
    return [(p, json.loads(p.read_text(encoding='utf-8'))) for p in sorted(Path(directory or ROOT/'profiles').glob('*.json'))]

def rva_bytes(library, rva, size):
    elf = ELFFile(io.BytesIO(library))
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= rva and rva+size <= segment['p_vaddr']+segment['p_filesz']:
            start=segment['p_offset']+rva-segment['p_vaddr']
            return library[start:start+size]
    raise ValueError('RVA 不在文件加载段中：'+hex(rva))

def inspect_game(game, directory=None):
    candidates = load_profiles(directory)
    if not candidates: raise ValueError('没有版本配置')
    selected = next(((p,v) for p,v in candidates if v.get('version_name')==game.identity['version_name']), candidates[0])
    path, profile = selected
    checks = {k: profile.get(k)==v for k,v in game.hashes.items()}
    checks.update({k: profile.get(k)==game.identity[k] for k in ('package','version_name','version_code','abi')})
    fingerprints = []
    for name, target in profile.get('fingerprints', {}).items():
        try: actual=digest(rva_bytes(game.library,int(target['rva'],16),target['size']))
        except ValueError: actual=None
        fingerprints.append({'name': name, 'rva': target['rva'], 'size': target['size'],
            'expected_sha256':target['sha256'], 'actual_sha256':actual, 'match':actual==target['sha256']})
    reviewed = profile.get('builder', {}).get('verified') is True
    compatible = reviewed and all(checks.values()) and all(f['match'] for f in fingerprints) and bool(fingerprints) and not game.resource_splits
    return {'schema':1, 'builder_version':'1.0.0', 'input':str(game.path), 'container':game.kind,
        'identity':game.identity, 'hashes':game.hashes, 'profile':path.name,
        'identity_and_payload_checks':checks, 'module_fingerprints':fingerprints,
        'features':{f:{'compatible':compatible and profile['builder']['features'].get(f,False),
            'dependencies':DEPENDENCIES[f], 'reason':'已验证版本和指纹一致' if compatible else '需要适配或输入包不完整'} for f in FEATURES},
        'can_build':compatible, 'resource_splits':game.resource_splits,
        'tank_injection':{'supported':compatible,'adapter':'aot-5.1.0-arm64-v1','reviewed_models':['T54_1949'],'player_only':True,'reason':'匹配版本时可准备 T54 玩家资源'},
        'android_device_test':profile.get('builder',{}).get('android_device_test','not performed')}

def draft_profile(report, destination, directory=None):
    _, original = load_profiles(directory)[0]
    draft = copy.deepcopy(original)
    draft.update(report['identity']); draft.update(report['hashes'])
    draft['builder']['verified'] = False
    draft['builder']['features'] = {f:False for f in FEATURES}
    draft['builder']['prebuilt_module_sha256'] = None
    draft['adaptation_required'] = ['重新定位 RVA 和 API 导出', '验证字段布局、参数 ABI 和资源层级',
        '更新指纹及对应 ARM64 回归', '编译模块并进行真机验证，再审核启用配置']
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return destination

def generate_header(profile, destination):
    macros=profile['native_macros']
    if not all(k.startswith(('RVA_', 'FIELD_')) and k.replace('_','').isalnum() and isinstance(v,str) and v.startswith('0x') and int(v,16)>=0 for k,v in macros.items()):
        raise ValueError('非法原生配置宏')
    symbols={'SYMBOL_BASE_ANCHOR':'base_anchor','SYMBOL_CLASS_METHOD':'class_get_method_from_name','SYMBOL_CLASS_FIELDS':'class_get_fields'}
    text='#pragma once\n// Generated from a reviewed version profile.\n'+''.join(f'#define {k} {v}\n' for k,v in sorted(macros.items()))
    for macro,key in symbols.items():
        value=profile.get('api_symbols',{}).get(key)
        if not isinstance(value,str) or not value.isascii() or not value.replace('_','').isalnum():raise ValueError('非法 API 导出名')
        text+='#define '+macro+' '+json.dumps(value)+'\n'
    Path(destination).write_text(text,encoding='ascii')

def native_config_digest(profile):
    return digest(json.dumps({k:profile[k] for k in ('native_macros','api_symbols','fields','hooks','tank_factory')},sort_keys=True,separators=(',',':')).encode())
