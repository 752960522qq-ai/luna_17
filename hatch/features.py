"""Pack data-only gameplay extensions, independently of APK assembly."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from .package import validate

def pack_features(directory, output):
    directory, output = Path(directory), Path(output)
    doc = json.loads((directory/'hatch.json').read_text(encoding='utf-8'))
    payload = (directory/'features.json').read_bytes()
    if len(payload)>65536 or not isinstance(json.loads(payload),dict):
        raise ValueError('Invalid gameplay configuration')
    doc.update(features_bytes=len(payload),features_sha256=hashlib.sha256(payload).hexdigest())
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('hatch.json',json.dumps(doc,ensure_ascii=False,indent=2))
            archive.writestr('features.json',payload)
        validate(temporary)
        temporary.replace(output)
    finally:temporary.unlink(missing_ok=True)
    return doc

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(pack_features(args.directory,args.output),ensure_ascii=False,indent=2))
