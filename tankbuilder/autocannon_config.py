"""The archive keeps the full magazine spec; the stock loader handles the interval between rounds."""
import hashlib, json, math, zipfile
from hatch.pack import CFG

ID = "Panzer_II_Ausf_F"
MODE = "unity-button-magazine-v1"

def update(src, dst):
    with zipfile.ZipFile(src) as base:
        h=json.loads(base.read("hatch.json"));w=json.loads(base.read("weapon.json"))
        m=h["magazine"]; assert h["id"]==ID and m==w["magazine"] and m==dict(capacity=10,shotInterval=.4,reloadTime=4.85)
        b=bytearray(base.read("runtime.bin")); cfg=list(CFG.unpack_from(b,24))
        assert cfg[7]+cfg[35] == w["reload"] or abs(cfg[7]+cfg[35]-w["reload"])<1e-5
        cfg[7]=math.ceil(m["shotInterval"]);cfg[35]=m["shotInterval"]-cfg[7];CFG.pack_into(b,24,*cfg)
        h.update(fire_controller=MODE,runtime_sha256=hashlib.sha256(b).hexdigest())
        out={"runtime.bin":bytes(b),"hatch.json":json.dumps(h,ensure_ascii=False,indent=2).encode()}
        with zipfile.ZipFile(dst,"w") as z:
            for i in base.infolist():z.writestr(i,out[i.filename] if i.filename in out else base.read(i.filename))
