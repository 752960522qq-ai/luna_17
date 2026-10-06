"""Run the real launch-gate Java class on a JVM with Android lifecycle doubles.

Also validate the binary manifest transformation against the input APK.
This does not replace an Android/Unity device run.
"""
import argparse
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys
from loguru import logger
logger.disable('androguard')
from androguard.core.axml import AXMLPrinter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from repack import patch_manifest

DOUBLES={
'android/os/Bundle.java':'package android.os; public class Bundle {}',
'android/content/Intent.java':'package android.content; public class Intent { public final Class<?> target; public Intent(Object from,Class<?> target){this.target=target;} }',
'android/widget/TextView.java':'package android.widget; public class TextView { public TextView(Object a){} public void setText(String s){} public void setPadding(int a,int b,int c,int d){} }',
'android/app/Activity.java':'''package android.app;
import android.content.Intent; import android.os.Bundle;
public class Activity { public boolean destroyed,finishing,created; public int launches; public Intent launched;
protected void onCreate(Bundle b){created=true;} public void setContentView(Object v){}
public boolean isFinishing(){return finishing;} public boolean isDestroyed(){return destroyed;}
public void startActivity(Intent i){if(!created)throw new AssertionError("Missing super.onCreate"); launches++; launched=i;} public void finish(){finishing=true;}
}''',
'android/app/AlertDialog.java':'''package android.app;
public class AlertDialog { public static int shown; public interface Click {void click(Object d,int w);}
public static class Builder {public Builder(Object a){} public Builder setTitle(String s){return this;} public Builder setMessage(String s){return this;} public Builder setCancelable(boolean b){return this;} public Builder setPositiveButton(String s,Click c){return this;} public void show(){shown++;}}
}''',
'com/hatch/loader/HatchLoader.java':'''package com.hatch.loader;
public class HatchLoader {interface Prepared {void complete(String failure);} static Prepared pending;
static void prepare(Object a,Prepared p){pending=p;}}
''',
'com/hatch/loader/HatchGameActivity.java':'package com.hatch.loader; public class HatchGameActivity {}',
'com/hatch/loader/StartupRun.java':'''package com.hatch.loader;
import android.app.AlertDialog; import android.os.Bundle;
public class StartupRun {
static void check(boolean condition){if(!condition)throw new AssertionError();}
public static void main(String[] args){
HatchActivity a=new HatchActivity(); a.onCreate(new Bundle());
check(a.created && a.launches==0 && !a.finishing);
if(args[0].equals("success")){HatchLoader.pending.complete(null);check(a.launches==1 && a.finishing && a.launched.target==HatchGameActivity.class);}
if(args[0].equals("failure")){HatchLoader.pending.complete("native init failed");check(a.launches==0 && AlertDialog.shown==1);}
if(args[0].equals("destroyed")){a.destroyed=true;HatchLoader.pending.complete(null);check(a.launches==0 && AlertDialog.shown==0);}
if(args[0].equals("finishing")){a.finish();HatchLoader.pending.complete(null);check(a.launches==0 && AlertDialog.shown==0);}
System.out.println(args[0]+": passed");}}
''',
}

class Startup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.path=Path(cls.temp.name)
        for name,content in DOUBLES.items():
            p=cls.path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        gate=cls.path/'com/hatch/loader/HatchActivity.java'
        gate.write_text((ROOT/'loader/src/com/hatch/loader/HatchActivity.java').read_text())
        subprocess.run(['java','com.sun.tools.javac.Main','--release','8','-d',str(cls.path),*[str(p) for p in cls.path.rglob('*.java')]],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def run_path(self,path):
        subprocess.run(['java','-cp',str(self.path),'com.hatch.loader.StartupRun',path],check=True,capture_output=True,text=True)
    def test_delayed_success_opens_game_once(self):self.run_path('success')
    def test_init_failure_never_opens_unity(self):self.run_path('failure')
    def test_destroyed_gate_never_opens_game(self):self.run_path('destroyed')
    def test_finishing_gate_never_opens_game(self):self.run_path('finishing')
    def test_manifest_retains_unity_config_and_blocks_direct_entry(self):
        with zipfile.ZipFile(ARGS.source) as z:original=z.read('AndroidManifest.xml')
        binary=patch_manifest(original,launcher='com.hatch.loader.HatchActivity',label='突击坦克 · 舱盖',game_activity='com.hatch.loader.HatchGameActivity',old_launchers=('com.unity3d.player.UnityPlayerActivity','com.luna17.aot.ModActivity'))
        ns='{http://schemas.android.com/apk/res/android}'
        activities=AXMLPrinter(binary).get_xml_obj().find('application').findall('activity')
        gate=next(a for a in activities if a.attrib[ns+'name']=='com.hatch.loader.HatchActivity')
        game=next(a for a in activities if a.attrib[ns+'name']=='com.hatch.loader.HatchGameActivity')
        self.assertEqual(len(gate.findall('intent-filter')),1)
        self.assertEqual(len(game.findall('intent-filter')),0)
        self.assertEqual(game.attrib[ns+'exported'],'false')
        for key in ['screenOrientation','configChanges','launchMode']:
            self.assertEqual(game.attrib[ns+key],gate.attrib[ns+key])
        self.assertEqual([m.attrib for m in game.findall('meta-data')],[m.attrib for m in gate.findall('meta-data')])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',required=True)
    ARGS,rest=p.parse_known_args();unittest.main(argv=['startup']+rest,verbosity=2)
