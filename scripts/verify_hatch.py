#!/usr/bin/env python3
"""Inspect packaging, original payload, DEX inheritance and native dependencies."""
import argparse
import hashlib
import io
import json
import re
import struct
import zipfile
from pathlib import Path
from loguru import logger
logger.remove()
from androguard.core.axml import AXMLPrinter
from androguard.core.dex import DEX
from elftools.elf.elffile import ELFFile

ROOT=Path(__file__).resolve().parents[1]
NS='{http://schemas.android.com/apk/res/android}'

def verify(apk,apks,native_test_report=None,profile_path=None,unity_data=None):
    profile=json.loads(Path(profile_path or ROOT/'profiles/attack-on-tank-5.1.0.json').read_text())
    with zipfile.ZipFile(apk) as z, zipfile.ZipFile(apks) as bundle:
        assert z.testzip() is None,'Corrupt ZIP entry'
        manifest=AXMLPrinter(z.read('AndroidManifest.xml')).get_xml_obj()
        assert manifest.attrib['package']==profile['package']
        assert manifest.attrib[NS+'versionName']==profile['version_name']
        assert manifest.attrib[NS+'versionCode']==str(profile['version_code'])
        assert NS+'requiredSplitTypes' not in manifest.attrib
        app=manifest.find('application')
        assert app.attrib[NS+'extractNativeLibs']=='true'
        assert app.attrib[NS+'label']=='坦无敌3000'
        launcher=[a for a in app.findall('activity') if a.find('intent-filter') is not None]
        assert any(a.attrib[NS+'name']=='com.luna17.aot.ModActivity' for a in launcher)
        assert next(a for a in launcher if a.attrib[NS+'name']=='com.luna17.aot.ModActivity').attrib[NS+'label']=='坦无敌3000'
        assert not any(m.attrib.get(NS+'name') in {'com.android.vending.splits.required','com.android.vending.splits'} for m in app.findall('meta-data'))
        assert not any(p.attrib.get(NS+'name')=='android.permission.SYSTEM_ALERT_WINDOW' for p in manifest.findall('uses-permission'))
        with zipfile.ZipFile(io.BytesIO(bundle.read('base.apk'))) as original:
            preserved=0
            for info in original.infolist():
                name=info.filename
                if name=='AndroidManifest.xml' or name=='stamp-cert-sha256' or name=='META-INF/MANIFEST.MF' or re.match(r'META-INF/[^/]+\.(?:RSA|DSA|EC|SF)$',name,re.I):continue
                if unity_data and name=='assets/bin/Data/data.unity3d':
                    assert z.read(name)==Path(unity_data).read_bytes(),'Prepared Unity bundle differs from APK'
                    continue
                assert z.read(name)==original.read(name),f'Original payload changed: {name}'
                preserved+=1
            original_dex=[name for name in original.namelist() if re.fullmatch(r'classes\d*\.dex',name)]
        parent=None
        for name in original_dex:
            if b'Lcom/unity3d/player/UnityPlayerActivity;' not in z.read(name):continue
            parent=DEX(z.read(name)).get_class('Lcom/unity3d/player/UnityPlayerActivity;')
            if parent is not None:break
        assert parent is not None,'Original Unity activity missing'
        assert not parent.get_access_flags() & 0x10,'Unity activity is final'
        for method in parent.get_methods():
            if method.get_name() in {'onCreate','onDestroy'}:assert not method.get_access_flags() & 0x10
        added=set(n for n in z.namelist() if re.fullmatch(r'classes\d*\.dex',n))-set(original_dex)
        assert len(added)==1
        dex=DEX(z.read(next(iter(added))))
        assert {'坦无敌3000','坦克模组加载器','Hatch · 舱盖 0.1'}.issubset(set(dex.get_strings())), 'Mod menu names missing'
        assert dex.get_class('Lcom/unity3d/player/UnityPlayerActivity;') is None,'Compile stub leaked into APK'
        activity=dex.get_class('Lcom/luna17/aot/ModActivity;')
        assert activity.get_superclassname()=='Lcom/unity3d/player/UnityPlayerActivity;'
        bridge=dex.get_class('Lcom/luna17/aot/NativeBridge;')
        native_names={m.get_name() for m in bridge.get_methods() if m.get_access_flags() & 0x100}
        module=z.read('lib/arm64-v8a/libaotmod.so')
        elf=ELFFile(io.BytesIO(module))
        assert elf['e_machine']=='EM_AARCH64'
        dependencies={t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t['d_tag']=='DT_NEEDED'}
        assert dependencies=={'libc.so','libdl.so','liblog.so'}
        assert not any(t['d_tag']=='DT_TEXTREL' for t in elf.get_section_by_name('.dynamic').iter_tags())
        assert all(s['p_align']>=16384 for s in elf.iter_segments() if s['p_type']=='PT_LOAD')
        exports={s.name for s in elf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF'}
        assert all('Java_com_luna17_aot_NativeBridge_'+name in exports for name in native_names)
        assert hashlib.sha256(z.read('lib/arm64-v8a/libil2cpp.so')).hexdigest()==profile['libil2cpp_sha256']
        for info in z.infolist():
            if info.compress_type!=0:continue
            with Path(apk).open('rb') as f:f.seek(info.header_offset);header=f.read(30)
            name_length,extra_length=struct.unpack_from('<HH',header,26)
            assert (info.header_offset+30+name_length+extra_length)%4==0,info.filename
    native_results=None
    if native_test_report:
        native_results=json.loads(native_test_report.read_text())
        assert native_results['passed'] and native_results['errors']==0 and native_results['failures']==0
        assert native_results['module_sha256']==hashlib.sha256(module).hexdigest(),'Native test module differs from APK'
        assert native_results['game_library_sha256']==profile['libil2cpp_sha256']
    return {'file':Path(apk).name,'size_bytes':Path(apk).stat().st_size,
            'sha256':hashlib.sha256(Path(apk).read_bytes()).hexdigest(),
            'preserved_original_entries':preserved,'native_methods':sorted(native_names),
            'module_16k_elf_alignment':True,'display_name':'坦无敌3000','english_name':'Hatch','loader_version':'0.1','manifest_labels_verified':True,'menu_names_verified':True,'original_game_payload_unchanged':unity_data is None,'prepared_unity_data_sha256':hashlib.sha256(Path(unity_data).read_bytes()).hexdigest() if unity_data else None,
            'native_execution_tests':native_results,'android_device_test':'not performed'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apk',required=True);p.add_argument('--apks',required=True);p.add_argument('--report',type=Path);p.add_argument('--native-test-report',type=Path)
    p.add_argument('--unity-data',type=Path);p.add_argument('--profile',type=Path)
    args=p.parse_args();report=verify(args.apk,args.apks,args.native_test_report,args.profile,args.unity_data)
    text=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.report:args.report.write_text(text)
    print(text)


