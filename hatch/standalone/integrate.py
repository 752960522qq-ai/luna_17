#!/usr/bin/env python3
"""Hatch 0.1 standalone installer. Python 3.10+; Java 17+ for signing."""
import argparse,contextlib,hashlib,io,json,os,re,secrets,shutil,struct,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from axml import patch_manifest
MAX_PACK=256*1024*1024

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def entry_digest(z,name):
 h=hashlib.sha256()
 with z.open(name) as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def validate_pack(path):
 if path.stat().st_size<=0 or path.stat().st_size>MAX_PACK:raise ValueError('Tank package size limit: '+path.name)
 with zipfile.ZipFile(path) as z:
  infos=z.infolist();names=[i.filename for i in infos]
  if len(names)>16 or len(set(names))!=len(names) or any(i.is_dir() or '/' in i.filename or '\\' in i.filename or '..' in i.filename or i.file_size>MAX_PACK for i in infos):raise ValueError('Unsafe/duplicate package entries: '+path.name)
  if 'hatch.json' not in names or 'runtime.bin' not in names:raise ValueError('Use .hatch packages; convert raw .tankpack first')
  if z.getinfo('hatch.json').file_size>16384:raise ValueError('Oversized tank manifest')
  m=json.loads(z.read('hatch.json'))
  if (m.get('format'),m.get('loader'),m.get('loader_version'),m.get('game_version'),m.get('abi'))!=(1,'Hatch','0.1','5.1.0','arm64-v8a'):raise ValueError('Incompatible tank package: '+path.name)
  if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',m.get('id','')):raise ValueError('Invalid tank ID')
  size=z.getinfo('runtime.bin').file_size
  if size<616 or size!=m.get('runtime_bytes') or size>MAX_PACK or entry_digest(z,'runtime.bin')!=m.get('runtime_sha256'):raise ValueError('Runtime content checksum/size mismatch')
  with z.open('runtime.bin') as f:head=f.read(88)
  magic,version,total,nodes,images=struct.unpack_from('<8sIIII',head)
  if magic!=b'HATCH01\0' or version!=1 or total!=size or not 4<=nodes<=2048 or images>128 or head[24:88].split(b'\0')[0].decode('ascii')!=m['id']:raise ValueError('Runtime header/identity mismatch')
 return {'id':m['id'],'name':m['name'],'sha256':digest(path),'size':path.stat().st_size,'runtime_bytes':size,'path':path}
def collect_mods(directory):
 result=[];ids=set();total=0
 for p in sorted(directory.glob('*.hatch')):
  m=validate_pack(p)
  if m['id'] in ids:raise ValueError('Duplicate tank ID: '+m['id'])
  ids.add(m['id']);total+=m['runtime_bytes'];result.append(m)
 if len(result)>16 or total>512*1024*1024:raise ValueError('Tank count/total runtime memory limit')
 return result

def write_aligned(out,name,data,compression=zipfile.ZIP_DEFLATED):
 i=zipfile.ZipInfo(name,(2026,10,6,0,0,0));i.compress_type=compression;i.external_attr=0o644<<16
 if compression==zipfile.ZIP_STORED:
  alignment=16384 if name.endswith('.so') else 4
  start=out.fp.tell()+30+len(name.encode('utf-8'))
  if start%alignment:
   pad=-(start+6)%alignment;i.extra=struct.pack('<HHH',0xd935,pad+2,alignment)+b'\0'*pad
 out.writestr(i,data,compresslevel=6)
def check_alignment(path):
 with zipfile.ZipFile(path) as z,Path(path).open('rb') as f:
  for i in z.infolist():
   if i.compress_type!=zipfile.ZIP_STORED:continue
   f.seek(i.header_offset);h=f.read(30);n,x=struct.unpack_from('<HH',h,26)
   align=16384 if i.filename.endswith('.so') else 4
   if (i.header_offset+30+n+x)%align:raise ValueError('ZIP alignment error: '+i.filename)

def strip_signature(name):
 return name=='stamp-cert-sha256' or name=='META-INF/MANIFEST.MF' or bool(re.fullmatch(r'META-INF/[^/]+\.(?:RSA|DSA|EC|SF)',name,re.I))
@contextlib.contextmanager
def game_archives(path):
 with contextlib.ExitStack() as stack:
  outer=stack.enter_context(zipfile.ZipFile(path))
  if 'AndroidManifest.xml' in outer.namelist():yield outer,[];return
  if 'base.apk' not in outer.namelist():raise ValueError('Input must be a clean APK or APKS with base.apk')
  base=stack.enter_context(zipfile.ZipFile(io.BytesIO(outer.read('base.apk'))));splits=[]
  for n in outer.namelist():
   if n.endswith('.apk') and n!='base.apk':splits.append(stack.enter_context(zipfile.ZipFile(io.BytesIO(outer.read(n)))))
  yield base,splits

def assemble(input_file,output,mods):
 config=json.loads((ROOT/'module.json').read_text(encoding='utf-8'))
 for relative,expected in config['payload_sha256'].items():
  if digest(ROOT/relative)!=expected:raise ValueError('Loader payload modified: '+relative)
 profile=json.loads((ROOT/'adapters/attack-on-tank-5.1.0.json').read_text(encoding='utf-8'))
 with game_archives(input_file) as (base,splits):
  if 'lib/arm64-v8a/libaotmod.so' in base.namelist():raise ValueError('Input already contains Hatch; use the clean original')
  if entry_digest(base,'assets/bin/Data/Managed/Metadata/global-metadata.dat')!=profile['metadata_sha256']:raise ValueError('Unsupported game metadata: requires 5.1.0 ARM64')
  if profile.get('unity_data_sha256') and entry_digest(base,'assets/bin/Data/data.unity3d')!=profile['unity_data_sha256']:raise ValueError('Game resources differ from reviewed original')
  native={}
  for z in [base]+splits:
   for i in z.infolist():
    if i.filename.startswith('lib/arm64-v8a/') and not i.is_dir():
     if i.filename in native and entry_digest(z,i.filename)!=entry_digest(native[i.filename],i.filename):raise ValueError('Conflicting ARM64 split')
     native[i.filename]=z
  key='lib/arm64-v8a/libil2cpp.so'
  if key not in native or entry_digest(native[key],key)!=profile['libil2cpp_sha256']:raise ValueError('Unsupported/missing ARM64 game library')
  manifest=patch_manifest(base.read('AndroidManifest.xml'))
  dex=[(int(m.group(1) or 1),i.filename) for i in base.infolist() if (m:=re.fullmatch(r'classes(\d*)\.dex',i.filename))]
  if not dex:raise ValueError('Original game DEX missing')
  if any(b'Lcom/luna17/aot/' in base.read(n) for _,n in dex):raise ValueError('Input contains an earlier modifier; use a clean original')
  added=f'classes{max(n for n,_ in dex)+1}.dex';preserved=0
  catalog={'format':1,'loader':'Hatch','version':'0.1','mods':[{k:v for k,v in m.items() if k in ['id','name','sha256','size']} for m in mods]}
  with zipfile.ZipFile(output,'w',allowZip64=False) as out:
   written=set()
   for i in base.infolist():
    name=i.filename
    if strip_signature(name):continue
    if name.startswith('assets/Hatch/'):raise ValueError('Input contains an earlier Hatch asset folder')
    write_aligned(out,name,manifest if name=='AndroidManifest.xml' else base.read(name),i.compress_type);written.add(name)
    if name!='AndroidManifest.xml':preserved+=1
   for name,z in native.items():
    if name not in written:write_aligned(out,name,z.read(name),zipfile.ZIP_DEFLATED);written.add(name)
   write_aligned(out,added,(ROOT/'loader/hatch.dex').read_bytes())
   write_aligned(out,'lib/arm64-v8a/libaotmod.so',(ROOT/'loader/libaotmod.so').read_bytes(),zipfile.ZIP_DEFLATED)
   write_aligned(out,'assets/Hatch/module.json',(ROOT/'module.json').read_bytes())
   write_aligned(out,'assets/Hatch/catalog.json',json.dumps(catalog,ensure_ascii=False,indent=2).encode())
   for m in mods:write_aligned(out,'assets/Hatch/mods/'+m['id']+'.hatch',m['path'].read_bytes(),zipfile.ZIP_STORED)
  check_alignment(output)
  return {'loader':'Hatch','version':'0.1','package':profile['package'],'game_version':'5.1.0','abi':'arm64-v8a','added_dex':added,'preserved_base_entries':preserved,'builtin_tanks':[m['id'] for m in mods],'zip_16k_alignment':True,'android_device_test':'not performed'}

def run(*args):subprocess.run([str(a) for a in args],check=True)
def sign(unsigned,output,args,signing_root):
 java=shutil.which('java');keytool=shutil.which('keytool')
 if not java or not keytool:raise ValueError('Install JDK 17+ or choose --unsigned')
 signer=ROOT/'tools/apksigner.jar';ks=args.keystore;password=args.password_file
 if ks:
  if password is None or not password.is_file():raise ValueError('--keystore requires --password-file')
 else:
  if password:raise ValueError('--password-file requires --keystore')
  directory=signing_root/'Hatch-signing';directory.mkdir(exist_ok=True);ks=directory/'hatch-development.jks';password=directory/'password.txt'
  if not ks.exists():
   password.write_text(secrets.token_urlsafe(32)+'\n');os.chmod(password,0o600)
   run(keytool,'-genkeypair','-keystore',ks,'-alias',args.alias,'-storepass:file',password,'-keypass:file',password,'-keyalg','RSA','-keysize','3072','-sigalg','SHA256withRSA','-validity','3650','-dname','CN=Hatch Development, OU=Offline Loader, O=Hatch')
  if not password.is_file():raise ValueError('Signing password is missing; preserve your local signing directory')
 run(java,'-jar',signer,'sign','--ks',ks,'--ks-key-alias',args.alias,'--ks-pass','file:'+str(password),'--min-sdk-version','28','--v1-signing-enabled','false','--v2-signing-enabled','true','--v3-signing-enabled','true','--v4-signing-enabled','false','--alignment-preserved','true','--out',output,unsigned)
 run(java,'-jar',signer,'verify','--verbose',output)

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--mods',type=Path,default=ROOT/'mods');p.add_argument('--unsigned',action='store_true');p.add_argument('--keystore',type=Path);p.add_argument('--password-file',type=Path);p.add_argument('--alias',default='hatch');args=p.parse_args(argv)
 input_file=args.input.resolve();output=args.output.resolve()
 if input_file==output:raise ValueError('Output must not overwrite the original input')
 if not args.mods.is_dir():raise ValueError('Mod directory not found')
 mods=collect_mods(args.mods);output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='hatch-',dir=output.parent) as temp:
  directory=Path(temp);unsigned=directory/'unsigned.apk';report=assemble(input_file,unsigned,mods);candidate=directory/'signed.apk'
  if args.unsigned:shutil.copyfile(unsigned,candidate)
  else:sign(unsigned,candidate,args,output.parent)
  check_alignment(candidate);report.update(signed=not args.unsigned,size_bytes=candidate.stat().st_size,sha256=digest(candidate));candidate.replace(output)
 output.with_suffix('.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Created:',output)
 return report
if __name__=='__main__':
 try:main()
 except (ValueError,OSError,KeyError,zipfile.BadZipFile,subprocess.CalledProcessError) as e:print('Hatch integration failed:',e,file=sys.stderr);sys.exit(2)
