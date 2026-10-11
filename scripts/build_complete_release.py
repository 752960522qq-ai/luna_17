#!/usr/bin/env python3
"""Build the complete BTE 0.1 APK from the supplied Hatch 0.3 game APK.

Preserves all bundled vehicle packages and embeds the merged crew/gameplay pack.
The original voice ZIP and local signing material are required; never commit keys.
"""
import argparse,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hatch.features import pack_features
from hatch.pack import pack_project
from restore_t54_model import restore

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-apk',type=Path,required=True)
    p.add_argument('--voice-archive',type=Path,required=True)
    p.add_argument('--signing-key',type=Path,required=True,help='PKCS8 DER key')
    p.add_argument('--signing-cert',type=Path,required=True,help='X.509 DER certificate')
    p.add_argument('--work-dir',type=Path,default=ROOT/'build/complete-release')
    p.add_argument('--output',type=Path,default=ROOT/'dist/Attack-on-Tank-Hatch-0.4-BTE0.1-Complete.apk')
    a=p.parse_args()
    for f in (a.base_apk,a.voice_archive,a.signing_key,a.signing_cert):
        if not f.is_file():raise SystemExit('Missing release input: '+str(f))
    content=a.work_dir.resolve()/'content';content.mkdir(parents=True,exist_ok=True)
    packages=[]
    with zipfile.ZipFile(a.base_apk) as base:
        catalog=json.loads(base.read('assets/Hatch/catalog.json'))
        if catalog['loader_version']!='0.3':raise SystemExit('Use the original supplied Hatch 0.3 APK')
        for item in catalog['mods']:
            if item['id']=='tankinvincible3000':continue
            import io
            with zipfile.ZipFile(io.BytesIO(base.read('assets/Hatch/mods/'+item['id']+'.hatch'))) as z:
                entries={n:z.read(n) for n in z.namelist()}
            doc=json.loads(entries['hatch.json'])
            if doc.get('type','tank')!='tank':continue
            doc.setdefault('continuous_fire',doc['id']=='Panzer_II_Ausf_L')
            weapon=json.loads(entries['weapon.json']);weapon['continuousFire']=doc['continuous_fire']
            entries['hatch.json']=json.dumps(doc,ensure_ascii=False,indent=2).encode()
            entries['weapon.json']=json.dumps(weapon,ensure_ascii=False,indent=2).encode()
            path=content/(doc['id']+'.hatch')
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                for name,data in entries.items():z.writestr(name,data)
            packages.append(path)
    grille=ROOT/'tanks/Grille';restore(grille/'model.glb')
    path=content/'Grille.hatch';pack_project(grille,path);packages.append(path)
    path=content/'better_tank_experience-0.1.hatch';pack_features(ROOT/'mods/better_tank_experience',path,a.voice_archive);packages.append(path)
    args=[sys.executable,str(ROOT/'scripts/build.py'),'--apks',str(a.base_apk.resolve()),
          '--ndk',str(ROOT/'tools/ndk'),'--android-jar',str(ROOT/'tools/platforms-android-35/android.jar'),
          '--r8',str(ROOT/'tools/build-tools-35.0.0/lib/d8.jar'),'--apksigner',str(ROOT/'tools/build-tools-35.0.0/lib/apksigner.jar'),
          '--zipalign',str(ROOT/'tools/build-tools-35.0.0/zipalign'),'--signing-key',str(a.signing_key.resolve()),
          '--signing-cert',str(a.signing_cert.resolve()),'--work-dir',str(a.work_dir.resolve()/'apk'),'--output',str(a.output.resolve())]
    for path in packages:args.extend(['--hatch',str(path)])
    subprocess.run(args,check=True)
if __name__=='__main__':main()
