"""Restore the two-mission game resources with Python 3; the input APK is read-only."""
import argparse,hashlib,json,os,shutil,tempfile,zipfile
from pathlib import Path
from contextlib import ExitStack
DATA='assets/bin/Data/data.unity3d'
FILES=('classes5.dex','lib/arm64-v8a/libhatchcampaign.so','assets/bin/Data/StormWeather.resource','assets/Hatch/catalog.json','assets/Hatch/mods/Panzer_III_Ausf_F.hatch','assets/Hatch/mods/T28.hatch','AI/Hatch-Enemy-AI-index.json')
def checked(condition,why):
    if not condition:raise ValueError(why)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def restore(base,kit,out):
    out=out.resolve()
    checked(not out.exists() or out.is_dir() and not any(out.iterdir()),'Output directory must be new or empty')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as work,zipfile.ZipFile(kit) as z:
        work=Path(work);src=work/'base-resource';overlay=work/'overlay'
        t=json.loads(z.read('integration.json'));checked(sha(base)==t['base_apk_sha256'],'Base APK SHA-256 differs; use the specified cumulative build')
        with zipfile.ZipFile(base) as game,game.open(DATA) as f,src.open('wb') as d:shutil.copyfileobj(f,d,1<<20)
        checked(sha(src)==t['base_sha256'],'Original game resource does not match')
        with z.open(t['overlay_file']) as f,overlay.open('wb') as d:shutil.copyfileobj(f,d,1<<20)
        checked(sha(overlay)==t['overlay_sha256'],'Overlay checksum mismatch')
        prefix,a,b=t['header_bytes'],t['retain_start'],t['retain_end']
        checked(0<prefix<overlay.stat().st_size and 0<=a<b<=src.stat().st_size,'Invalid bundle boundaries')
        staged=work/'staged';target=staged/DATA;target.parent.mkdir(parents=True)
        with src.open('rb') as f,overlay.open('rb') as o,target.open('wb') as d:
            d.write(o.read(prefix));f.seek(a);remaining=b-a
            while remaining:
                q=f.read(min(1<<20,remaining));checked(q,'Unexpected end of resource');d.write(q);remaining-=len(q)
            shutil.copyfileobj(o,d,1<<20)
        checked(sha(target)==t['result_sha256'],'Restored scene bundle checksum mismatch')
        checked(set(t['staged_files'])==set(FILES),'The staged payload is incomplete')
        for name in FILES:
            dest=staged/name;dest.parent.mkdir(parents=True,exist_ok=True)
            with z.open(name) as f,dest.open('wb') as d:shutil.copyfileobj(f,d,1<<20)
            checked(sha(dest)==t['staged_files'][name],name+' checksum mismatch')
        os.replace(staged,out)
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('base','kit','out'):p.add_argument('--'+k,required=True,type=Path)
    d=restore(**vars(p.parse_args()));print('Verified and restored campaign resources:',d)
