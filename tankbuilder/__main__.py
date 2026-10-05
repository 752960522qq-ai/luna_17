import argparse
import json
import sys
import tempfile
from pathlib import Path
from .package import GamePackage
from .profiles import inspect_game, draft_profile, FEATURES
from .runner import run_build, write_report
from .tankpack import validate_pack

def main():
    parser=argparse.ArgumentParser(prog='TankInvincible')
    parser.add_argument('--profiles',type=Path)
    sub=parser.add_subparsers(dest='action',required=True)
    scan=sub.add_parser('inspect',help='检测安装包并输出版本/兼容性报告')
    scan.add_argument('input',type=Path);scan.add_argument('--out',type=Path,default=Path('build/inspection'))
    draft=sub.add_parser('draft-profile',help='生成默认禁止构建的新版适配草案')
    draft.add_argument('input',type=Path);draft.add_argument('--out',type=Path,required=True)
    packs=sub.add_parser('tankpack',help='批量校验 Tank Pack 格式，不写入游戏资源');packs.add_argument('input',type=Path,nargs='+')
    build=sub.add_parser('build',help='对已验证版本构建并签名 APK')
    build.add_argument('input',type=Path);build.add_argument('--config',type=Path,required=True)
    build.add_argument('--output',type=Path,required=True)
    build.add_argument('--features',nargs='+',choices=FEATURES)
    build.add_argument('--tankpack',nargs='*',type=Path,default=[])
    prepare=sub.add_parser('prepare-assets',help='写入已审核的玩家 Tank Pack，只输出 Unity 资源，不打包 APK')
    prepare.add_argument('input',type=Path);prepare.add_argument('--tankpack',type=Path,required=True);prepare.add_argument('--out',type=Path,required=True)
    sub.add_parser('gui',help='打开本地构建界面')
    args=parser.parse_args()
    try:
        if args.action=='prepare-assets':
            from .unity_assets import prepare_assets
            from .tankpack import extract_reviewed_pack
            with tempfile.TemporaryDirectory(prefix='tank-assets-') as temp:
                temp=Path(temp);pack=extract_reviewed_pack(args.tankpack,temp/'pack')
                if args.input.suffix.lower() in ('.apk','.apks'):
                    with GamePackage(args.input) as game:
                        inspection=inspect_game(game,args.profiles)
                        if not inspection['can_build']:raise ValueError('安装包尚未通过版本/资源检查')
                        data=temp/'data.unity3d';data.write_bytes(game.bundle)
                else:data=args.input
                print(json.dumps(prepare_assets(data,pack,args.out),ensure_ascii=False,indent=2))
            return 0
        if args.action=='gui':
            from .gui import main as gui
            gui();return 0
        if args.action=='tankpack':
            reports=[validate_pack(path) for path in args.input];print(json.dumps(reports,ensure_ascii=False,indent=2));return 0 if all(r['valid'] for r in reports) else 2
        if args.action=='build':
            r=run_build(args.input,args.output,args.config,args.features,args.tankpack,args.profiles)
            return 0 if r['status']=='succeeded' else 2
        with GamePackage(args.input) as game:report=inspect_game(game,args.profiles)
        if args.action=='draft-profile':
            print(draft_profile(report,args.out,args.profiles));return 0
        write_report(report,args.out,'inspection');print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report['can_build'] else 2
    except Exception as exc:
        print('错误：'+str(exc),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
