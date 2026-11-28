"""Read the signed Android game and both refit fields; this is not a device test.

Pin the stock 5.1.0 launcher classifier, scope dependency and the real compiled
projectile arithmetic in the packaged sources before replaying them on the scene
inputs. No process attachment or instrumentation is needed.
"""
import argparse, hashlib, io, json, math, struct, zipfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
from tankbuilder.barbarossa.mission.release import Members
from tankbuilder.barbarossa.mission.codec import cname
from tankbuilder.barbarossa.mission.scope_flight import IMPORTED,verify_optics,verify_actor_roots
from tankbuilder.extra_campaign import file
from tankbuilder.serialization import parse_complete as val
from tankbuilder.unity_assets import read_mb

GAME='lib/arm64-v8a/libil2cpp.so'
CORE='assets/Hatch/mods/tankinvincible3000.hatch'
DATA='assets/bin/Data/data.unity3d'
F32=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]

def image(data):
    e=ELFFile(io.BytesIO(data))
    seg=[(x['p_vaddr'],x.data()) for x in e.iter_segments() if x['p_type']=='PT_LOAD']
    def get(a,n):return next(b[a-i:a-i+n] for i,b in seg if i<=a<=i+len(b)-n)
    return get,e

def check_code(game,core):
    g,_=image(game);c,elf=image(core)
    # Launcher.Init: String.op_Equality, then set isSubGun to 0/1. The main path
    # also copies UnitStatus.InitShellSpeed. ShellMove alternates initialization
    # and gravity branches; its first tick stores the magnitude in nrmInitV.
    def pins(get,table):
        for a,h in table.items():assert get(a,len(bytes.fromhex(h)))==bytes.fromhex(h),hex(a)
    pins(g,{0x195c364:'3c8b4b94c0020036',0x195c3b0:'0000221ee8031f2a605600bd',
            0x195c3c0:'2800805268820239',0x196087c:'68030034',0x196089c:'0139201e618a00bd',
            0x1960904:'4982ffb0001940bd211542bd0808211e689a00bd',
            0x19867f8:'686640f9',0x1986820:'f2110f94a04600b4',0x1986830:'69dd7694',
            0x19868b4:'1f090071',0x198bb14:'2800805201b5881a'})
    stock_scale=struct.unpack('<f',g(0x9a9214,4))[0]
    assert math.isclose(stock_scale,.23,rel_tol=1e-6)
    word,=struct.unpack('<I',g(0x1962814,4))  # stock ShellMove constructor: movz w9, imm16, lsl #16
    assert word&0xffe0001f==0x52a00009 and g(0x196281c,4)==bytes.fromhex('097c00b9')
    stock_gravity=struct.unpack('<f',struct.pack('<I',((word>>5)&65535)<<16))[0]
    sym=elf.get_section_by_name('.symtab')
    def start(n):return sym.get_symbol_by_name(n)[0]['st_value']
    fix=start('shell_fixed_update');gate=start('attack_info')
    def half(a):return (struct.unpack('<I',c(a,4))[0]>>5)&65535
    def scalar(a,b):return struct.unpack('<f',struct.pack('<I',half(a)|(half(b)<<16)))[0]
    div=scalar(fix+0x7c,fix+0x80);gravity=scalar(fix+0x94,fix+0xa0)
    assert div==stock_scale and math.isclose(gravity,9.81,abs_tol=1e-5)
    # Inspect the original module (not its possibly different development source).
    at=gate+0x640
    op,branch=struct.unpack('<II',c(at,8))
    assert op==0x39428288 and branch>>24==0x35 and (branch>>5)&0x7ffff==56
    assert struct.unpack('<I',c(fix+0x88,4))[0]==0x1e211800  # fdiv s0,s0,s1
    assert struct.unpack('<I',g(0x1960910,4))[0]==0x1e210808 # fmul s8,s0,s1
    return stock_scale,stock_gravity,gravity

def check(old,new,kit):
    with zipfile.ZipFile(old) as a,zipfile.ZipFile(new) as b,zipfile.ZipFile(kit) as k:
        assert a.read(GAME)==b.read(GAME) and a.read(CORE)==b.read(CORE)
        with zipfile.ZipFile(io.BytesIO(b.read(CORE))) as z:core=z.read('module.so')
        scale,sg,g=check_code(b.read(GAME),core)
        previous=Members(a.read(DATA));actual=Members(b.read(DATA))
        name='globalgamemanagers.assets';names={p:o.read_typetree(check_read=False)['m_ClassName'] for p,o in file(actual.read(name)).objects.items() if o.type.name=='MonoScript'}
        data=json.loads(k.read('mission.json'));normal=file(actual.read('level8'))
        assert previous.read('level8')==actual.read('level8')
        def has_button(sf,go):
            return any(o.type.name=='MonoBehaviour' and cname(o,names)=='Button'
                       for p in val(sf.objects[go])['m_Component'] for o in [sf.objects[p['component']['m_PathID']]])
        assert has_button(normal,4057)
        speed_cases={};counts={}
        for side,s in data['sides'].items():
            n='level'+str(s['index']);before=file(previous.read(n));after=file(actual.read(n))
            if side=='GE':
                assert not has_button(before,4057) and has_button(after,4057)
                verify_optics(after,normal,s['optics'],s['primary_button'],names)
            verify_actor_roots(after,before,s)
            hero=next(u for u in s['units'] if u['team']=='player')
            actors=[(u,u['tank']) for u in s['units']]+[(s['factory'],hero['tank'])]
            changed=0
            for row,tank in actors:
                ident=row['controllers']['Launcher']
                def gun(sf):return read_mb('Launcher',sf.objects[ident].get_raw_data())
                pre,post=gun(before),gun(after)
                if tank not in IMPORTED:
                    assert pre==post and not pre['weaponName'];continue
                with zipfile.ZipFile(io.BytesIO(b.read('assets/Hatch/mods/'+tank+'.hatch'))) as h:w=json.loads(h.read('weapon.json'))
                assert w['ballistics']=='physical' and pre['weaponName']==w['name'] and not post['weaponName']
                assert w['muzzleVelocity']==post['initSpeed']
                # Native GetShellAttackInfo preserves its own per-ammo multiplier.
                # For AP the actual nominal value is the launcher's base. Repeat
                # with two other inputs to also guard against applying the scale twice.
                nominal=w['muzzleVelocity']
                for attack_speed in (nominal,nominal*.7,nominal*1.3):
                    oldv=F32(F32(attack_speed)*scale)
                    newv=F32(F32(F32(attack_speed)/scale)*scale)
                    assert math.isclose(newv,attack_speed,rel_tol=1e-6) and oldv<.24*newv
                speed_cases[tank]={'old_AP_initial_game_speed':round(F32(nominal*scale),3),'new_AP_initial_game_speed':nominal}
                changed+=1
            assert changed==14;counts[side]=changed
        return {'stock_speed_scale':round(scale,2),'stock_gravity':sg,'mod_gravity':round(g,2),'field_launchers_restored':counts,
                'AP_first_tick_from_packaged_code_and_data':speed_cases,'android_device_test':False}
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('old','new','kit'):p.add_argument('--'+n,type=Path,required=True)
    print(json.dumps(check(**vars(p.parse_args())),ensure_ascii=False,indent=2))
