"""Read Hatch's shipped model stream and emit real Unity render assets (no APK)."""

import hashlib
import io
import struct
from dataclasses import dataclass

import numpy as np
from PIL import Image

from hatch.pack import CFG, NODE

from .unity_assets import aabb, pp


@dataclass
class Node:
    parent: int
    flags: int
    trs: tuple
    images: tuple
    tint: tuple
    name: str
    vertices: np.ndarray
    indices: np.ndarray


def read_model(data, manifest):
    magic, version, size, count, image_count = struct.unpack_from("<8sIIII", data)
    if (magic, version, size, count, image_count) != (
        b"HATCH01\0",
        1,
        len(data),
        manifest["nodes"],
        manifest["textures"],
    ):
        raise ValueError("Hatch stream/header mismatch")
    if hashlib.sha256(data).hexdigest() != manifest["runtime_sha256"]:
        raise ValueError("Hatch stream hash mismatch")
    cfg = CFG.unpack_from(data, 24)
    if cfg[0].split(b"\0")[0].decode() != manifest["id"]:
        raise ValueError("Tank ID mismatch")
    at, nodes, images = 24 + CFG.size, [], []
    for _ in range(count):
        v = NODE.unpack_from(data, at)
        at += NODE.size
        nv, ni = v[12:14]
        verts = np.frombuffer(data, "<f4", nv * 8, at).reshape((-1, 8))
        at += nv * 32
        inds = np.frombuffer(data, "<u4", ni, at)
        at += ni * 4
        if ni % 3 or (ni and inds.max() >= nv) or not np.isfinite(verts).all():
            raise ValueError("Invalid Hatch geometry")
        nodes.append(
            Node(v[0], v[1], v[2:12], v[14:16], v[16:20], v[20].split(b"\0")[0].decode(), verts, inds)
        )
    for _ in range(image_count):
        (n,) = struct.unpack_from("<I", data, at)
        at += 4
        if at + n > len(data):
            raise ValueError("Texture exceeds Hatch stream")
        images.append(data[at : at + n])
        at += n
    if at != len(data) and (
        data[at : at + 8] != b"HATCHOPT" or struct.unpack_from("<I", data, at + 8)[0] != len(data) - at
    ):
        raise ValueError("Unknown Hatch trailer")
    for i, n in enumerate(nodes):
        ancestor, visited = i, set()
        while ancestor != -1:
            if not 0 <= ancestor < count or ancestor in visited:
                raise ValueError("Invalid Hatch hierarchy")
            visited.add(ancestor)
            ancestor = nodes[ancestor].parent
    return cfg, nodes, images


def matrix(trs):
    x, y, z, w = trs[3:7]
    rot = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )
    m = np.eye(4)
    m[:3, :3] = rot @ np.diag(trs[7:])
    m[:3, 3] = trs[:3]
    return m


def local_point(nodes, index, model_position):
    world = np.eye(4)
    while index >= 0:
        world = matrix(nodes[index].trs) @ world
        index = nodes[index].parent
    x, y, z = model_position
    return np.linalg.solve(world, (x, y, -z, 1))[:3]


class Visuals:
    def __init__(self, stage, images, ident, manifest):
        self.s = stage
        self.images = images
        self.ident = ident
        self.textures = {}
        self.materials = {}
        self.alpha = {}
        self.uv_unity = manifest.get("texture_uv_convention", "").lower().startswith("unity")

    def texture(self, i, normal=False):
        if i < 0:
            return pp()
        key = i, normal
        if key in self.textures:
            return pp(self.textures[key])
        with Image.open(io.BytesIO(self.images[i])) as im:
            im = im.convert("RGBA")
            self.alpha[i] = im.getchannel("A").getextrema()[0] < 128
            data = im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
            t = self.s.template("Texture2D")
            t.update(
                m_Name=f"{self.ident}_tex{i}" + ("_n" if normal else ""),
                m_Width=im.width,
                m_Height=im.height,
                m_TextureFormat=4,
                m_MipCount=1,
                m_CompleteImageSize=len(data),
                m_IsReadable=False,
                m_StreamingMipmaps=False,
                m_MipsStripped=0,
                m_ColorSpace=0 if normal else 1,
                m_StreamData={"offset": 0, "size": 0, "path": ""},
                m_PlatformBlob=b"",
            )
            t["image data"] = data
        pid = self.s.make("Texture2D", t)
        self.textures[key] = pid
        return pp(pid)

    def material(self, node, track):
        # Two track sides need distinct materials when the game scrolls them independently.
        key = node.images, node.tint, track
        if key in self.materials:
            return self.materials[key]
        t = self.s.standard_material()
        color, norm = node.images
        main, bump = self.texture(color), self.texture(norm, True)
        t["m_Name"] = f"{self.ident}_mat{len(self.materials)}"
        t["m_ValidKeywords"] = []
        t["m_InvalidKeywords"] = []
        for name, val in t["m_SavedProperties"]["m_TexEnvs"]:
            val.update(
                m_Texture=main if name == "_MainTex" else bump if name == "_BumpMap" else pp(),
                m_Offset={"x": 0.0, "y": 0.0},
                m_Scale={"x": 1.0, "y": 1.0},
            )
        t["disabledShaderPasses"] = []
        t["m_CustomRenderQueue"] = -1
        t["stringTagMap"] = []
        if norm >= 0:
            t["m_ValidKeywords"].append("_NORMALMAP")
        cutout = track is not None and self.alpha.get(color, False)
        if cutout:
            t["m_ValidKeywords"].append("_ALPHATEST_ON")
            t["m_CustomRenderQueue"] = 2450
            t["stringTagMap"] = [("RenderType", "TransparentCutout")]
        floats = dict(t["m_SavedProperties"]["m_Floats"])
        floats.update(
            _Metallic=0.0,
            _Glossiness=0.25,
            _SpecularHighlights=0.0,
            _GlossyReflections=0.0,
            _Mode=1.0 if cutout else 0.0,
            _Cutoff=0.5,
            _SrcBlend=1.0,
            _DstBlend=0.0,
            _ZWrite=1.0,
        )
        t["m_SavedProperties"]["m_Floats"] = list(floats.items())
        for name, c in t["m_SavedProperties"]["m_Colors"]:
            if name == "_Color":
                c.update(zip("rgba", node.tint))
        pid = self.s.make("Material", t)
        self.materials[key] = pid
        return pid

    def mesh(self, n, i, cpu_deform=False):
        verts = n.vertices.copy()
        if not self.uv_unity:
            verts[:, 7] = 1.0 - verts[:, 7]
        bounds = aabb(verts[:, :3])
        count = len(n.indices)
        t = self.s.template("Mesh")
        channels = [{"stream": 0, "offset": 0, "format": 0, "dimension": 0} for _ in range(14)]
        for ch, of, dim in ((0, 0, 3), (1, 12, 3), (4, 24, 2)):
            channels[ch].update(offset=of, dimension=dim)
        t.update(
            m_Name=f"{self.ident}_{i}_{n.name}",
            m_SubMeshes=[
                {
                    "firstByte": 0,
                    "indexCount": count,
                    "topology": 0,
                    "baseVertex": 0,
                    "firstVertex": 0,
                    "vertexCount": len(verts),
                    "localAABB": bounds,
                }
            ],
            m_MeshCompression=0,
            m_IsReadable=cpu_deform,
            m_IndexFormat=int(len(verts) > 65535),
            m_IndexBuffer=n.indices.astype("<u4" if len(verts) > 65535 else "<u2").tobytes(),
            m_VertexData={
                "m_VertexCount": len(verts),
                "m_Channels": channels,
                "m_DataSize": verts.tobytes(),
            },
            m_LocalAABB=bounds,
            m_BindPose=[],
            m_BoneNameHashes=[],
            m_BonesAABB=[],
            m_RootBoneNameHash=0,
            m_BakedConvexCollisionMesh=b"",
            m_BakedTriangleCollisionMesh=b"",
            m_StreamData={"offset": 0, "size": 0, "path": ""},
            m_MeshLodInfo={
                "m_LodSelectionCurve": {"m_LodSlope": 0.0, "m_LodBias": 0.0},
                "m_NumLevels": 1,
                "m_SubMeshes": [{"m_Levels": [{"m_IndexStart": 0, "m_IndexCount": count}]}],
            },
        )
        if cpu_deform:
            t.update(m_KeepVertices=True, m_KeepIndices=True)
        return self.s.make("Mesh", t)

    def render(self, node, i, go, track, *, cpu_deform=False):
        mesh = self.mesh(node, i, cpu_deform)
        mat = self.material(node, track)
        f = self.s.make("MeshFilter", {"m_GameObject": pp(go), "m_Mesh": pp(mesh)})
        t = self.s.template("MeshRenderer")
        t.update(
            m_GameObject=pp(go),
            m_Enabled=True,
            m_Materials=[pp(mat)],
            m_LightmapIndex=65535,
            m_LightmapIndexDynamic=65535,
            m_StaticBatchRoot=pp(),
            m_StaticBatchInfo={"firstSubMesh": 0, "subMeshCount": 0},
            m_ProbeAnchor=pp(),
            m_LightProbeVolumeOverride=pp(),
            m_AdditionalVertexStreams=pp(),
            m_EnlightenVertexStream=pp(),
            m_ForceMeshLod=-1,
        )
        r = self.s.make("MeshRenderer", t)
        tree = self.s.get(go)
        tree["m_Component"] += [{"component": pp(f)}, {"component": pp(r)}]
        self.s.put(go, tree)
        return r
