"""Read the original OBJ material islands from the author's GLB, without discarding its UV maps."""
import hashlib, io
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from ..modelrig import Model
from ..panzer4c.source import Island

ID = 'T28'
SOURCE_SHA = '58c815552c2bc9fed9f5f31cb46d61b0a79e8503ae46b83b0e51e89583507d09'
def read(path):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SOURCE_SHA:
        raise ValueError('Different T-28 source: re-audit the material islands.')
    model = Model(path)
    g = model.g
    parts = {}
    images = {}
    for n,image in enumerate(g.images):
        bv = g.bufferViews[image.bufferView]
        with Image.open(io.BytesIO(model.blob[bv.byteOffset:bv.byteOffset+bv.byteLength])) as im:
            images[n] = im.convert('RGBA')
    for j,mesh in enumerate(g.meshes):
        p, = mesh.primitives
        ix = model.array(p.indices).reshape(-1, 3)
        v, n, uv = [model.array(getattr(p.attributes, k))[ix].astype(float) for k in (
            'POSITION',
            'NORMAL',
            'TEXCOORD_0'
        )]
        vs, inv = np.unique(np.round(v.reshape(-1, 3), 5), axis=0, return_inverse=True)
        tri = inv.reshape(-1, 3)
        a = tri.ravel()
        b = tri[:, [1, 2, 0]].ravel()
        count, cc = connected_components(coo_matrix((np.ones(len(a)), (a, b)), shape=(len(vs), len(vs))), directed=False)
        labels = cc[tri[:, 0]]
        for k in range(count):
            sel = labels == k
            parts[j * 10000 + k] = Island(v[sel], n[sel], uv[sel], j, p.material)
    return (parts, images, g.asset.extras)
