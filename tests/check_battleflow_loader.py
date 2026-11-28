"""Run the actual Java loadTank bytecode with each APK's own parsed manifest.
Android's JSONObject view and native bridge are substituted on this host."""
import argparse,io,json,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def jar(z,n):return zipfile.ZipFile(io.BytesIO(z.read(n)))
def check(previous,current,classes,android):
    with tempfile.TemporaryDirectory() as t:
        w=Path(t);src=w/'src';cp=str(classes)+':'+str(classes.parent/'interfaces')+':'+str(android)
        def source(path,s):
            p=src/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s);return p
        obj=source('org/json/JSONObject.java','''package org.json;import java.io.*;import java.util.*;
        public class JSONObject {Properties p;String key;public JSONObject(String file)throws Exception{p=new Properties();try(FileReader f=new FileReader(file)){p.load(f);}key="";}JSONObject(Properties p,String k){this.p=p;key=k;}
        public JSONObject optJSONObject(String k){for(String a:p.stringPropertyNames())if(a.startsWith(key+k+"."))return new JSONObject(p,key+k+".");return null;}
        public String getString(String k){return p.getProperty(key+k);}public String optString(String k,String def){return p.getProperty(key+k,def);}
        public boolean has(String k){return p.containsKey(key+k);}public int getInt(String k){return Integer.parseInt(getString(k));}public double getDouble(String k){return Double.parseDouble(getString(k));}
        public boolean optBoolean(String k,boolean v){return Boolean.parseBoolean(optString(k,""+v));}}''')
        nb=source('com/luna17/aot/NativeBridge.java','''package com.luna17.aot;class NativeBridge{static boolean held;static int clip;static float interval,full;
        static void clearTankConfiguration(){}static boolean configureFilling(String id,float[]v,int m){return true;}
        static boolean configureContinuousFire(String id,boolean h,boolean u){held=h;return true;}
        static boolean configureMagazine(String id,int n,float i,float f){clip=n;interval=i;full=f;return true;} static String loadHatch(String file){return "";}}''')
        cs=source('com/luna17/aot/CampaignSupport.java','''package com.luna17.aot; class CampaignSupport{static boolean controlsFire(){return true;}static void registerVehicle(String id){} static void setAim(boolean a){} static void start(android.app.Activity a){} static void stop(){}}''')
        run=source('com/luna17/aot/Check.java','''package com.luna17.aot;import java.io.*;public class Check{public static void main(String[] a)throws Exception{
        String e=new TankInvincibleModule().loadTank(new File("runtime.bin"),a[0]);boolean ok=NativeBridge.held&&NativeBridge.clip==10&&NativeBridge.interval==.4f&&NativeBridge.full==4.85f;
        if(!e.isEmpty()||ok!=Boolean.parseBoolean(a[1]))throw new AssertionError(e+" "+ok);
        System.out.println("held="+NativeBridge.held+" clip="+NativeBridge.clip+" interval="+NativeBridge.interval+" reload="+NativeBridge.full);}}''')
        # Compile dependencies against the released SDK; host test doubles are loaded first at runtime.
        for old,package in ((True,previous),(False,current)):
            dest=w/('old' if old else 'new');dest.mkdir()
            if old:
                subprocess.run(['java','com.sun.tools.javac.Main','-cp',cp,'-d',dest,cs],check=True)
                module=source('archive/com/luna17/aot/TankInvincibleModule.java',subprocess.check_output(['git','show','1fc1270a:mods/tankinvincible/src/com/luna17/aot/TankInvincibleModule.java'],cwd=ROOT,text=True))
                subprocess.run(['java','com.sun.tools.javac.Main','-cp',str(dest)+':'+cp,'-d',dest,module],check=True)
            # Compile the runner against the actual TankInvincibleModule, then load captured Bridge instead.
            subprocess.run(['java','com.sun.tools.javac.Main','-cp',str(dest)+':'+cp,'-d',dest,obj,nb,cs,run],check=True)
            with zipfile.ZipFile(package) as z:
                for tank in ('Panzer_II_Ausf_L','Panzer_II_Ausf_F'):
                    with jar(z,'assets/Hatch/mods/'+tank+'.hatch') as h:doc=json.loads(h.read('hatch.json'))
                    def flat(v,k=''):
                        for a,b in v.items():
                            if isinstance(b,dict):yield from flat(b,k+a+'.')
                            elif isinstance(b,(bool,str,int,float)):yield k+a+'='+str(b).replace('\n',' ').lower() if isinstance(b,bool) else k+a+'='+str(b).replace('\n',' ')
                    props=w/'manifest.properties';props.write_text('\n'.join(flat(doc)))
                    expected=not(old and tank.endswith('_F'))
                    print(('previous' if old else 'fixed'),tank,end=': ',flush=True)
                    subprocess.run(['java','-cp',str(dest)+':'+cp,'com.luna17.aot.Check',props,str(expected).lower()],check=True)
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for key in ('previous','current','classes','android'):p.add_argument('--'+key,required=True,type=Path)
 check(**{k:v.resolve() for k,v in vars(p.parse_args()).items()})
