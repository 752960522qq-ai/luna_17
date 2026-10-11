#!/usr/bin/env python3
"""Build Hatch loader DEX and .hatch mods only. Never assemble or sign an APK."""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hatch.package import pack_module
from hatch.features import pack_features

def run(*args):subprocess.run([str(a) for a in args],check=True)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk',type=Path,required=True)
    parser.add_argument('--android-jar',type=Path,required=True)
    parser.add_argument('--voice-archive',type=Path,help='Original uploaded Chinese WAV ZIP; builds Better Crew Experience')
    parser.add_argument('--r8',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,default=ROOT/'build/mods')
    parser.add_argument('--output',type=Path,default=ROOT/'dist/mods')
    args=parser.parse_args();work=args.work_dir.resolve();out=args.output.resolve()
    work.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    host={'Linux':'linux-x86_64','Darwin':'darwin-x86_64','Windows':'windows-x86_64'}[platform.system()]
    clang=args.ndk/'toolchains/llvm/prebuilt'/host/'bin'/('aarch64-linux-android28-clang.cmd' if os.name=='nt' else 'aarch64-linux-android28-clang')
    library=work/'libaotmod.so'
    run(clang,'-shared','-fPIC','-O2','-Wall','-Wextra','-mno-outline-atomics',
        '-Wl,-z,max-page-size=16384,--hash-style=both,-z,defs,-soname,libaotmod.so',
        ROOT/'native/aotmod.c',ROOT/'native/guards.S','-ldl','-llog','-lm','-o',library)
    classes=work/'loader-classes';module=work/'module-classes';dex=work/'module-dex'
    for directory in (classes,module,dex):
        if directory.exists():shutil.rmtree(directory)
        directory.mkdir(parents=True,exist_ok=True)
    run('java','com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',args.android_jar,'-d',classes,
        *sorted((ROOT/'loader/src').rglob('*.java')),*sorted((ROOT/'app/stubs').rglob('*.java')))
    run('java','com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',os.pathsep.join(map(str,(args.android_jar,classes))),'-d',module,
        *sorted((ROOT/'mods/tankinvincible/src').rglob('*.java')))
    loader_dex=work/'loader-dex'
    if loader_dex.exists():shutil.rmtree(loader_dex)
    loader_dex.mkdir()
    run('java','-cp',args.r8,'com.android.tools.r8.D8','--lib',args.android_jar,'--classpath',classes,'--min-api','28','--output',loader_dex,
        *sorted((classes/'com/hatch/loader').rglob('*.class')))
    run('java','-cp',args.r8,'com.android.tools.r8.D8','--lib',args.android_jar,'--classpath',classes,'--min-api','28','--output',dex,
        *sorted(module.rglob('*.class')))
    (out/'hatch-loader-0.4.dex').write_bytes((loader_dex/'classes.dex').read_bytes())
    pack_module(dex/'classes.dex',library,out/'tankinvincible3000.hatch')
    pack_features(ROOT/'mods/better_tank_experience',out/'better_tank_experience-0.1.hatch')
    if args.voice_archive:pack_features(ROOT/'mods/better_crew_experience',out/'better_crew_experience-0.1.hatch',args.voice_archive)
    print('Loader DEX and .hatch packages built:',out)

if __name__=='__main__':main()
