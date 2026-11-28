"""Original rain and distant thunder, encoded as Unity-native, uncompressed single-subsound FMOD banks."""
import hashlib,struct,wave
import numpy as np
from scipy.signal import butter,sosfilt

RATE=24000

def sounds():
    rng=np.random.default_rng(194107);out={}
    def band(x,lo,hi):
        f=sosfilt(butter(3,[lo,hi],fs=RATE,btype='bandpass',output='sos'),x)
        return f/max(np.std(f),1e-8)
    def pcm(x,vol):return np.asarray(np.clip(x*vol/max(np.max(np.abs(x)),1e-8),-1,1)*32767,dtype='<i2')
    n=RATE*16;w=rng.normal(size=n+RATE);t=np.arange(len(w))/RATE
    a=.55*band(w,280,2300)+.51*band(rng.normal(size=len(w)),2400,8400)
    a*=.88+.07*np.sin(t*np.pi*.54)+.05*np.sin(t*np.pi*1.1)
    # Wet canopy patter; blend the tail into the head for a click-free ambient loop.
    for x in rng.integers(0,len(a)-700,800):
        k=np.arange(440)/RATE;a[x:x+len(k)]+=rng.uniform(.2,1.3)*np.sin(2*np.pi*rng.uniform(950,3400)*k)*np.exp(-k*205)
    fade=np.linspace(0,1,RATE,endpoint=False);a[:RATE]=a[n:]* (1-fade)+a[:RATE]*fade
    out['rain']=pcm(a[:n],.75)
    for j,(name,length) in enumerate([('roll',7),('crack',5)]):
        t=np.arange(RATE*length)/RATE;noise=rng.normal(size=len(t));v=np.zeros_like(t)
        for at,strength,decay in [(0,.92,.82),(.13,.7,.9),(.45,.48,1.05),(.89,.35,1.1),(1.65,.23,.97)]:
            q=np.maximum(0,t-at);v+=strength*(1-np.exp(-q/(.032 if not j else .012)))*np.exp(-q/decay)
        low=band(noise,31,135)+.55*band(rng.normal(size=len(t)),105,380)
        y=low*v+(.3+.52*j)*band(noise,430,2200)*(1-np.exp(-t*100))*np.exp(-t*(2.3+j));y*=np.minimum(1,(length-t)/.55)
        out[name]=pcm(y,.90)
    return out

def bank(data):
    pcm=data.tobytes();pad=bytes(-len(pcm)%32);sample=struct.pack('<Q',(len(data)<<34)|(6<<1));sample+=bytes(16-len(sample))
    return struct.pack('<4s6I',b'FSB5',1,1,len(sample),0,len(pcm)+len(pad),2)+bytes(8)+hashlib.md5(pcm).digest()+bytes(8)+sample+pcm+pad

def write_banks(path):
    clips=sounds();data=bytearray();res={}
    for name,arr in clips.items():
        data+=bytes(-len(data)%32);raw=bank(arr);res[name]={'offset':len(data),'size':len(raw),'seconds':len(arr)/RATE};data+=raw
    path.write_bytes(data);return res

def preview(path):
    clips=sounds();rain=clips['rain'].astype(float)/32768;t=np.tile(rain,2)[:24*RATE]*.36
    for name,sec in [('roll',4.8),('crack',16.1)]:
        q=clips[name].astype(float)/32768;start=int(sec*RATE);t[start:start+len(q)]+=q*(.65 if name=='roll' else .55)
    t[:RATE//2]*=np.linspace(0,1,RATE//2);t[-RATE:]*=np.linspace(1,0,RATE)
    with wave.open(str(path),'wb') as f:f.setparams((1,2,RATE,0,'NONE',''));f.writeframes((np.clip(t,-1,1)*32767).astype('<i2').tobytes())
