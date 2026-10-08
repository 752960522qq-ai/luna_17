import json
import math
import re
import struct
import zipfile
from pathlib import PurePosixPath, Path

COUNTRIES = {'USSR','Germany','USA','Japan','UK','Italy'}
REQUIRED = {'manifest.json','tank.json','weapon.json','armor.json','model.glb','thumbnail.png'}

def validate_documents(documents):
    errors=[]
    manifest=documents.get('manifest',{})
    if manifest.get('format')!=1:errors.append('manifest.format 必须为 1')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(manifest.get('id',''))):errors.append('载具 id 格式错误')
    for k in ('displayName','basePrefab'):
        if not isinstance(manifest.get(k),str) or not 1<=len(manifest[k])<=128:errors.append('缺少 '+k)
    if manifest.get('country') not in COUNTRIES:errors.append('country 不在六国支持列表中')
    for section in ('tank','weapon','armor'):
        value=documents.get(section)
        if not isinstance(value,dict) or not value:errors.append('缺少 '+section+' 参数');continue
        def walk(obj):
            if isinstance(obj,dict):
                for v in obj.values():walk(v)
            elif isinstance(obj,list):
                for v in obj:walk(v)
            elif isinstance(obj,(int,float)) and (isinstance(obj,bool) or not math.isfinite(obj)):
                errors.append(section+' 包含无效数值')
        walk(value)
    for key in ('maxForwardSpeed','maxReverseSpeed','enginePower','crew','gunElevation','gunDepression','turretRotation'):
        value=documents.get('tank',{}).get(key)
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):errors.append('tank.'+key+' 需要有限数值')
        elif key not in ('gunDepression',) and value<0:errors.append('tank.'+key+' 不得为负数')
    weapon=documents.get('weapon',{})
    for key in ('caliber','reload'):
        value=weapon.get(key)
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<=0:errors.append('weapon.'+key+' 必须大于 0')
    ammo=weapon.get('ammo',{})
    if not isinstance(ammo,dict) or not ammo:errors.append('缺少弹药分配')
    else:
        for k,v in ammo.items():
            if k not in ('AP','APCR','HE','HEAT','WP') or type(v)!=int or v<0:errors.append('弹药种类或数量无效')
    adapter=manifest.get('role')=='player' and manifest.get('adapter')=='aot-5.1.0-arm64-v1' and manifest.get('basePrefab') in ('T34_85_Player','SU_85_Player','ZiS_3_Player')
    if adapter:
        from .project import document_errors
        errors.extend(document_errors(documents))
    return {'valid':not errors,'errors':errors,'id':manifest.get('id'),
        'display_name':manifest.get('displayName'),'can_inject':adapter and not errors,
        'reason':'需要完整模型/绑定检查及匹配原始 5.1.0' if adapter else '需要选择已有适配器'}

def validate_pack(path):
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist();names=[i.filename for i in infos]
        if len(set(names))!=len(names) or len(names)>64:raise ValueError('重复或过多 ZIP 条目')
        for info in infos:
            name=info.filename;p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:raise ValueError('Tank Pack 包含不安全路径')
        if sum(i.file_size for i in infos)>512*1024*1024:raise ValueError('Tank Pack 解压大小过大')
        if not REQUIRED.issubset(names):raise ValueError('缺少文件：'+', '.join(sorted(REQUIRED-set(names))))
        documents={}
        for name in ('manifest','tank','weapon','armor'):
            if archive.getinfo(name+'.json').file_size>1024*1024:raise ValueError('JSON 参数文件过大')
            documents[name]=json.loads(archive.read(name+'.json'))
        report=validate_documents(documents)
        glb=archive.read('model.glb')
        if len(glb)<12 or struct.unpack_from('<4sII',glb)!= (b'glTF',2,len(glb)):
            report['errors'].append('model.glb 不是有效的 GLB 2.0 容器')
        if not archive.read('thumbnail.png').startswith(b'\x89PNG\r\n\x1a\n'):
            report['errors'].append('thumbnail.png 不是 PNG')
        if report['can_inject'] and 'rig.json' not in names:
            report['errors'].append('已审核的模型包需要 rig.json')
        if report['can_inject'] and not report['errors']:
            import tempfile
            from .project import validate_project
            with tempfile.TemporaryDirectory() as temp:
                directory=Path(temp)
                for info in infos:
                    if info.is_dir():continue
                    target=directory/info.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(info))
                checked=validate_project(directory);report['errors'].extend(checked['errors']);report['model']=checked
        report['valid']=not report['errors'];report['can_inject']=report['can_inject'] and report['valid'];report['file']=str(path)
        return report

def extract_reviewed_pack(path,destination):
    report=validate_pack(path)
    if not report['valid'] or not report['can_inject']:raise ValueError(report['reason'])
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir():continue
            target=destination/info.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(info))
    return destination
