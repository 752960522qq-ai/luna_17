"""Migrate old F archives to the same loader contract as the working Luchs."""
import hashlib, json, math, zipfile
from hatch.pack import CFG

ID = "Panzer_II_Ausf_F"
def update(src, dst):
    with zipfile.ZipFile(src) as base:
        h=json.loads(base.read("hatch.json")); w=json.loads(base.read("weapon.json"))
        m=h["magazine"]; assert h["id"]==ID and m==w["magazine"]==dict(capacity=10,shotInterval=.4,reloadTime=4.85)
        b=bytearray(base.read("runtime.bin")); cfg=list(CFG.unpack_from(b,24))
        assert any(abs(cfg[7]+cfg[35]-t)<1e-5 for t in (m["shotInterval"],m["reloadTime"]))
        cfg[7]=math.ceil(m["reloadTime"]);cfg[35]=m["reloadTime"]-cfg[7];CFG.pack_into(b,24,*cfg)
        h.pop("fire_controller",None);w.pop("fireController",None)
        h.update(continuous_fire=True,runtime_sha256=hashlib.sha256(b).hexdigest())
        w["continuousFire"]=True
        out={"runtime.bin":bytes(b),"hatch.json":json.dumps(h,ensure_ascii=False,indent=2).encode(),
             "weapon.json":json.dumps(w,ensure_ascii=False,indent=2).encode()}
        with zipfile.ZipFile(dst,"w") as z:
            for i in base.infolist(): z.writestr(i,out[i.filename] if i.filename in out else base.read(i.filename))
