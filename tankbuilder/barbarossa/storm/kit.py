"""Assemble and independently stage-test the cumulative field kit, without producing an APK."""
import argparse,json,zipfile
from pathlib import Path
from .restore import FILES,DATA,sha
from ..mission.release import dumps,digest

def assemble(out,apk,staged,compiled):
    here=Path(__file__).parent
    dest={'classes5.dex':compiled/'main-dex/classes.dex','lib/arm64-v8a/libhatchcampaign.so':compiled/'libhatchcampaign.so','assets/bin/Data/StormWeather.resource':out/'StormWeather.resource'}
    for n in FILES:
        if n not in dest:dest[n]=staged/n
    catalog=json.loads(dest['assets/Hatch/catalog.json'].read_bytes());report=json.loads((out/'verification.json').read_bytes());spec=json.loads((out/'integration.json').read_bytes())
    assert report['status']=='passed' and report['matchesResourceSHA256']==sha(out/'data.unity3d')==spec['result_sha256']
    assert set(dest)==set(FILES)
    with zipfile.ZipFile(apk) as z:
        for mod in (catalog if isinstance(catalog,list) else catalog['mods']):
            name='assets/Hatch/mods/'+mod['id']+'.hatch'
            assert mod['sha256']==(sha(dest[name]) if name in dest else digest(z.read(name))),name
    spec.update(format=1,base_apk_name=apk.name,base_apk_sha256=sha(apk),staged_files={k:sha(v) for k,v in dest.items()})
    extra={'README_zh.md':here/'KIT.md','apply_overlay.py':here/'restore.py',spec['overlay_file']:out/spec['overlay_file'],'campaign.json':out/'campaign.json','verification.json':out/'verification.json','previews/Barbarossa-02-Deployment.png':out/'Barbarossa-02-Deployment.png','previews/Storm-Audio.mp3':out/'Storm-Audio.mp3'}
    target=out/'Barbarossa-01-02-Storm.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        z.writestr('integration.json',dumps(spec))
        for n,p in {**dest,**extra}.items():z.write(p,n)
    print(target,sha(target),target.stat().st_size)
    return target

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    for k in ('out','apk','staged','compiled'):a.add_argument('--'+k,type=Path,required=True)
    assemble(**vars(a.parse_args()))
