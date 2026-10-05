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
    prepare.add_argument('input',type=Path);prepare.add_argument('--tankpack',type=Path,nargs='+',required=True);prepare.add_argument('--out',type=Path,required=True)
    project=sub.add_parser('project',help='创建、检查、导入模型/贴图和导出可复用坦克项目')
    actions=project.add_subparsers(dest='operation',required=True)
    create=actions.add_parser('create');create.add_argument('directory',type=Path);create.add_argument('--template',default='T54_1949');create.add_argument('--id',required=True)
    check=actions.add_parser('check');check.add_argument('directory',type=Path)
    pack=actions.add_parser('pack');pack.add_argument('directory',type=Path);pack.add_argument('--output',type=Path,required=True)
    model=actions.add_parser('model');model.add_argument('directory',type=Path);model.add_argument('input',type=Path);model.add_argument('--bindings',type=Path)
    texture=actions.add_parser('texture');texture.add_argument('directory',type=Path);texture.add_argument('input',type=Path);texture.add_argument('--material',required=True);texture.add_argument('--slot',choices=['baseColor','normal'],default='baseColor')
    sub.add_parser('gui',help='打开本地构建界面')
    args=parser.parse_args()
    try:
        if args.action=='project':
            from .project import create_project,validate_project,pack_project,import_model,replace_texture
            if args.operation=='create':result=create_project(args.directory,args.template,args.id)
            elif args.operation=='check':result=validate_project(args.directory)
            elif args.operation=='pack':result=pack_project(args.directory,args.output)
            elif args.operation=='model':result=import_model(args.directory,args.input,json.loads(args.bindings.read_text()) if args.bindings else None)
            else:result=replace_texture(args.directory,args.material,args.input,args.slot)
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if args.operation=='create' or result['valid'] else 2
        if args.action=='prepare-assets':
            from .unity_assets import prepare_assets
            from .tankpack import extract_reviewed_pack
            with tempfile.TemporaryDirectory(prefix='tank-assets-') as temp:
                temp=Path(temp);pack=[extract_reviewed_pack(p,temp/('pack'+str(i))) for i,p in enumerate(args.tankpack)]
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
