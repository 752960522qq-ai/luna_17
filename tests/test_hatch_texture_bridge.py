"""Execute the shipped byte[] LoadImage wrapper with all real mod PNGs.
The GPU/internal decoder is replaced by Pillow: this checks original ABI
marshaling and image validity, not Android GPU behavior.
"""
import argparse, hashlib, io, json, struct, zipfile
from pathlib import Path
from PIL import Image
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn import arm64_const as R
from elftools.elf.elffile import ELFFile

def test(module,library,mod):
 with zipfile.ZipFile(mod) as z:blob=z.read('runtime.bin')
 nodes,images=struct.unpack_from('<II',blob,16);at=616
 for _ in range(nodes):v,i=struct.unpack_from('<II',blob,at+48);at+=176+v*32+i*4
 pics=[]
 for _ in range(images):size=struct.unpack_from('<I',blob,at)[0];at+=4;pics.append(blob[at:at+size]);at+=size
 assert at==len(blob)
 with open(library,'rb') as f:
  elf=ELFFile(f);segments=[(s['p_vaddr'],s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
 def read(a,n):return next(b[a-v:a-v+n] for v,b in segments if v<=a<v+len(b))
 # Token 0x06000002 in UnityEngine.ImageConversionModule.dll.
 wrapper=0x345f4f4;span=0x345f378
 code=read(wrapper,0x5c)
 assert code[0x34:0x40]==bytes.fromhex('821a40b98182009103000014'),'Byte[] conversion instructions changed'
 result=[]
 for idx,png in enumerate(pics):
  u=Uc(UC_ARCH_ARM64,UC_MODE_ARM);u.mem_map(0x3400000,0x70000);u.mem_map(0x3bd6000,0x1000);u.mem_map(0x40000000,0x2000000);u.mem_map(0x50000000,0x20000)
  u.mem_write(wrapper,code);u.mem_write(span,bytes.fromhex("c0035fd6"));u.mem_write(0x3bd61e9,b'\x01')
  arr=0x40000100;tex=0x40000040;halt=0x5001f000
  u.mem_write(arr+0x18,struct.pack('<Q',len(png)));u.mem_write(arr+0x20,png)
  def hook(uc,a,size,user):
   if a==span:
    assert uc.reg_read(R.UC_ARM64_REG_X0)==tex
    assert uc.reg_read(R.UC_ARM64_REG_X1)==arr+0x20
    assert uc.reg_read(R.UC_ARM64_REG_W2)==len(png)
    assert uc.reg_read(R.UC_ARM64_REG_W3)==0
    raw=bytes(uc.mem_read(uc.reg_read(R.UC_ARM64_REG_X1),uc.reg_read(R.UC_ARM64_REG_W2)))
    assert hashlib.sha256(raw).digest()==hashlib.sha256(png).digest()
    im=Image.open(io.BytesIO(raw));im.load();result.append({'image':idx,'size':im.size,'mode':im.mode})
    uc.reg_write(R.UC_ARM64_REG_X0,1);uc.reg_write(R.UC_ARM64_REG_PC,uc.reg_read(R.UC_ARM64_REG_LR))
   elif a==halt:uc.emu_stop()
  u.hook_add(UC_HOOK_CODE,hook);u.reg_write(R.UC_ARM64_REG_SP,0x50010000);u.reg_write(R.UC_ARM64_REG_X0,tex);u.reg_write(R.UC_ARM64_REG_X1,arr);u.reg_write(R.UC_ARM64_REG_LR,halt)
  u.emu_start(wrapper,halt,count=200)
  assert u.reg_read(R.UC_ARM64_REG_X0)==1
 source=Path(module).read_text();import re;assert re.search(r'"LoadImage"\s*,\s*2\s*,\s*load\s*,\s*textureklass',source)
 return {'images_tested':len(result),'original_byte_array_wrapper_executed':True,'pillow_decode_passed':True,'android_gpu_decoder_tested':False,'images':result}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--engine',type=Path,required=True);p.add_argument('--game-library',type=Path,required=True);p.add_argument('--mod',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 r=test(a.engine,a.game_library,a.mod);a.report.write_text(json.dumps(r,indent=2)+'\n');print('36 original ARM64 texture wrapper + PNG decode checks passed')

