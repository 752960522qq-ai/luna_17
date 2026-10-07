"""Persistent, reusable tank projects. No analysis service is used at build time."""
import copy, hashlib, io, json, math, os, re, shutil, tempfile, zipfile
from pathlib import Path
from .modelrig import Model
from PIL import Image
from pygltflib import BufferView

NATIONS=['USSR','Germany','USA','Japan','UK','Italy']
ADAPTER='aot-5.1.0-arm64-v1'
FILES=['manifest.json','tank.json','weapon.json','armor.json','rig.json','model.glb','thumbnail.png']
ROOT=Path(__file__).resolve().parents[1]

def read_documents(directory):
    d=Path(directory)
    return {n:json.loads((d/(n+'.json')).read_text(encoding='utf-8')) for n in ['manifest','tank','weapon','armor','rig']}

def document_errors(doc):
    errors=[];m=doc.get('manifest',{});t=doc.get('tank',{});w=doc.get('weapon',{});a=doc.get('armor',{})
    if not all(isinstance(x,dict) for x in (m,t,w,a)):return ['参数必须为 JSON 对象']
    if m.get('format')!=1:errors.append('manifest.format 必须为 1')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',str(m.get('id',''))):errors.append('ID 需要 1–48 个字母、数字、下划线或短横线')
    if not isinstance(m.get('displayName'),str) or not 1<=len(m['displayName'])<=128:errors.append('需要车型名称')
    if m.get('country') not in NATIONS:errors.append('需要选择已有六国之一')
    if m.get('adapter')!=ADAPTER or m.get('basePrefab')!='T34_85_Player' or m.get('role')!='player':errors.append('当前需要 T34_85_Player 玩家模板及 5.1.0 适配器')
    def num(section,key,low,high,integer=False):
        v=section.get(key)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high or (integer and int(v)!=v):errors.append(key+' 数值超出范围')
    num(m,'tier',1,255,True)
    for k,lo,hi,integer in [('crew',1,20,True),('maxForwardSpeed',1,150,True),('maxReverseSpeed',0,80,False),('enginePower',1,3000,True),('weightTonnes',1,200,False),('gunElevation',0,80,True),('gunDepression',-30,0,True),('turretRotation',1,90,False)]:num(t,k,lo,hi,integer)
    for k,lo,hi,integer in [('caliber',1,300,True),('reload',1,120,False),('muzzleVelocity',1,2500,True)]:num(w,k,lo,hi,integer)
    if w.get('ballistics','physical') not in ('physical','stock-t34-85'):errors.append('不支持的弹道配置')
    magazine=w.get('magazine')
    if magazine is not None:
        if not isinstance(magazine,dict):errors.append('magazine 需要对象')
        else:
            num(magazine,'capacity',2,200,True);num(magazine,'shotInterval',.03,60);num(magazine,'reloadTime',.03,300)
            if isinstance(magazine.get('reloadTime'),(int,float)) and isinstance(magazine.get('shotInterval'),(int,float)) and magazine['reloadTime']<magazine['shotInterval']:errors.append('整匣换弹时间不能小于射击间隔')
    if not isinstance(w.get('name'),str) or not 1<=len(w['name'])<=128:errors.append('需要火炮名称')
    ammo=w.get('ammo',{})
    if not isinstance(ammo,dict) or not ammo:errors.append('需要弹药分配')
    else:
        for k,v in ammo.items():
            if k not in ['AP','APCR','HE','HEAT'] or type(v)!=int or not 0<=v<=1000:errors.append('弹种或备弹量错误')
    shells=w.get('shells',{})
    for kind in ['AP','APCR','HEAT']:
        num(shells.get(kind,{}) if isinstance(shells,dict) else {},'penetrationMm',0,2000,True)
    mg=w.get('machineGun',{})
    num(mg if isinstance(mg,dict) else {},'ammo',0,1000,True)
    for region in ['body','turret']:
        value=a.get(region,{})
        if not isinstance(value,dict):errors.append('装甲分区错误');continue
        for face in ['front','side','rear']:num(value,face,0,2000,True)
    dims=t.get('dimensionsMeters',{})
    if not isinstance(dims,dict):errors.append('需要尺寸');dims={}
    for k in ['length','width','height']:num(dims,k,.1,30)
    return errors

def validate_project(directory):
    d=Path(directory);errors=[];summary={}
    try:
        doc=read_documents(d);errors+=document_errors(doc);m=Model(d/'model.glb');g=m.g;r=doc['rig']
        if len(g.nodes)>4096 or len(g.materials)>256 or len(g.meshes)>2048:errors.append('模型超过节点或材质上限')
        if len(g.buffers)!=1 or g.buffers[0].uri:errors.append('GLB 需要内嵌单个二进制缓冲区')
        if any(x.uri or x.bufferView is None for x in g.images):errors.append('图片必须嵌入 GLB；请先通过贴图替换命令嵌入')
        if g.extensionsRequired:errors.append('请导出未压缩的标准 GLB，移除必需扩展')
        names=[n.name for n in g.nodes]
        for name in ['Hull','Turret','Gun','Barrel_Recoil']:
            if names.count(name)!=1:errors.append('需要唯一模型节点 '+name)
        parents=m.parents()
        if not g.materials:errors.append('模型需要材质')
        if any(a.sparse for a in g.accessors):errors.append('请导出非稀疏顶点访问器')
        for start in range(len(g.nodes)):
            seen=set();i=start
            while i in parents:
                if i in seen:raise ValueError('模型层级存在循环')
                seen.add(i);i=parents[i]
        for i,n in enumerate(g.nodes):
            if n.matrix:errors.append('节点矩阵请在导出时转为位置/旋转/缩放')
            if n.mesh is not None:
                for p in g.meshes[n.mesh].primitives:
                    if p.mode not in (None,4) or p.indices is None:errors.append('只支持有索引的三角形网格');continue
                    vertices=m.array(p.attributes.POSITION);idx=m.array(p.indices)
                    if not len(vertices) or len(idx)%3 or idx.min()<0 or idx.max()>=len(vertices) or not __import__('numpy').isfinite(vertices).all():errors.append('模型顶点或索引无效')
                    if p.material is not None and not 0<=p.material<len(g.materials):errors.append('材质索引无效')
        for name in ['Turret','Gun','Barrel_Recoil']:
            if name not in names:continue
            i=names.index(name);ancestor={'Turret':'Hull','Gun':'Turret','Barrel_Recoil':'Gun'}[name];seen=set()
            while i in parents and i not in seen:
                seen.add(i);i=parents[i]
                if names[i]==ancestor:break
            else:errors.append(name+' 应位于 '+ancestor+' 下方')
        for key,name in [('turret','Turret'),('gun','Gun')]:
            node=r.get(key,{}).get('node')
            if type(node)!=int or not 0<=node<len(names) or names[node]!=name:errors.append('rig.'+key+' 与模型节点不一致')
        wheels=r.get('wheels',[]);road=[w for w in wheels if w.get('roadWheel')];tracks=r.get('tracks',[])
        if not 4<=len(road)<=24 or len(road)%2 or len(wheels)>28:errors.append('需要 4–24 个偶数负重轮；总轮数最多 28')
        if len({w.get('node') for w in wheels})!=len(wheels):errors.append('车轮节点重复')
        if sum(w.get('side')=='left' for w in road)!=len(road)//2:errors.append('左右负重轮数量应相同')
        for wheel in wheels:
            for key in ['node','suspensionNode'] if wheel.get('roadWheel') else ['node']:
                if type(wheel.get(key))!=int or not 0<=wheel[key]<len(names):errors.append('车轮节点索引无效')
            if wheel.get('side') not in ['left','right'] or not .05<=wheel.get('radius',0)<=2:errors.append('车轮方向或半径错误')
        if len(tracks)!=2 or any(x not in names or g.nodes[names.index(x)].mesh is None for x in tracks):errors.append('需要左右履带网格节点')
        for key in ['turret','gun']:
            v=r.get(key,{}).get('pivot')
            if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in v):errors.append('缺少 '+key+' 转动轴位置')
        for key in ['muzzle','coaxMuzzle']:
            pos=r.get(key,{}).get('position')
            if not isinstance(pos,list) or len(pos)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in pos):errors.append('缺少 '+key+' 发射点')
        for key in ['hull','turret','unit']:
            c=r.get('colliders',{}).get(key,{})
            for field in ['size','center']:
                v=c.get(field)
                if not isinstance(v,list) or len(v)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) or (field=='size' and x<=0) for x in v):errors.append('缺少碰撞体 '+key+'.'+field)
        s=r.get('suspension',{})
        for key in ['travel','restCompression','springPerWheel','damperPerWheel']: 
            if type(s.get(key)) not in (int,float) or not math.isfinite(s[key]) or s[key]<=0:errors.append('悬挂参数错误 '+key)
        # All transforms used as pivots must start in canonical orientation.
        for key in ['turret','gun']:
            node=r.get(key,{}).get('node')
            if type(node)==int and 0<=node<len(g.nodes):
                i=node
                while True:
                    n=g.nodes[i]
                    if n.rotation and any(abs(x-y)>1e-5 for x,y in zip(n.rotation,[0,0,0,1])):errors.append('炮塔/火炮祖先的初始旋转应归零');break
                    if n.scale and any(abs(x-1)>1e-5 for x in n.scale):errors.append('炮塔/火炮祖先的缩放应应用到几何');break
                    if i not in parents:break
                    i=parents[i]
        Image.open(d/'thumbnail.png').verify()
        summary={'id':doc['manifest']['id'],'meshes':sum(n.mesh is not None for n in g.nodes),'nodes':len(names),'materials':len(g.materials),'wheels':len(road),'textures':len(g.images)}
    except Exception as e:errors.append(str(e))
    return {'valid':not errors,'can_inject':not errors,'errors':list(dict.fromkeys(errors)),**summary,'android_device_test':'not performed'}

def default_colliders(tank):
    d=tank['dimensionsMeters'];w,h,l=d['width'],d['height'],d['length']
    return {'hull':{'size':[w*.95,h*.58,l*.65],'center':[0,h*.33,0]},'turret':{'size':[w*.75,h*.4,l*.28],'center':[0,h*.1,0]},'unit':{'size':[w*1.04,h*1.16,l*.72],'center':[0,h*.58,0]}}

def create_project(output,template='T54_1949',ident=None):
    if ident and not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',ident):raise ValueError('坦克 ID 格式无效')
    source=Path(template)
    if not source.is_dir():source=ROOT/'tanks'/template
    out=Path(output)
    if out.exists():raise ValueError('目标目录已存在，避免覆盖已有项目')
    shutil.copytree(source,out)
    try:
        doc=read_documents(out)
        if ident:doc['manifest']['id']=ident;doc['manifest']['displayName']=ident
        doc['rig'].setdefault('colliders',default_colliders(doc['tank']))
        # Inputs carry their original sample parameters; no historical-data claims.
        save_documents(out,doc);return validate_project(out)
    except Exception:
        shutil.rmtree(out);raise

def save_documents(directory,doc):
    for key,value in doc.items():
        if key not in ['manifest','tank','weapon','armor','rig']:raise ValueError('未知项目文件')
        target=Path(directory)/(key+'.json');tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');os.replace(tmp,target)

def infer_rig(model,tank):
    """Canonical named models: infer pivots and wheel radii, require an explicit muzzle marker."""
    import numpy as np
    names=[n.name for n in model.g.nodes];parents=model.parents()
    for name in ['Hull','Turret','Gun','Barrel_Recoil','Muzzle_Main']:
        if names.count(name)!=1:raise ValueError('自动绑定需要唯一节点 '+name+'；或提供 rig.json')
    wheels=[]
    for i,n in enumerate(model.g.nodes):
        match=re.match(r'wheel_([lr])_(\d+)',n.name or '')
        if not match or n.mesh is None:continue
        lo,hi=model.bounds(i);parent=parents.get(i);anchor=parent if parent is not None and (names[parent] or '').startswith('SuspensionAnchor') else i
        wheels.append({'node':i,'name':n.name,'side':'left' if match[1]=='l' else 'right','roadWheel':True,'radius':float((hi[1]-lo[1])*.5),'suspensionNode':anchor,'center':model.translation(i).tolist()})
    tracks=[n.name for n in model.g.nodes if (n.name or '').startswith(('track_l','track_r')) and n.mesh is not None]
    count=len(wheels);weight=tank['weightTonnes']*1000
    gun=model.translation(names.index('Gun')).tolist();coax='Muzzle_Coax_SGMT' if 'Muzzle_Coax_SGMT' in names else 'Muzzle_Main'
    return {'format':1,'forward':'-Z','turret':{'node':names.index('Turret'),'pivot':model.translation(names.index('Turret')).tolist()},'gun':{'node':names.index('Gun'),'pivot':gun},'muzzle':{'position':model.translation(names.index('Muzzle_Main')).tolist()},'coaxMuzzle':{'position':model.translation(names.index(coax)).tolist()},'wheels':wheels,'tracks':tracks,'colliders':default_colliders(tank),'suspension':{'travel':.24,'restCompression':.12,'springPerWheel':weight*9.81/max(count,1)/.12,'damperPerWheel':18000.}}

def import_model(directory,path,bindings=None):
    """Import canonical GLB + rig. Explicit bindings rename canonical control nodes."""
    d=Path(directory);source=Path(path);m=Model(source)
    if bindings:
        used=set()
        for canonical,original in bindings.items():
            if canonical not in ['Hull','Turret','Gun','Barrel_Recoil']:raise ValueError('未知控制节点')
            found=[n for n in m.g.nodes if n.name==original]
            if len(found)!=1 or original in used:raise ValueError('绑定节点需要唯一且不能重复')
            used.add(original);found[0].name=canonical
    # A separate rig is needed when wheel/muzzle pivots differ; never inherit silently.
    sibling=source.with_name('rig.json')
    rig=json.loads(sibling.read_text()) if sibling.is_file() else infer_rig(m,read_documents(d)['tank'])
    with tempfile.TemporaryDirectory() as temp:
        work=Path(temp)/'project';shutil.copytree(d,work);m.save(work/'model.glb');(work/'rig.json').write_text(json.dumps(rig,indent=2)+'\n')
        r=validate_project(work)
        if not r['valid']:raise ValueError('; '.join(r['errors']))
        shutil.copyfile(work/'model.glb',d/'model.glb');shutil.copyfile(work/'rig.json',d/'rig.json')
    return r

def replace_texture(directory,material,image_path,slot='baseColor'):
    d=Path(directory);m=Model(d/'model.glb');matches=[x for x in m.g.materials if x.name==material]
    if len(matches)!=1:raise ValueError('材质名称不存在或不唯一')
    mat=matches[0]
    texture=mat.pbrMetallicRoughness.baseColorTexture if slot=='baseColor' else mat.normalTexture if slot=='normal' else None
    if texture is None:raise ValueError('材质没有此贴图槽；请在模型中建立对应材质槽')
    source=m.g.textures[texture.index].source
    # Copy-on-write prevents changing other material slots sharing this image.
    im=Image.open(image_path).convert('RGBA');im.thumbnail((2048,2048));data=io.BytesIO();im.save(data,format='PNG')
    m.blob.extend(b'\0'*((-len(m.blob))%4));offset=len(m.blob);m.blob.extend(data.getvalue())
    vi=len(m.g.bufferViews);m.g.bufferViews.append(BufferView(buffer=0,byteOffset=offset,byteLength=len(data.getvalue())))
    image=copy.deepcopy(m.g.images[source]);image.bufferView=vi;image.uri=None;image.mimeType='image/png';m.g.images.append(image)
    tex=copy.deepcopy(m.g.textures[texture.index]);tex.source=len(m.g.images)-1;m.g.textures.append(tex);texture.index=len(m.g.textures)-1
    temporary=d/'model-update.glb';m.save(temporary);os.replace(temporary,d/'model.glb')
    return validate_project(d)

def pack_project(directory,output):
    d=Path(directory);r=validate_project(d)
    if not r['valid']:raise ValueError('; '.join(r['errors']))
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            for name in FILES:z.write(d/name,name)
        os.replace(tmp,out)
    finally:
        if tmp.exists():tmp.unlink()
    return {'status':'packed','file':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),**r}

def generate_runtime_header(directories,destination):
    configs=[]
    for directory in directories:
        r=validate_project(directory)
        if not r['valid']:raise ValueError('; '.join(r['errors']))
        doc=read_documents(directory);m,t,w,a,rig=[doc[k] for k in ['manifest','tank','weapon','armor','rig']]
        wheels=[x for x in rig['wheels'] if x['roadWheel']];sus=rig['suspension']
        values=[m['id'],round(w['shells']['AP']['penetrationMm']),round(w['caliber']),round(w['muzzleVelocity']),math.ceil(w['reload']),w['reload']-math.ceil(w['reload']),round(t['enginePower']),round(t['maxForwardSpeed']),t['maxReverseSpeed']/3.6,round(t['turretRotation']),t['weightTonnes'],round(t['gunElevation']),round(abs(t['gunDepression'])),t['crew'],m['tier'],[a['body'][x] for x in ['front','side','side','rear']],[a['turret'][x] for x in ['front','side','side','rear']],[w['ammo'].get(x,0) for x in ['AP','HE','APCR','WP','HEAT']],w['machineGun']['ammo'],[w['shells'].get(x,{}).get('penetrationMm',0) for x in ['AP','HE','APCR','WP','HEAT']],len(wheels),sus['travel'],sus['restCompression'],sus['springPerWheel'],sus['damperPerWheel'],sum(x['radius'] for x in wheels)/len(wheels),t['dimensionsMeters']['length']*.62]
        magazine=w.get('magazine',{})
        values.extend([magazine.get('capacity',0),magazine.get('shotInterval',0),magazine.get('reloadTime',0)])
        def c(v):
            if isinstance(v,str):return json.dumps(v)
            if isinstance(v,list):return '{'+','.join(map(c,v))+'}'
            return str(v)
        configs.append('{'+','.join(map(c,values))+'}')
    text='''#pragma once
// Generated from validated project parameters. Never reuse with other resources.
typedef struct { const char *id; int penetration,caliber,speed,reload; float reload_offset; int power,max_speed; float reverse_speed; int turret_speed; float weight; int elevation,depression,crew,tier; int body_armor[4],turret_armor[4],ammo[5],mg_ammo,shell_penetration[5],wheel_count; float travel,rest,spring,damper,radius,track_length; int magazine_capacity; float shot_interval,magazine_reload; } CustomTank;
'''+('static const CustomTank custom_tanks[]={'+','.join(configs)+'};\n' if configs else 'static const CustomTank custom_tanks[1]={{0}};\n')+f'#define CUSTOM_TANK_COUNT {len(configs)}\n'
    Path(destination).write_text(text,encoding='utf-8')
    return hashlib.sha256(text.encode()).hexdigest()


