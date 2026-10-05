from pathlib import Path
from elftools.elf.elffile import ELFFile
import struct, json, re, argparse
parser=argparse.ArgumentParser(description='Decode the seven protected metadata sections in Attack on Tank 5.1.0 ARM64.')
parser.add_argument('--metadata',type=Path,required=True)
parser.add_argument('--libil2cpp',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
raw=args.metadata.read_bytes()
with args.libil2cpp.open('rb') as f:
    elf=ELFFile(f)
    for segment in elf.iter_segments():
        if segment['p_vaddr']<=0xd49898<segment['p_vaddr']+segment['p_filesz']:
            table=segment.data()[0xd49898-segment['p_vaddr']:0xd49898-segment['p_vaddr']+256]
def crypt(data,state):
    out=bytearray(data); mask=(1<<64)-1
    for i,v in enumerate(out):
        state=(state^(state<<13))&mask
        state=(state^(state>>7))&mask
        state=(state^(state<<17))&mask
        out[i]=v^table[(state^(state>>8)^(state>>16)^(state>>24))&255]
    return bytes(out)
header=crypt(raw[:0x324],0x5bb6c71b5ea5f330)
out=args.output;out.mkdir(parents=True,exist_ok=True)
(out/'header.dat').write_bytes(header)
sections=[(0x2ac,0x2b4,-0x40c,0x3a3cc07bba3248ea),(0x1a4,0x1ac,-0x1464,0xdcab4da51d5f6539),(0x1f8,0x200,-0x858,0xbb1a123cbe65f597),(0x150,0x158,0x1134,0x1d8ca196d1ffc71e),(0x18,0x20,-0x1a7c,0x8f7f47f51032918c),(0x180,0x188,0x1ce0,0x1e38e71fe1f5c368),(0x1c8,0x1d0,-0x9c8,0x3a979521731c999d)]
print('Header',header[:32].hex())
manifest=[]
for i,(size_at,off_at,adjust,seed) in enumerate(sections):
    size=struct.unpack_from('<I',header,size_at)[0];offset=struct.unpack_from('<I',header,off_at)[0]+adjust
    assert 0<=offset<=len(raw) and 0<=size<=len(raw)-offset,(i,hex(offset),size)
    data=crypt(raw[offset:offset+size],seed)
    (out/f'section{i}.dat').write_bytes(data)
    printable=sum(32<=v<127 or v in (0,10,13) for v in data)/len(data)
    print(i,'offset',hex(offset),'size',hex(size),'printable',round(printable,2),'first',repr(data[:140]))
    hits=[(n.decode(),hex(m.start())) for n in [b'UnitDamage',b'MainGun',b'TankGenManager'] for m in re.finditer(n,data)]
    print('hits',hits)
    manifest.append(dict(index=i,offset=offset,size=size,header_size_offset=size_at,header_offset_offset=off_at,offset_adjust=adjust,seed=seed))
(out/'sections.json').write_text(json.dumps(manifest,indent=2))
