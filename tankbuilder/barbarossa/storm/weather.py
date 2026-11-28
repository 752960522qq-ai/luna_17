"""Camera-local rain volume, overcast stock sky, one bounded flash and a delayed thunder source per strike."""
import random,struct
from ...campaign_ugui import PTR
from ...enemy_assets import refs
from ...serialization import parse_complete as val,encode_complete
from ...unity_assets import pp,xyz
from ..mission.codec import part,update
from ..mission.interface import event
from .events import fixture,add_component,active,timer
from . import DEADLINE
from .lightning import sky_bolts
from .sound import VOLUME

STREAM='StormWeather.resource'
def color(r,g,b,a=1):return dict(r=r,g=g,b=b,a=a)
def constant(curve,x):curve.update(minMaxState=0,scalar=x,minScalar=x)
def strikes():
    rng=random.Random(19410626);sec=31;plan=[]
    while sec<DEADLINE-9:
        plan.append((sec, round(rng.uniform(.22,.46),2),round(rng.uniform(1.1,3.7),2),rng.choice(('crack','roll'))));sec+=rng.randint(41,76)
    return plan

def install(l,stock,shared,gui,side,clips,clock):
    sf=l.sf;root=next(p for p,o in sf.objects.items() if o.type.name=='GameObject' and o.peek_name()=='Barbarossa_Polesie_Summer');anchor=part(sf,root,'Transform')
    weather,wt=fixture(l,anchor,'Hatch Storm Weather');campos=val(sf.objects[part(sf,791,'Transform')])['m_LocalPosition']
    rain,rt=fixture(l,wt,'Hatch Storm Rain',True,(campos['x'],campos['y']+7,campos['z']));comp={}
    sky=pp(10,l.external('sharedassets1.assets'));assert gui.objects[10].peek_name()=='AllSky_Overcast3_High'
    rs=next(o for o in sf.objects.values() if o.type.name=='RenderSettings');cfg=val(rs)
    cfg.update(m_SkyboxMaterial=sky,m_Fog=True,m_FogMode=3,m_FogColor=color(.39,.445,.49),m_FogDensity=.00135,m_LinearFogStart=200.,m_LinearFogEnd=1100.,m_AmbientMode=1,m_AmbientIntensity=.68,m_AmbientSkyColor=color(.48,.54,.61),m_AmbientEquatorColor=color(.34,.39,.41),m_AmbientGroundColor=color(.22,.25,.24),m_ReflectionIntensity=.38)
    l.add(rs,rs.path_id,encode_complete(rs,cfg));sun=cfg['m_Sun']['m_PathID'];assert sf.objects[sun].type.name=='Light'
    light=sf.objects[sun];raw=bytearray(light.get_raw_data());assert len(raw)==276 and struct.unpack_from('<i',raw,16)==(1,)
    main_go=PTR.unpack_from(raw)[1];struct.pack_into('<5f',raw,20,.68,.755,.845,1.,.47);l.add(light,sun,bytes(raw))
    flash,ft=fixture(l,wt,'Hatch Storm Lightning',False);rot=val(sf.objects[part(sf,main_go,'Transform')])['m_LocalRotation'];update(sf,ft,m_LocalRotation=rot)
    fid=l.alloc();PTR.pack_into(raw,0,0,flash);struct.pack_into('<5f',raw,20,.82,.89,1.,1.,1.58);struct.pack_into('<i',raw,60,0);l.add(light,fid,bytes(raw));add_component(sf,flash,fid)
    # The original time-of-day controller writes the sky and fog after scene load. All of its presets must agree.
    gc=sf.objects[155115];b=bytearray(gc.get_raw_data());at=160
    for i in range(4):
        n=struct.unpack_from('<i',b,at)[0];assert n==(1,3,1,1)[i];at+=4
        for j in range(n):
            if i:PTR.pack_into(b,at,sky['m_FileID'],sky['m_PathID'])
            at+=12
    at+=12+16;assert struct.unpack_from('<i',b,at)[0]==3;at+=4
    for _ in range(3):struct.pack_into('<4f',b,at,.39,.445,.49,1.);at+=16
    struct.pack_into('<f',b,at,.00135);l.add(gc,gc.path_id,bytes(b))
    ps=stock.objects[147133];render=stock.objects[150046]
    def remap(q):
        if not q['m_PathID']:return pp()
        if not q['m_FileID']:return pp(rain) if q['m_PathID']==493 else pp()
        e=stock.externals[q['m_FileID']-1];return pp(q['m_PathID'],l.external(e.path,e))
    t=refs(val(ps),remap);t.update(m_GameObject=pp(rain),lengthInSec=5.,looping=True,prewarm=True,playOnAwake=True,moveWithTransform=1,useUnscaledTime=False,cullingMode=3)
    for m in t.values():
        if isinstance(m,dict) and 'enabled' in m:m['enabled']=False
    init=t['InitialModule'];init.update(enabled=True,maxNumParticles=920,size3D=False,rotation3D=False)
    for k,value in [('startLifetime',.94),('startSpeed',0.),('startSize',.046),('gravityModifier',0),('startRotation',0)]:constant(init[k],value)
    tint=color(.72,.81,.9,.44);init['startColor'].update(minMaxState=0,minColor=tint,maxColor=tint)
    sh=t['ShapeModule'];sh.update(enabled=True,type=5,m_Scale=xyz((31,4,36)),m_Position=xyz((0,0,0)),m_Rotation=xyz((0,0,0)))
    ve=t['VelocityModule'];ve.update(enabled=True,inWorldSpace=True)
    for k,x in [('x',-2.5),('y',-18.),('z',.8),('speedModifier',1)]:constant(ve[k],x)
    em=t['EmissionModule'];em.update(enabled=True,m_BurstCount=0,m_Bursts=[]);constant(em['rateOverTime'],880.);constant(em['rateOverDistance'],0.)
    pid=l.alloc();l.add(ps,pid,encode_complete(ps,t));add_component(sf,rain,pid)
    re=refs(val(render),remap);re.update(m_GameObject=pp(rain),m_Enabled=True,m_Materials=[pp(2,l.external('resources.assets'))],m_RenderMode=1,m_VelocityScale=.020,m_LengthScale=3.3,m_MaxParticleSize=.075,m_CastShadows=0,m_ReceiveShadows=False,m_CameraVelocityScale=0.0)
    rid=l.alloc();l.add(render,rid,encode_complete(render,re));add_component(sf,rain,rid)
    clip_src=shared.objects[145];audio=stock.objects[144403];sources={};clip_ids={}
    for name,i in clips.items():
        clip=l.alloc();ct=val(clip_src);ct.update(m_Name='Storm '+name,m_LoadType=0,m_Channels=1,m_Frequency=24000,m_BitsPerSample=16,m_Length=i['seconds'],m_LoadInBackground=False,m_PreloadAudioData=True,m_CompressionFormat=0,m_Resource=dict(m_Source=STREAM,m_Offset=i['offset'],m_Size=i['size']));l.add(clip_src,clip,encode_complete(clip_src,ct));clip_ids[name]=clip
        go,_=fixture(l,wt,'Hatch Storm Audio '+name);ai=l.alloc();au=refs(val(audio),remap);au.update(m_GameObject=pp(go),m_Enabled=True,m_audioClip=pp(clip),m_Resource=pp(clip),Loop=name=='rain',m_PlayOnAwake=name=='rain',m_Volume=VOLUME[name],DopplerLevel=0.,Spatialize=False,Priority=145 if name=='rain' else 120)
        for key in au['panLevelCustomCurve']['m_Curve']:key['value']=0.
        l.add(audio,ai,encode_complete(audio,au));add_component(sf,go,ai);sources[name]=ai
    bolts=sky_bolts(l,wt,side);log=[]
    for sec,dur,delay,sample in strikes():
        bolt=bolts[len(log)%len(bolts)]['root']
        a=timer(l,side.scenario,sec,[active(flash,True),active(bolt,True)],clock);b=timer(l,side.scenario,sec+dur,[active(flash,False),active(bolt,False)],clock);c=timer(l,side.scenario,sec+delay,[event(sources[sample],'UnityEngine.AudioSource, UnityEngine.AudioModule','Play')],clock)
        log.append(dict(second=sec,flashSeconds=dur,thunderDelay=delay,sample=sample,bolt=bolt,timers=[a,b,c]))
    return dict(root=weather,rain=rain,rainTransform=rt,particles=pid,renderer=rid,flash=flash,light=fid,sun=sun,ambient=sources,clips=clip_ids,strikes=log,bolts=bolts,sky=sky)
