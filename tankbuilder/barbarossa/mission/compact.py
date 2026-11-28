"""Retain the original game blocks and re-encode only live extra resources, losslessly."""
import io, json, lzma, struct, sys
from pathlib import Path
import lz4.block
from UnityPy.helpers.CompressionHelper import decompress_lzma
from ..bundle import metadata
from .release import Members,dumps,digest

def encode(chunk):
    f=dict(id=lzma.FILTER_LZMA1,dict_size=1<<24,mode=lzma.MODE_NORMAL,mf=lzma.MF_BT4,nice_len=64,lc=3,lp=0,pb=2)
    data=b'\x5d'+struct.pack('<I',f['dict_size'])+lzma.compress(chunk,format=lzma.FORMAT_RAW,filters=[f])
    assert decompress_lzma(data)==chunk
    return data

def compact(work):
    spec=json.loads((work/'integration.json').read_bytes());prior=(work/'data.unity3d').read_bytes()
    pack=Members(prior);hdr,start,_,old,entries=metadata(prior); end=spec['retain_end']
    phys=start;plain=0;blocks=[];parts=[];members={}
    for row in old:
        if phys==end:break
        n,c,mode=row;phys+=c;plain+=n;blocks.append(row)
    assert phys==end
    origin=plain
    def append(raw,packed,mode):
        nonlocal plain
        if len(packed)>=len(raw):packed=raw;mode=0
        parts.append(packed);blocks.append((len(raw),len(packed),mode));plain+=len(raw)
    def snappy(chunk):
        append(chunk,lz4.block.compress(chunk,mode="high_compression",compression=9,store_size=False),3)
    for name,(at,n,flag) in sorted(entries.items(),key=lambda kv:kv[1][0]):
        if at+n<=origin:
            members[name]=(at,n,flag);continue
        assert at>=origin
        raw=pack.read(name)
        gap=(-plain)%16
        if gap:append(bytes(gap),bytes(gap),0)
        members[name]=(plain,len(raw),flag)
        # The original title, registry and common terrain still have small LZ4 blocks.
        if name in ('level0','level21','globalgamemanagers') or len(raw)<131072:
            for i in range(0,len(raw),131072):snappy(raw[i:i+131072])
        else:
            blocksize=(4 if name in ('level22','level23') else 16)<<20
            for i in range(0,len(raw),blocksize):
                chunk=raw[i:i+blocksize];append(chunk,encode(chunk),1)
        print("compacted",name,flush=True)
    d=io.BytesIO();d.write(bytes(16)+struct.pack('>I',len(blocks)))
    for row in blocks:d.write(struct.pack('>IIH',*row))
    d.write(struct.pack('>I',len(entries)))
    for name in entries:
        d.write(struct.pack('>qqI',*members[name])+name.encode()+b'\0')
    bare=d.getvalue();directory=lz4.block.compress(bare,store_size=False)
    head=bytearray(prior[:start]);sz=end+sum(map(len,parts))+len(directory)
    struct.pack_into('>QIII',head,hdr,sz,len(directory),len(bare),0xc2)
    result=b''.join([head,prior[start:end],*parts,directory]);del parts
    assert result[start:end]==prior[start:end]
    reread=Members(result);assert set(reread.members)==set(pack.members)
    # Verify every member by bytes, including all native stock assets.
    for n in pack.members:
        assert pack.read(n)==reread.read(n),n
    (work/'data.unity3d').write_bytes(result)
    overlay=result[:start]+result[end:];(work/spec['overlay_file']).write_bytes(overlay)
    spec.update(result_sha256=digest(result),overlay_sha256=digest(overlay));(work/'integration.json').write_bytes(dumps(spec))
    rep=json.loads((work/'verification.json').read_bytes())
    rep["storage"]={"identical_members":len(pack.members),"stock_block_bytes_preserved":end-start,
                    "menu_max_block_bytes":131072,"field_max_block_bytes":4<<20,"vehicle_max_block_bytes":16<<20}
    (work/'verification.json').write_bytes(dumps(rep))
    print("verified",len(pack.members),"members;",len(result),"bytes",flush=True)

if __name__=='__main__': compact(Path(sys.argv[1]))
