import hashlib
import io
import re
import struct
import zipfile
from pathlib import Path
from loguru import logger
logger.remove()
from androguard.core.axml import AXMLPrinter

NS = '{http://schemas.android.com/apk/res/android}'
LIB = 'lib/arm64-v8a/libil2cpp.so'
META = 'assets/bin/Data/Managed/Metadata/global-metadata.dat'
DATA = 'assets/bin/Data/data.unity3d'

def digest(data):
    return hashlib.sha256(data).hexdigest()

class GamePackage:
    """Read only; normalize a supported APK Set without unpacking ZIP paths."""
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.outer = zipfile.ZipFile(self.path)
        self.nested = []
        self.resource_splits = []
        if len(set(self.outer.namelist())) != len(self.outer.namelist()):
            raise ValueError('安装包有重复 ZIP 条目')
        self.kind = 'apk' if 'AndroidManifest.xml' in self.outer.namelist() else 'apks'
        if self.kind == 'apk':
            self.base = self.outer
            self.base_entry = None
        else:
            candidates = [n for n in self.outer.namelist() if n.endswith('.apk')]
            preferred = [n for n in candidates if Path(n).name in {'base.apk', 'base-master.apk'}]
            if len(preferred) != 1:
                raise ValueError('无法唯一确定 base.apk；请先用 bundletool 按 ARM64 设备规格导出安装集')
            self.base_entry = preferred[0]
            self.base = self.open_nested(self.base_entry)
        self.library_archive = self.base if LIB in self.base.namelist() else None
        if self.kind == 'apks':
            for entry in self.outer.namelist():
                if not entry.endswith('.apk') or entry == self.base_entry:
                    continue
                archive = self.open_nested(entry)
                if LIB in archive.namelist():
                    if self.library_archive is not None:
                        raise ValueError('检测到多个 ARM64 库候选，需要按设备规格选择安装集')
                    self.library_archive = archive
                # Density/language/resource splits cannot be merged by copying libs.
                if any(n == 'resources.arsc' or n.startswith(('res/', 'assets/')) for n in archive.namelist()):
                    self.resource_splits.append(entry)
        if self.library_archive is None:
            raise ValueError('未找到 arm64-v8a/libil2cpp.so')
        if 'lib/arm64-v8a/libaotmod.so' in self.base.namelist():
            raise ValueError('请导入未修改的原始安装包')
        self.library = self.library_archive.read(LIB)
        self.metadata = self.base.read(META)
        manifest = AXMLPrinter(self.base.read('AndroidManifest.xml')).get_xml_obj()
        self.identity = {'package': manifest.attrib.get('package'),
            'version_name': manifest.attrib.get(NS+'versionName'),
            'version_code': int(manifest.attrib.get(NS+'versionCode', '0')), 'abi': 'arm64-v8a'}
        bundle = self.base.read(DATA) if DATA in self.base.namelist() else b''
        # UnityFS header stores the actual engine version before compressed blocks.
        versions = re.findall(rb'\b(?:20\d\d|6000)\.\d+\.\d+[abfp]\d+\b', bundle[:256])
        self.identity['unity_version'] = versions[-1].decode() if versions else 'unknown'
        self.hashes = {'libil2cpp_sha256': digest(self.library),
            'metadata_sha256': digest(self.metadata), 'unity_data_sha256': digest(bundle)}
        self.bundle = bundle

    def open_nested(self, entry):
        info = self.outer.getinfo(entry)
        if info.file_size > 2_000_000_000:
            raise ValueError('APK 条目超过大小限制')
        archive = zipfile.ZipFile(io.BytesIO(self.outer.read(entry)))
        if len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError('APK 内有重复条目')
        self.nested.append(archive)
        return archive

    def normalized(self, path):
        if self.resource_splits:
            raise ValueError('资源 split 尚未支持合并：'+', '.join(self.resource_splits))
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as out:
            base_bytes = self.path.read_bytes() if self.kind == 'apk' else self.outer.read(self.base_entry)
            out.writestr('base.apk', base_bytes)
            if self.library_archive is not self.base:
                for entry in self.outer.namelist():
                    if entry == self.base_entry or not entry.endswith('.apk'):
                        continue
                    with zipfile.ZipFile(io.BytesIO(self.outer.read(entry))) as split:
                        if LIB in split.namelist():
                            out.writestr('arm64.apk', self.outer.read(entry))
        return Path(path)

    def close(self):
        for archive in self.nested: archive.close()
        self.outer.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
