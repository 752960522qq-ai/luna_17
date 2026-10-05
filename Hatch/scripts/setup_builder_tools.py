#!/usr/bin/env python3
"""Fetch two Android SDK packages from Google's index, checking sizes/checksums.
No signing keys are downloaded or generated. Requires an installed JDK 17+.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

BASE='https://dl.google.com/android/repository/'

def install(package_id,directory):
    xml=ET.fromstring(urllib.request.urlopen(BASE+'repository2-1.xml',timeout=60).read())
    package=next(p for p in xml if p.tag.endswith('remotePackage') and p.get('path')==package_id)
    archives=package.find('archives').findall('archive')
    host={'Linux':'linux','Windows':'windows','Darwin':'macosx'}[platform.system()]
    archive=next(a for a in archives if a.findtext('host-os') in (None,host))
    complete=archive.find('complete');url=complete.findtext('url')
    if '/' in url or '..' in url:raise ValueError('非法 SDK 下载地址')
    expected_size=int(complete.findtext('size'));checksum=complete.find('checksum')
    algorithm=checksum.get('type','sha1');expected=checksum.text.strip()
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        downloaded=Path(temporary)/'package.zip';hasher=hashlib.new(algorithm)
        with urllib.request.urlopen(BASE+url,timeout=60) as response, downloaded.open('wb') as file:
            while data:=response.read(1024*1024):file.write(data);hasher.update(data)
        if downloaded.stat().st_size!=expected_size or hasher.hexdigest()!=expected:raise ValueError('SDK 下载校验失败')
        extracted=Path(temporary)/'content';extracted.mkdir()
        with zipfile.ZipFile(downloaded) as z:
            for info in z.infolist():
                target=(extracted/info.filename).resolve()
                if not target.is_relative_to(extracted.resolve()):raise ValueError('非法 SDK ZIP 路径')
            z.extractall(extracted)
        target=directory/package_id.replace(';','-');target.mkdir(exist_ok=True)
        for child in extracted.iterdir():
            if child.is_dir():shutil.copytree(child,target,dirs_exist_ok=True)
            else:shutil.copy2(child,target/child.name)
        for file in target.rglob('*'):
            if file.is_file() and file.name in {'zipalign','aapt','aapt2','d8'}:os.chmod(file,0o755)
    print('SDK package verified:',package_id)
    return target

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('tools'))
    p.add_argument('--config',type=Path,default=Path('builder.config.json'));args=p.parse_args()
    args.directory=args.directory.resolve();args.directory.mkdir(parents=True,exist_ok=True)
    platform_dir=install('platforms;android-35',args.directory)
    build_dir=install('build-tools;35.0.0',args.directory)
    def one(root,name):return str(next(root.rglob(name)))
    root=Path(__file__).resolve().parents[1]
    config={'android_jar':one(platform_dir,'android.jar'),'r8':one(build_dir,'d8.jar'),
        'apksigner':one(build_dir,'apksigner.jar'),'zipalign':one(build_dir,'zipalign.exe' if os.name=='nt' else 'zipalign'),
        'native_prebuilt':str(root/'prebuilt/5.1.0/libaotmod.so'),
        'keystore':str(root/'private/luna17-development.jks'),'password_file':str(root/'private/password.txt'),
        'alias':'luna17','expected_certificate_sha256':'9b09d75b77a30e67aa14196823b41cc04c70cb3ec6ac1eab41c41f0980568571'}
    args.config.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8');print('Config:',args.config.resolve())

if __name__=='__main__':main()
