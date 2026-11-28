"""Package a field/HUD/vehicle refit on the last cumulative build; never replace the game engine."""
import argparse,hashlib,io,json,subprocess,zipfile
from pathlib import Path
from update_campaign_loader import build_updates,repack_apk,repack_kit,verify_apk,CERT
from assemble_campaign_apk import CAT,CORE,DATA,NATIVE

def sha(b):return hashlib.sha256(b).hexdigest()
def write(o):return json.dumps(o,ensure_ascii=False,indent=2).encode()

def build(a):
    out=a.out;out.mkdir(parents=True,exist_ok=True);work=a.work;work.mkdir(parents=True,exist_ok=True)
    asset=a.assets
    report=json.loads((asset/"verification.json").read_bytes());assert report["status"]=="passed" and len(report["ai_nameplates"])==11
    updates=build_updates(work,a.apk,a.android_jar,a.r8)
    subprocess.run([a.clang,"-std=c11","-O2","-shared","-fPIC","-Wall","-Wextra","-Werror","-Wl,-z,max-page-size=16384,-z,defs,-soname,libhatchcampaign.so",Path(__file__).resolve().parents[1]/"campaign-runtime/campaign.c","-ldl","-lm","-o",work/"libhatchcampaign.so"],check=True)
    updates[NATIVE]=(work/"libhatchcampaign.so").read_bytes()
    catalog=json.loads(updates[CAT])
    with zipfile.ZipFile(a.apk) as src:
        for path in (a.t26,a.pz2):
            name=path.stem;entry="assets/Hatch/mods/"+path.name
            record,=[r for r in catalog["mods"] if r["id"]==name]
            prev=sha(src.read(entry));assert prev==record["sha256"]
            new=path.read_bytes()
            with zipfile.ZipFile(io.BytesIO(new)) as z:
                h=json.loads(z.read("hatch.json"));assert h["id"]==name and sha(z.read("runtime.bin"))==h["runtime_sha256"] and z.testzip() is None
            record.update(sha256=sha(new),size=len(new),supersedes_sha256=sorted(set(record.get("supersedes_sha256",[]))|{prev}))
            updates[entry]=new
    updates[CAT]=write(catalog)
    extra={n:(asset/n).read_bytes() for n in ("integration.json","mission.json","verification.json","Barbarossa-01.overlay")}
    extra["AI/Hatch-Enemy-AI-index.json"]=(asset/"ai-index.json").read_bytes()
    data=(asset/"data.unity3d").read_bytes()
    spec=json.loads(extra["integration.json"]);assert sha(data)==spec["result_sha256"] and sha(extra[spec["overlay_file"]])==spec["overlay_sha256"]
    unsigned=work/"unsigned.apk";signed=out/"Hatch-0.4-Barbarossa-Complete.apk"
    apk_updates={**updates,DATA:data}
    print("assembling APK",flush=True);repack_apk(a.apk,unsigned,apk_updates)
    if sha(a.cert.read_bytes())!=CERT:raise ValueError("Wrong project certificate")
    tool=["java","-cp",a.apksigner,"com.android.apksigner.ApkSignerTool"]
    subprocess.run([*tool,"sign","--key",a.key,"--cert",a.cert,"--min-sdk-version","28","--v1-signing-enabled","false","--v2-signing-enabled","true","--v3-signing-enabled","true","--v4-signing-enabled","false","--alignment-preserved","true","--out",signed,unsigned],check=True)
    ver=subprocess.check_output([*tool,"verify","--verbose","--print-certs",signed],text=True)
    v2=subprocess.check_output([*tool,"verify","--verbose","--min-sdk-version","24","--max-sdk-version","27",signed],text=True)
    assert "certificate SHA-256 digest: "+CERT in ver and "Verified using v2 scheme (APK Signature Scheme v2): true" in v2 and "Verified using v3 scheme (APK Signature Scheme v3): true" in ver
    print("verifying APK contents",flush=True);verify_apk(a.apk,signed,apk_updates)
    print("assembling mission kit",flush=True);repack_kit(a.kit,out/"Barbarossa-01-Gates-of-Hell.zip",updates|extra)
    print("signed APK and kit passed",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("apk","kit","work","assets","out","t26","pz2","android-jar","r8","clang","apksigner","key","cert"):
        p.add_argument("--"+k,type=Path,required=True)
    build(p.parse_args())
