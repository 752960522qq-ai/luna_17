import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from . import VERSION
from .package import GamePackage, digest
from .profiles import ROOT, FEATURES, inspect_game, generate_header, native_config_digest
from .tankpack import validate_pack,extract_reviewed_pack

def write_report(report, directory, stem='build_report'):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    (directory/(stem+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['TankInvincible_3000 '+VERSION, '状态：'+str(report.get('status','检测完成')),
        '时间：'+datetime.now(timezone.utc).isoformat()]
    inspection=report.get('inspection',report)
    identity=inspection.get('identity',{})
    lines += ['游戏：'+str(identity.get('version_name','unknown')),
        'Unity：'+str(identity.get('unity_version','unknown')), 'ABI：'+str(identity.get('abi','unknown'))]
    for name,feature in inspection.get('features',{}).items():
        lines.append(name+'：'+('兼容' if feature.get('compatible') else '需要适配'))
    if report.get('error'):lines.append('原因：'+report['error'])
    if report.get('output'):lines.append('输出：'+report['output'])
    lines += ['真机验证：'+str(report.get('android_device_test','not performed')),
        '', '完整指纹和检查结果见同名 JSON。']
    (directory/(stem+'.txt')).write_text('\n'.join(lines)+'\n',encoding='utf-8')

def run_build(input_path, output, config_path, selected=None, tankpacks=(), profiles_dir=None, log=print):
    output=Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    report={'status':'failed','builder_version':VERSION,'android_device_test':'not performed'}
    try:
        config_path=Path(config_path).resolve()
        cfg=json.loads(config_path.read_text(encoding='utf-8'))
        def config_file(value):
            path=Path(value).expanduser()
            return path.resolve() if path.is_absolute() else (config_path.parent/path).resolve()
        selected=list(FEATURES if selected is None else selected)
        if not selected or set(selected)-set(FEATURES):raise ValueError('至少选择一项有效修改功能')
        with GamePackage(input_path) as game:
            inspection=inspect_game(game,profiles_dir);report['inspection']=inspection
            if not inspection['can_build']:raise ValueError('版本、布局或资源指纹尚未审核通过；已输出检测报告')
            if not all(inspection['features'][f]['compatible'] for f in selected):raise ValueError('所选功能需要重新适配')
            report['tankpacks']=[validate_pack(p) for p in tankpacks]
            if len(tankpacks)>1:raise ValueError('当前适配器一次支持一个已审核的 T54 玩家包')
            if not all(x['valid'] and x['can_inject'] for x in report['tankpacks']):raise ValueError('Tank Pack 格式或适配器尚未审核通过')
            profile_path=Path(profiles_dir or ROOT/'profiles')/inspection['profile']
            profile=json.loads(profile_path.read_text(encoding='utf-8'))
            paths={k:config_file(cfg[k]) for k in ('android_jar','r8','apksigner','zipalign','keystore','password_file')}
            for key,path in paths.items():
                if not path.is_file():raise ValueError('缺少 '+key+'：'+str(path))
            if not shutil.which('java'):raise ValueError('需要 JDK 17 或更高版本')
            with tempfile.TemporaryDirectory(prefix='tank-build-',dir=output.parent) as temporary:
                work=Path(temporary);source=work/'source'
                for directory in ('app','native','scripts','profiles','tests'):
                    shutil.copytree(ROOT/directory,source/directory,ignore=shutil.ignore_patterns('__pycache__'))
                generate_header(profile,source/'native/profile_config.h')
                chosen=source/'profiles/selected.json';chosen.write_text(json.dumps(profile),encoding='utf-8')
                flags={'GODMODE':'godmode','INFINITE_AMMO':'infinite_ammo','TANK_SWAP':'tank_swap'}
                feature_java='package com.luna17.aot;\nfinal class FeatureConfig {\nstatic final String BUILD_LABEL = '+json.dumps(profile['version_name']+'  /  ARM64 '+profile['builder']['revision'])+';\n'+''.join(
                    'static final boolean '+k+' = '+str(v in selected).lower()+';\n' for k,v in flags.items())+'}\n'
                (source/'app/src/com/luna17/aot/FeatureConfig.java').write_text(feature_java,encoding='utf-8')
                normalized=game.normalized(work/'input.apks')
                original_lib=work/'libil2cpp.so';original_lib.write_bytes(game.library)
                native=cfg.get('native_prebuilt')
                if native:
                    native=config_file(native)
                    if digest(native.read_bytes())!=profile['builder'].get('prebuilt_module_sha256'):
                        raise ValueError('预编译模块指纹不匹配；请配置 NDK 重新编译')
                    if native_config_digest(profile)!=profile['builder'].get('prebuilt_config_sha256'):
                        raise ValueError('布局/原生配置已变化，不能复用此前预编译模块')
                elif not cfg.get('ndk'):raise ValueError('需要匹配版本的预编译模块或 NDK')
                command=[sys.executable,str(source/'scripts/build.py'),'--apks',str(normalized),
                    '--profile',str(chosen),'--work-dir',str(work/'build'),'--output',str(work/'signed.apk'),
                    '--alias',cfg.get('alias','luna17')]
                for k,v in paths.items():command.extend(['--'+k.replace('_','-'),str(v)])
                # CLI names for existing build script differ from config names.
                command.extend(['--native-prebuilt',str(native)] if native else ['--ndk',str(config_file(cfg['ndk']))])
                prepared=None
                if tankpacks:
                    from .unity_assets import prepare_assets
                    pack=extract_reviewed_pack(tankpacks[0],work/'pack')
                    original_data=work/'data-original.unity3d';original_data.write_bytes(game.bundle)
                    report['asset_preparation']=prepare_assets(original_data,pack,work/'prepared-assets',log)
                    prepared=work/'prepared-assets/data.unity3d'
                    assets_test_report=work/'asset-tests.json'
                    assets_test=subprocess.run([sys.executable,str(source/'tests/test_assets.py'),
                        '--original',str(original_data),'--modified',str(prepared),
                        '--report',str(assets_test_report)],capture_output=True,text=True)
                    if assets_test.returncode:raise ValueError('选车/战斗资源回归失败：'+assets_test.stderr[-1500:])
                    report['asset_verification']=json.loads(assets_test_report.read_text())
                    command.extend(['--unity-data',str(prepared)])
                log('构建菜单、合并资源、对齐并签名…')
                process=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
                (output.parent/'build_tool_output.txt').write_text(process.stdout,encoding='utf-8')
                if process.returncode:raise ValueError('构建工具失败；详情见 build_tool_output.txt')
                module=Path(native) if native else work/'build/libaotmod.so'
                test_report=work/'native-tests.json'
                tests=subprocess.run([sys.executable,str(source/'tests/test_native.py'),'--module',str(module),
                    '--game-library',str(original_lib),'--report',str(test_report)],capture_output=True,text=True)
                if tests.returncode:raise ValueError('原生执行回归失败：'+tests.stderr[-1500:])
                sys.path.insert(0,str(source/'scripts'))
                from verify import verify
                verification=verify(work/'signed.apk',normalized,test_report,chosen,prepared)
                certs=subprocess.check_output(['java','-jar',str(paths['apksigner']),'verify','--print-certs',str(work/'signed.apk')],text=True)
                certificate=re.search(r'certificate SHA-256 digest: ([a-f0-9]+)',certs).group(1)
                expected=cfg.get('expected_certificate_sha256')
                if expected and certificate!=expected:raise ValueError('签名与指定测试版不一致；覆盖安装检查未通过')
                report.update(status='succeeded',selected_features=selected,verification=verification,
                    signing_certificate_sha256=certificate,output=str(output))
                # Only a fully checked APK becomes the user's output.
                os.replace(work/'signed.apk',output)
                log('构建成功：'+str(output))
    except Exception as exc:
        report['error']=str(exc)
        log('构建未完成：'+str(exc))
    write_report(report,output.parent)
    return report
