#!/usr/bin/env python3
"""Build Hatch 0.2, its independent TankInvincible3000 1.0 prerequisite, and an APK."""
import argparse
import os
import secrets
import shutil
import subprocess
import sys
import platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from repack_hatch import repack_loader
from hatch.package import pack_module

ROOT=Path(__file__).resolve().parents[1]

def run(*args):
    subprocess.run([str(a) for a in args],check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apks',type=Path,required=True)
    native=p.add_mutually_exclusive_group(required=True)
    native.add_argument('--ndk',type=Path,help='Android NDK directory (Linux x86-64)')
    native.add_argument('--native-prebuilt',type=Path,help='Already validated libaotmod.so')
    p.add_argument('--ecj',type=Path,help='Optional Eclipse Java compiler JAR')
    p.add_argument('--hatch',type=Path,action='append',default=[],help='Built-in .hatch package (repeatable)')
    p.add_argument('--android-jar',type=Path,required=True)
    p.add_argument('--r8',type=Path,required=True)
    p.add_argument('--apksigner',type=Path,required=True,help='apksigner.jar')
    p.add_argument('--zipalign',type=Path,required=True,help='Android SDK zipalign executable')
    p.add_argument('--unity-data',type=Path,help='Derived Unity bundle with matching asset_report.json')
    p.add_argument('--profile',type=Path,default=ROOT/'profiles/attack-on-tank-5.1.0.json')
    p.add_argument('--keystore',type=Path)
    p.add_argument('--password-file',type=Path)
    p.add_argument('--alias',default='luna17')
    p.add_argument('--work-dir',type=Path,default=ROOT/'build')
    p.add_argument('--output',type=Path,default=ROOT/'dist/Attack-on-Tank-5.1.0-luna17-test.apk')
    args=p.parse_args()
    work=args.work_dir.resolve();work.mkdir(parents=True,exist_ok=True)
    args.output=args.output.resolve();args.output.parent.mkdir(parents=True,exist_ok=True)
    java=shutil.which('java');keytool=shutil.which('keytool')
    if not java or not keytool:raise SystemExit('A JDK (17+) is required')
    for file in [args.apks,args.android_jar,args.r8,args.apksigner,args.zipalign,args.profile]:
        if not file.is_file():raise SystemExit(f'Missing file: {file}')
    library=args.native_prebuilt
    if args.ndk:
        host={'Linux':'linux-x86_64','Darwin':'darwin-x86_64','Windows':'windows-x86_64'}[platform.system()]
        clang=args.ndk/'toolchains/llvm/prebuilt'/host/'bin'/('aarch64-linux-android28-clang.cmd' if os.name=='nt' else 'aarch64-linux-android28-clang')
        if not clang.is_file():raise SystemExit(f'Missing compiler: {clang}')
        library=work/'libaotmod.so'
        run(clang,'-shared','-fPIC','-O2','-Wall','-Wextra','-mno-outline-atomics',
            '-Wl,-z,max-page-size=16384,--hash-style=both,-z,defs,-soname,libaotmod.so',
            ROOT/'native/aotmod.c',ROOT/'native/guards.S','-ldl','-llog','-lm','-o',library)
    classes=work/'classes';dex=work/'dex'
    for directory in [classes,dex]:
        if directory.exists():shutil.rmtree(directory)
        directory.mkdir()
    sources=sorted((ROOT/'loader/src').rglob('*.java'))+sorted((ROOT/'app/stubs').rglob('*.java'))
    if args.ecj:
        run(java,'-jar',args.ecj,'-8','-encoding','UTF-8',
            '-cp',args.android_jar,'-d',classes,*sources)
    else:
        run(java,'com.sun.tools.javac.Main','--release','8','-encoding','UTF-8',
            '-cp',args.android_jar,'-d',classes,*sources)
    # The compile-time Unity stub must not be included in the new DEX.
    added_classes=sorted((classes/'com/hatch/loader').rglob('*.class'))
    run(java,'-cp',args.r8,'com.android.tools.r8.D8','--lib',args.android_jar,
        '--classpath',classes,'--min-api','28','--output',dex,*added_classes)
    module_classes=work/'module-classes';module_dex=work/'module-dex'
    for directory in [module_classes,module_dex]:
        if directory.exists():shutil.rmtree(directory)
        directory.mkdir()
    module_sources=sorted((ROOT/'mods/tankinvincible/src').rglob('*.java'))
    run(java,'com.sun.tools.javac.Main','--release','8','-encoding','UTF-8',
        '-cp',os.pathsep.join(map(str,[args.android_jar,classes])),'-d',module_classes,*module_sources)
    run(java,'-cp',args.r8,'com.android.tools.r8.D8','--lib',args.android_jar,
        '--classpath',classes,'--min-api','28','--output',module_dex,*sorted(module_classes.rglob('*.class')))
    prerequisite=args.output.parent/'TankInvincible3000-1.0.hatch'
    pack_module(module_dex/'classes.dex',library,prerequisite)
    unsigned=work/'unsigned.apk'
    repack_loader(args.apks,dex/'classes.dex',unsigned,args.profile,[prerequisite,*args.hatch],args.unity_data)
    aligned=work/'aligned.apk'
    run(args.zipalign,'-f','-P','16','4',unsigned,aligned)
    keystore=args.keystore;password=args.password_file
    if not keystore:
        if password:raise SystemExit('--password-file requires --keystore')
        signing=work/'signing';signing.mkdir(exist_ok=True)
        keystore=signing/'development.jks';password=signing/'password.txt'
        if not keystore.exists():
            password.write_text(secrets.token_urlsafe(32)+'\n');os.chmod(password,0o600)
            run(keytool,'-genkeypair','-keystore',keystore,'-alias',args.alias,
                '-storepass:file',password,'-keypass:file',password,'-keyalg','RSA',
                '-keysize','3072','-sigalg','SHA256withRSA','-validity','3650',
                '-dname','CN=luna_17 Development, OU=Offline Mod, O=luna_17')
    if not password or not password.is_file():raise SystemExit('A signing password file is required')
    run(java,'-jar',args.apksigner,'sign','--ks',keystore,'--ks-key-alias',args.alias,
        '--ks-pass',f'file:{password}','--v1-signing-enabled','false',
        '--v2-signing-enabled','true','--v3-signing-enabled','true','--min-sdk-version','28',
        '--out',args.output,aligned)
    run(java,'-jar',args.apksigner,'verify','--verbose',args.output)
    run(args.zipalign,'-c','-P','16','4',args.output)
    print(args.output)

if __name__=='__main__':main()


