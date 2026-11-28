"""Separate the right deck access hatch from the released T26 turret, keeping the belt indices stable."""
import copy
import hashlib
import json
import struct
import tempfile
import zipfile
from pathlib import Path

import numpy as np
from pygltflib import Mesh, Node
from hatch.pack import CFG, NODE
from .modelrig import Model
from .enemy_visuals import read_model

BASE_RUNTIME = "f4174df72e8e2aca1a630f81d422f59bbba8eafeff64c0498faf47313f78733d"
HATCH = "T26_Hull_Access_Hatch"
FIDUCIAL_TRIANGLES = 174  # lid, surround, insert, hinge and handle on the right deck


def split(v, faces, pivot, unity=False):
    world = v[:, :3].astype(float) + pivot
    if unity: world[:, 2] *= -1
    # Weld only for topology detection; the exported surfaces retain every UV/normal seam.
    _, weld = np.unique(np.round(world,4),axis=0,return_inverse=True)
    tri=weld[faces]; parents=list(range(int(weld.max())+1))
    def root(i):
        while parents[i]!=i:
            parents[i]=parents[parents[i]];i=parents[i]
        return i
    for a,b,c in tri:
        q=root(a);parents[root(b)]=q;parents[root(c)]=q
    labels=np.array([root(a) for a in tri[:,0]])
    groups=[k for k in np.unique(labels) if
            ((world[faces[labels==k]] >= [.410,1.545,.165]) &
             (world[faces[labels==k]] <= [.800,1.593,.595])).all()]
    selected=np.isin(labels,groups)
    if len(groups)!=5 or selected.sum() != FIDUCIAL_TRIANGLES:
        raise ValueError("Right deck hatch no longer matches five complete islands")
    def compact(t):
        ids, inv = np.unique(t.ravel(), return_inverse=True)
        return ids, inv.reshape(-1,3)
    return compact(faces[~selected]), compact(faces[selected])


def glb_hatch(path):
    m = Model(path); g = m.g
    ni, = [i for i,n in enumerate(g.nodes) if n.name == "Turret_Visual"]
    hull, = [i for i,n in enumerate(g.nodes) if n.name == "Hull"]
    mesh = g.meshes[g.nodes[ni].mesh]
    prim, = mesh.primitives
    tr = m.translation(ni) - m.translation(hull)
    keep, hatch = split(m.array(prim.attributes.POSITION), m.array(prim.indices).reshape(-1,3), m.translation(ni))
    def primitive(part):
        ids, ix = part
        q = copy.deepcopy(prim)
        for field, ac in vars(prim.attributes).items():
            if ac is None: continue
            old = g.accessors[ac]
            setattr(q.attributes, field, m.add_array(m.array(ac)[ids], old.type, old.componentType))
        q.indices = m.add_array(ix, "SCALAR", g.accessors[prim.indices].componentType)
        return q
    mesh.primitives = [primitive(keep)]
    new = len(g.nodes)
    g.nodes[hull].children.append(new)
    g.nodes.append(Node(name=HATCH, mesh=len(g.meshes), translation=tr.tolist()))
    g.meshes.append(Mesh(name=HATCH, primitives=[primitive(hatch)]))
    m.save(path)
    return new


def runtime_hatch(data, h):
    _, nodes, _ = read_model(data, h)
    at = 24 + CFG.size
    records=[]; extra=[]
    for i,n in enumerate(nodes):
        stop = at + NODE.size + n.vertices.nbytes + n.indices.nbytes
        if n.name in ("mesh_5_0", "mesh_5_0_back") and n.parent == 5:
            pivot = np.array(nodes[1].trs[:3])
            keep, hatch = split(n.vertices, n.indices.reshape(-1,3), pivot, unity=True)
            def subset(part, parent, name):
                ids, ix = part; rec=list(NODE.unpack_from(data, at))
                rec[0]=parent;rec[12:14]=[len(ids),ix.size];rec[20]=name.encode()
                return NODE.pack(*rec)+n.vertices[ids].tobytes()+ix.astype("<u4").tobytes()
            records.append(subset(keep, n.parent, n.name))
            extra.append(subset(hatch,len(nodes),HATCH+("_Back" if n.name.endswith("_back") else "_Face")))
        else: records.append(data[at:stop])
        at=stop
    if len(extra)!=2:raise ValueError("Expected both sides of the turret surface")
    rest = [0.,0.,0.,1.,1.,1.,1.]
    pivot=NODE.pack(0,0,*nodes[1].trs[:3],*rest,0,0,-1,-1,1,1,1,1,HATCH.encode())
    payload=data[24:24+CFG.size]+b"".join(records+[pivot]+extra)+data[at:]
    return struct.pack("<8sIIII",b"HATCH01\0",1,len(payload)+24,len(nodes)+3,h["textures"])+payload


def update(source, dest):
    with zipfile.ZipFile(source) as old, tempfile.TemporaryDirectory() as tmp:
        h=json.loads(old.read("hatch.json"));rig=json.loads(old.read("rig.json"))
        if h["id"]!="T26" or h["runtime_sha256"]!=BASE_RUNTIME: raise ValueError("Unreviewed T26 source")
        f=Path(tmp)/"model.glb";f.write_bytes(old.read(f.name));gid=glb_hatch(f)
        blob=runtime_hatch(old.read("runtime.bin"),h)
        rig["hullAccessHatch"]={"name":HATCH,"node":gid,"runtimeNode":h["nodes"],"parent":"Hull"}
        h.update(nodes=h["nodes"]+3,runtime_bytes=len(blob),runtime_sha256=hashlib.sha256(blob).hexdigest())
        _,ns,_=read_model(blob,h)
        assert ns[rig["hullAccessHatch"]["runtimeNode"]].parent==0
        changes={"model.glb":f.read_bytes(),"runtime.bin":blob,
                 "hatch.json":json.dumps(h,ensure_ascii=False,indent=2).encode(),
                 "rig.json":json.dumps(rig,ensure_ascii=False,indent=2).encode()}
        with zipfile.ZipFile(dest,"w") as out:
            for e in old.infolist():out.writestr(e,changes[e.filename] if e.filename in changes else old.read(e.filename))
