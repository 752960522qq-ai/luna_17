"""Pinned release type trees for the reviewed Unity 6000.3.19f1 resources.

UnityPy's bundled fallback predates fields inserted inside Renderer and Mesh.
Never append an assumed suffix to that layout or rely on ObjectReader.Position:
the Boost reader advances it by the whole object, not by its consumed tree.
"""
import gzip
import hashlib
import json
from pathlib import Path
from UnityPy.helpers.TypeTreeNode import TypeTreeNode
from UnityPy.helpers import TypeTreeHelper
from UnityPy.streams import EndianBinaryReader, EndianBinaryWriter

SCHEMA_PATH = Path(__file__).resolve().parents[1]/'profiles/adapters/unity-6000.3.19f1.json.gz'

def _node(value):
    return TypeTreeNode(m_Level=value['Level'],m_Type=value['TypeName'],
        m_Name=value['Name'],m_ByteSize=value['ByteSize'],m_Version=value['Version'],
        m_MetaFlag=value['MetaFlag'],m_Index=value['Index'],m_TypeFlags=value['TypeFlags'],
        m_Children=[_node(c) for c in value['SubNodes']])

SCHEMA_BYTES = SCHEMA_PATH.read_bytes()
SCHEMA_SHA256 = 'abb1c149faa5cd7d4c08de7207a05d0430165b320dfad672775d4b9e54748dfc'
if hashlib.sha256(SCHEMA_BYTES).hexdigest()!=SCHEMA_SHA256:
    raise ValueError('Reviewed serialization schema fingerprint changed')
REVIEWED_SCHEMA = json.loads(gzip.decompress(SCHEMA_BYTES))
UNITY_VERSION = REVIEWED_SCHEMA['unity_version']
NODES = {name:_node(value) for name,value in REVIEWED_SCHEMA['classes'].items()}

def apply_reviewed_typetrees(env):
    """Use the pinned schema only on the exact reviewed version, locally to env.

    Supplying parser nodes does not enable embedded trees or alter object bytes.
    """
    files = {id(o.assets_file):o.assets_file for o in env.objects}
    for file in files.values():
        if file.unity_version != UNITY_VERSION:
            raise ValueError('Unsupported Unity serialization version: '+file.unity_version)
        for obj in file.objects.values():
            node=NODES.get(obj.type.name)
            if node is not None:
                obj.serialized_type.node=node
    return {'unity_version':UNITY_VERSION,'class_count':len(NODES),
        'schema_sha256':hashlib.sha256(SCHEMA_BYTES).hexdigest(),
        'source_commit':REVIEWED_SCHEMA['source_commit']}

def parse_complete(obj,raw=None,node=None):
    raw=obj.get_raw_data() if raw is None else raw
    node=obj._get_typetree_node() if node is None else node
    reader=EndianBinaryReader(raw,endian=obj.reader.endian)
    # check_read checks the actual consumed length returned by Boost.
    return TypeTreeHelper.read_typetree(node,reader,as_dict=True,
        byte_size=len(raw),check_read=True,assetsfile=obj.assets_file)

def encode_complete(obj,tree,node=None,writer=None):
    node=obj._get_typetree_node() if node is None else node
    writer=EndianBinaryWriter(endian=obj.reader.endian) if writer is None else writer
    TypeTreeHelper.write_typetree(tree,node,writer,obj.assets_file)
    return writer.bytes

def assert_roundtrip(obj,raw=None):
    raw=obj.get_raw_data() if raw is None else raw
    tree=parse_complete(obj,raw)
    if encode_complete(obj,tree) != raw:
        raise ValueError(f'Non-lossless serialization: {obj.type.name} {obj.path_id}')
    return tree
