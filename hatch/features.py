"""Pack data-only gameplay extensions, independently of APK assembly."""
import argparse
import hashlib
import io
import re
import json
import zipfile
from pathlib import Path
from .package import validate

def pack_features(directory, output, voice_archive=None):
    directory, output = Path(directory), Path(output)
    doc = json.loads((directory/'hatch.json').read_text(encoding='utf-8'))
    payload = (directory/'features.json').read_bytes()
    if len(payload)>65536 or not isinstance(json.loads(payload),dict):
        raise ValueError('Invalid gameplay configuration')
    voice=None
    configuration=json.loads(payload)
    if 'crew' in configuration:
        if voice_archive is None:raise ValueError('Crew experience requires the uploaded voice archive')
        voice=Path(voice_archive).read_bytes()
        source=json.loads((directory/'audio-source.json').read_text(encoding='utf-8'))
        if hashlib.sha256(voice).hexdigest()!=source['sha256']:raise ValueError('Voice archive differs from the uploaded source')
        if source.get('layout')=='event-folders':
            flattened=io.BytesIO();seen=set()
            with zipfile.ZipFile(io.BytesIO(voice)) as original, zipfile.ZipFile(flattened,'w',zipfile.ZIP_DEFLATED) as runtime:
                total=0
                for entry in original.infolist():
                    path=Path(entry.filename)
                    if path.is_absolute() or '..' in path.parts or '\\' in entry.filename:raise ValueError('Unsafe voice source path')
                    if entry.is_dir():continue
                    name=path.name
                    total+=entry.file_size
                    if name in seen or not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}\.wav',name) or '..' in name or not 44<=entry.file_size<=5*1024*1024 or total>256*1024*1024:raise ValueError('Invalid voice source clip')
                    seen.add(name);runtime.writestr(name,original.read(entry))
            voice=flattened.getvalue()
            doc['voices_source_sha256']=source['sha256']
        doc.update(voices_bytes=len(voice),voices_sha256=hashlib.sha256(voice).hexdigest())
    doc.update(features_bytes=len(payload),features_sha256=hashlib.sha256(payload).hexdigest())
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('hatch.json',json.dumps(doc,ensure_ascii=False,indent=2))
            archive.writestr('features.json',payload)
            if voice is not None:archive.writestr('voices.zip',voice)
        validate(temporary)
        temporary.replace(output)
    finally:temporary.unlink(missing_ok=True)
    return doc

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--voice-archive',type=Path)
    args=parser.parse_args()
    print(json.dumps(pack_features(args.directory,args.output,args.voice_archive),ensure_ascii=False,indent=2))
