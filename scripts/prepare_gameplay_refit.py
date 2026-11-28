"""Rebuild editable vehicles and both battle scenes from the last cumulative release."""
import argparse, json, zipfile
from pathlib import Path
from tankbuilder import t26_hull_hatch,autocannon_config
from tankbuilder.barbarossa.mission import refit,compact,check_gameplay
from tankbuilder.barbarossa.mission.release import Members,dumps
from tankbuilder.extra_campaign import file
def prepare(apk,kit,assets,out):
    assets.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    inp=assets/"previous";inp.mkdir(exist_ok=True)
    with zipfile.ZipFile(apk) as src:
        for ident,fn in (("T26",t26_hull_hatch.update),("Panzer_II_Ausf_F",autocannon_config.update)):
            n=ident+".hatch";(inp/n).write_bytes(src.read("assets/Hatch/mods/"+n));fn(inp/n,out/n)
    refit.assets(apk,kit,assets,{i:out/(i+".hatch") for i in ("T26","Panzer_II_Ausf_F")})
    refit.finish(apk,kit,assets);compact.compact(assets)
    raw=(assets/"data.unity3d").read_bytes();bundle=Members(raw)
    names={i:o.read_typetree(check_read=False)["m_ClassName"] for i,o in file(bundle.read("globalgamemanagers.assets")).objects.items() if o.type.name=="MonoScript"}
    report=json.loads((assets/"verification.json").read_bytes())
    report["t26_deck"]=check_gameplay.rig(inp/"T26.hatch",out/"T26.hatch")
    report["inline_ai_labels"]=check_gameplay.packaged(raw,json.loads((assets/"mission.json").read_bytes()),json.loads((assets/"ai-index.json").read_bytes()),names)
    (assets/"verification.json").write_bytes(dumps(report))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("apk","kit","assets","out"):p.add_argument("--"+k,type=Path,required=True)
    prepare(**vars(p.parse_args()))
