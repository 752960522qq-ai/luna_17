#!/usr/bin/env python3
"""Verify loader/module separation, original payload, native ABI and regression identity."""
import argparse
import contextlib
import hashlib
import io
import json
import re
import struct
import zipfile
from pathlib import Path
from loguru import logger
logger.disable('androguard')
from androguard.core.axml import AXMLPrinter
from androguard.core.dex import DEX
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[1]
NS='{http://schemas.android.com/apk/res/android}'

def verify(apk, source, native_test_report=None, profile_path=None, unity_data=None):
    profile=json.loads(Path(profile_path or ROOT/'profiles/attack-on-tank-5.1.0.json').read_text())
    with contextlib.ExitStack() as stack:
        z=stack.enter_context(zipfile.ZipFile(apk));outer=stack.enter_context(zipfile.ZipFile(source))
        original=outer if 'AndroidManifest.xml' in outer.namelist() else stack.enter_context(zipfile.ZipFile(io.BytesIO(outer.read('base.apk'))))
        migrated='lib/arm64-v8a/libaotmod.so' in original.namelist()
        assert z.testzip() is None,'Corrupt APK entry'
        manifest=AXMLPrinter(z.read('AndroidManifest.xml')).get_xml_obj()
        assert manifest.attrib['package']==profile['package']
        assert manifest.attrib[NS+'versionName']==profile['version_name']
        assert manifest.attrib[NS+'versionCode']==str(profile['version_code'])
        app=manifest.find('application')
        assert app.attrib[NS+'label']=='突击坦克 · 舱盖'
        assert app.attrib[NS+'extractNativeLibs']=='true'
        launcher=[a for a in app.findall('activity') if a.find('intent-filter') is not None]
        assert any(a.attrib[NS+'name']=='com.hatch.loader.HatchActivity' for a in launcher)
        assert not any(m.attrib.get(NS+'name') in {'com.android.vending.splits.required','com.android.vending.splits'} for m in app.findall('meta-data'))
        preserved=0;original_dex=[]
        for info in original.infolist():
            name=info.filename
            if info.is_dir() or name=='AndroidManifest.xml' or name=='stamp-cert-sha256' or name=='META-INF/MANIFEST.MF' or re.fullmatch(r'META-INF/[^/]+\.(RSA|DSA|EC|SF)',name,re.I):continue
            if name.startswith('assets/Hatch/') or name=='lib/arm64-v8a/libaotmod.so' or (migrated and name=='classes4.dex'):continue
            if unity_data and name=='assets/bin/Data/data.unity3d':assert z.read(name)==Path(unity_data).read_bytes();continue
            assert z.read(name)==original.read(name),f'Original payload changed: {name}'
            preserved+=1
            if re.fullmatch(r'classes\d*\.dex',name):original_dex.append(name)
        added=set(n for n in z.namelist() if re.fullmatch(r'classes\d*\.dex',n))-set(original_dex)
        assert len(added)==1
        dex=DEX(z.read(next(iter(added))))
        classes=list(dex.get_classes());assert classes and all(c.get_name().startswith('Lcom/hatch/loader/') for c in classes)
        activity=dex.get_class('Lcom/hatch/loader/HatchActivity;');assert activity.get_superclassname()=='Lcom/unity3d/player/UnityPlayerActivity;'
        assert dex.get_class('Lcom/luna17/aot/NativeBridge;') is None
        assert dex.get_class('Lcom/unity3d/player/UnityPlayerActivity;') is None
        assert 'lib/arm64-v8a/libaotmod.so' not in z.namelist()
        catalog=json.loads(z.read('assets/Hatch/catalog.json'));assert catalog['loader_version']=='0.2'
        core=None
        for entry in catalog['mods']:
            payload=z.read('assets/Hatch/mods/'+entry['id']+'.hatch')
            assert len(payload)==entry['size'] and hashlib.sha256(payload).hexdigest()==entry['sha256']
            with zipfile.ZipFile(io.BytesIO(payload)) as pack:
                doc=json.loads(pack.read('hatch.json'))
                if doc['id']=='tankinvincible3000':
                    core=doc;module=pack.read('module.so');module_dex=pack.read('module.dex')
                    assert core['type']=='module' and core['version']=='1.0' and core['api_version']==2
                    assert hashlib.sha256(module).hexdigest()==core['native_sha256'] and len(module)==core['native_bytes']
                    assert hashlib.sha256(module_dex).hexdigest()==core['dex_sha256'] and len(module_dex)==core['dex_bytes']
        assert core is not None,'Mandatory module missing'
        mod=DEX(module_dex)
        assert mod.get_class('Lcom/luna17/aot/TankInvincibleModule;') is not None
        assert mod.get_class('Lcom/hatch/loader/HatchModule;') is None,'Shared API copied into module'
        assert {'坦无敌3000 1.0','必备前置模组','舱盖 0.2 · 管理 / 导入模组'}.issubset(set(mod.get_strings()))
        bridge=mod.get_class('Lcom/luna17/aot/NativeBridge;')
        native_names={m.get_name() for m in bridge.get_methods() if m.get_access_flags()&0x100}
        assert 'configureMagazine' in native_names
        elf=ELFFile(io.BytesIO(module));assert elf['e_machine']=='EM_AARCH64'
        dynamic=elf.get_section_by_name('.dynamic')
        assert {t.needed for t in dynamic.iter_tags() if t.entry.d_tag=='DT_NEEDED'}=={'libc.so','libdl.so','liblog.so'}
        assert not any(t.entry.d_tag=='DT_TEXTREL' for t in dynamic.iter_tags())
        assert all(s['p_align']>=16384 for s in elf.iter_segments() if s['p_type']=='PT_LOAD')
        exports={s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF'}
        assert all('Java_com_luna17_aot_NativeBridge_'+name in exports for name in native_names)
        assert not any(s.name.startswith('__aarch64_') and s['st_shndx']=='SHN_UNDEF' for s in elf.get_section_by_name('.dynsym').iter_symbols())
        assert hashlib.sha256(z.read('lib/arm64-v8a/libil2cpp.so')).hexdigest()==profile['libil2cpp_sha256']
        with Path(apk).open('rb') as file:
            for info in z.infolist():
                if info.compress_type!=zipfile.ZIP_STORED:continue
                file.seek(info.header_offset);header=file.read(30);name_length,extra_length=struct.unpack_from('<HH',header,26)
                assert (info.header_offset+30+name_length+extra_length)%4==0,info.filename
    results=json.loads(Path(native_test_report).read_text()) if native_test_report else None
    if results:
        assert results['passed'] and results['errors']==0 and results['failures']==0
        assert results['module_sha256']==hashlib.sha256(module).hexdigest()
        assert results['game_library_sha256']==profile['libil2cpp_sha256']
    return dict(file=Path(apk).name,size_bytes=Path(apk).stat().st_size,sha256=hashlib.sha256(Path(apk).read_bytes()).hexdigest(),preserved_original_entries=preserved,loader_version='0.2',prerequisite_version='1.0',loader_module_separation_verified=True,module_16k_elf_alignment=True,native_methods=sorted(native_names),native_execution_tests=results,android_device_test='not performed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apk',required=True);p.add_argument('--apks',required=True);p.add_argument('--report',type=Path);p.add_argument('--native-test-report',type=Path);p.add_argument('--unity-data',type=Path);p.add_argument('--profile',type=Path)
    a=p.parse_args();report=verify(a.apk,a.apks,a.native_test_report,a.profile,a.unity_data)
    text=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.report:a.report.write_text(text)
    print(text)
