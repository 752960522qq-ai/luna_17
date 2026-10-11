"""Replace selected bundled Hatch packages, update catalog, align, and sign APK v2."""
import argparse,datetime,hashlib,io,json,struct,zipfile
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.x509.oid import NameOID

def lp(b):return struct.pack('<I',len(b))+b

def digest(sections):
 chunks=[]
 for section in sections:
  for o in range(0,len(section),1048576):
   c=section[o:o+1048576];chunks.append(hashlib.sha256(b'\xa5'+struct.pack('<I',len(c))+c).digest())
 return hashlib.sha256(b'\x5a'+struct.pack('<I',len(chunks))+b''.join(chunks)).digest()

def eocd(data):
 p=data.rfind(b'PK\x05\x06');assert p>=0 and p+22+struct.unpack_from('<H',data,p+20)[0]==len(data)
 return p,struct.unpack_from('<I',data,p+16)[0]

def sign(data,key,cert):
 end,cd=eocd(data);dg=digest([data[:cd],data[cd:end],data[end:]])
 record=lp(struct.pack('<I',0x0103)+lp(dg));signed=lp(record)+lp(lp(cert))+lp(b'')
 sig=key.sign(signed,padding.PKCS1v15(),hashes.SHA256());key.public_key().verify(sig,signed,padding.PKCS1v15(),hashes.SHA256())
 signer=lp(signed)+lp(lp(struct.pack('<I',0x0103)+lp(sig)))+lp(key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo))
 value=lp(lp(signer));pair=struct.pack('<Q',4+len(value))+struct.pack('<I',0x7109871a)+value
 size=len(pair)+24;block=struct.pack('<Q',size)+pair+struct.pack('<Q',size)+b'APK Sig Block 42'
 tail=bytearray(data[end:]);struct.pack_into('<I',tail,16,cd+len(block));result=data[:cd]+block+data[cd:end]+tail
 # Independently recompute digest from final signed ZIP locations.
 e,c=eocd(result);bs=struct.unpack_from('<Q',result,c-24)[0];start=c-bs-8;normalized=bytearray(result[e:]);struct.pack_into('<I',normalized,16,start)
 assert result[c-16:c]==b'APK Sig Block 42' and digest([result[:start],result[c:e],normalized])==dg
 x509.load_der_x509_certificate(cert).public_key().verify(sig,signed,padding.PKCS1v15(),hashes.SHA256())
 return result,hashlib.sha256(cert).hexdigest()

def repack(base,mods,out,keypath,certpath):
 replacements={}
 for p in mods:
  with zipfile.ZipFile(p) as z:
   assert z.testzip() is None;meta=json.loads(z.read('hatch.json'));runtime=z.read('runtime.bin');assert hashlib.sha256(runtime).hexdigest()==meta['runtime_sha256'];assert len(runtime)==meta['runtime_bytes']
  replacements['assets/Hatch/mods/'+meta['id']+'.hatch']=p.read_bytes()
 with zipfile.ZipFile(base) as source:
  catalog=json.loads(source.read('assets/Hatch/catalog.json'))
  for item in catalog['mods']:
   path='assets/Hatch/mods/'+item['id']+'.hatch'
   if path in replacements:item['sha256']=hashlib.sha256(replacements[path]).hexdigest();item['size']=len(replacements[path])
  replacements['assets/Hatch/catalog.json']=json.dumps(catalog,ensure_ascii=False,indent=2).encode()
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w') as dest:
   for entry in source.infolist():
    if entry.filename.upper().startswith('META-INF/') and entry.filename.upper().endswith(('.RSA','.DSA','.EC','.SF','MANIFEST.MF')):continue
    data=replacements.get(entry.filename,source.read(entry.filename));new=zipfile.ZipInfo(entry.filename,entry.date_time);new.compress_type=entry.compress_type;new.external_attr=entry.external_attr
    alignment=16384 if entry.filename.endswith('.so') and new.compress_type==0 else 4 if new.compress_type==0 else 1
    if alignment>1:
     pad=(-(buffer.tell()+30+len(new.filename.encode())+4))%alignment;new.extra=struct.pack('<HH',0xd935,pad)+b'\0'*pad
    dest.writestr(new,data)
 if keypath.exists():
  key=serialization.load_pem_private_key(keypath.read_bytes(),None);cert=certpath.read_bytes()
 else:
  raise FileNotFoundError('Fixed project signing key is required; do not generate a new key')
 result,certsha=sign(buffer.getvalue(),key,cert)
 if certsha!='734e17a0550eb23e3e5975dc90a7932eb513ee0e62ad4804b436cacd5f15413e':raise ValueError('Wrong project signing certificate')
 out.write_bytes(result)
 with zipfile.ZipFile(out) as final,zipfile.ZipFile(base) as source:
  assert final.testzip() is None
  changed=[]
  for entry in source.infolist():
   if entry.filename in replacements:assert final.read(entry.filename)==replacements[entry.filename];changed.append(entry.filename)
   else:assert final.read(entry.filename)==source.read(entry.filename)
  for entry in final.infolist():
   if entry.filename.endswith('.so') and entry.compress_type==0:
    offset=entry.header_offset;namelen,extra=struct.unpack_from('<HH',result,offset+26);assert (offset+30+namelen+extra)%16384==0
 report={'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'apk_sha256':hashlib.sha256(result).hexdigest(),'apk_bytes':len(result),'changed_entries':changed,'catalog':catalog,'signature_scheme':'v2 RSA PKCS1 SHA256','certificate_sha256':certsha,'signing_key_changed':True,'zip_crc_check':'passed','unchanged_entries_byte_comparison':'passed','elf_zip_alignment':'16384 bytes','signature_and_content_digest':'passed','android_device_test':'not performed'}
 out.with_suffix('.verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='catalog'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--mod',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--key',type=Path,required=True);p.add_argument('--cert',type=Path,required=True);a=p.parse_args();repack(a.base,a.mod,a.output,a.key,a.cert)
