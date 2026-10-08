from tankbuilder.unity_assets import Adapter,read_mb
from tankbuilder.weapon_assets import clone_he_pool
from pathlib import Path
import json,hashlib
import argparse
parser=argparse.ArgumentParser(description='Prepare original SU-85 and ZiS-3 HE projectile pools for Hatch 0.3')
parser.add_argument('source',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--report',type=Path,required=True)
args=parser.parse_args()
p=args.source;a=Adapter(p);report=[]
before={(o.assets_file.name,o.path_id):hashlib.sha256(o.get_raw_data()).hexdigest() for o in a.env.objects}
allowed=set()
for pid in [125836,137614]:
 launcher=a.sf.objects[pid];v=read_mb('Launcher',launcher.get_raw_data());assert len(v['shellApGos'])==2 and not v['shellHeGos']
 parent=a.sf.objects[v['thisTrf']['m_PathID']];allowed.update([('resources.assets',pid),('resources.assets',parent.path_id)])
 refs=clone_he_pool(a,launcher,parent,prefix='Hatch03_HE_'+str(pid));report.append({'launcher':pid,'he_count':len(refs)})
output=args.output;bundle=next(x for x in a.env.files.values() if hasattr(x,'save_fs'));output.write_bytes(bundle.save(packer='lz4'))
b=Adapter(output)
for entry in report:assert len(read_mb('Launcher',b.sf.objects[entry['launcher']].get_raw_data())['shellHeGos'])==2
changed=[key for key,h in before.items() if hashlib.sha256(b.files[key[0]].objects[key[1]].get_raw_data()).hexdigest()!=h]
assert set(changed)==allowed,changed
args.report.write_text(json.dumps(dict(pools=report,changed_original_objects=changed,added_objects=len(a.created)),indent=2));print(report,changed)
