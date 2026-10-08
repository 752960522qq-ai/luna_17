"""Run the production native host, bridge and session on a real JVM/JNI library.

Two child URLClassLoaders use the same prerequisite library through the parent.
The native fixture includes the production RegisterNatives table, with test
implementations of the game operations. Android linker behavior still needs
an Android device run.
"""
import argparse
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

FIXTURE=r'''
#include <jni.h>
static int failed;
JNIEXPORT void JNICALL Java_com_luna17_aot_NativeBridge_init(JNIEnv *e,jclass c){(void)c; jclass system=(*e)->FindClass(e,"java/lang/System");jmethodID get=(*e)->GetStaticMethodID(e,system,"getProperty","(Ljava/lang/String;)Ljava/lang/String;");jstring key=(*e)->NewStringUTF(e,"fixture.fail");failed=(*e)->CallStaticObjectMethod(e,system,get,key)!=0;}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_state(JNIEnv *e,jclass c){return failed?-1:2;}
JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_initError(JNIEnv *e,jclass c){return (*e)->NewStringUTF(e,"first startup failure: IL2CPP namespace lookup");}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_toggle(JNIEnv *e,jclass c,jint id,jboolean on){return on;}
JNIEXPORT jobjectArray JNICALL Java_com_luna17_aot_NativeBridge_tanks(JNIEnv *e,jclass c,jint nation){jclass s=(*e)->FindClass(e,"java/lang/String");return (*e)->NewObjectArray(e,0,s,0);}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_switchTank(JNIEnv *e,jclass c,jint nation,jint index){return JNI_TRUE;}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_switchResult(JNIEnv *e,jclass c){return 7;}
JNIEXPORT jobjectArray JNICALL Java_com_luna17_aot_NativeBridge_enemyTanks(JNIEnv *e,jclass c,jint nation){jclass s=(*e)->FindClass(e,"java/lang/String");return (*e)->NewObjectArray(e,0,s,0);}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_spawnEnemy(JNIEnv *e,jclass c,jint nation,jint index){return JNI_TRUE;}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_spawnEnemyResult(JNIEnv *e,jclass c){return 1;}
JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_loadHatch(JNIEnv *e,jclass c,jstring path){return (*e)->NewStringUTF(e,"");}
JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_hatchError(JNIEnv *e,jclass c){return (*e)->NewStringUTF(e,"");}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_configureMagazine(JNIEnv *e,jclass c,jstring id,jint cap,jfloat interval,jfloat reload){return cap>=2;}
#include "jni_module_host.h"
'''

JAVA={
'android/app/Activity.java':'package android.app; public class Activity {}',
'com/luna17/aot/Probe.java':'''package com.luna17.aot;
public class Probe {public static void start(String path){NativeBridge.start(path);} public static boolean ready(){return NativeBridge.loaded;} public static boolean library(){return NativeBridge.libraryLoaded;} public static String error(){return NativeBridge.error;} public static int value(){return NativeBridge.switchResult();} public static void operations(){
if(!NativeBridge.toggle(0,true)||NativeBridge.tanks(0).length!=0||!NativeBridge.switchTank(0,0)||NativeBridge.enemyTanks(0).length!=0||!NativeBridge.spawnEnemy(0,0)||NativeBridge.spawnEnemyResult()!=1||!NativeBridge.loadHatch("unused").isEmpty()||!NativeBridge.hatchError().isEmpty()||!NativeBridge.configureMagazine("fixture",2,.1f,1.f))throw new AssertionError("Native signature mismatch");}}
''',
'com/hatch/loader/ModuleRun.java':'''package com.hatch.loader;
import java.io.File; import java.net.URLClassLoader; import java.net.URL; import java.lang.reflect.Method; import android.app.Activity;
public class ModuleRun {
static void check(boolean value){if(!value)throw new AssertionError();}
static Class<?> child(String directory)throws Exception {return new URLClassLoader(new URL[]{new File(directory).toURI().toURL()},ModuleRun.class.getClassLoader()).loadClass("com.luna17.aot.Probe");}
static Object call(Class<?> c,String method)throws Exception{return c.getMethod(method).invoke(null);}
static void begin(Class<?> c,String path)throws Exception{c.getMethod("start",String.class).invoke(null,path);}
static class Stub implements HatchModule {int calls;final boolean fail;Stub(boolean fail){this.fail=fail;}public int apiVersion(){return 2;}public void prepare(File library){calls++;if(fail)throw new IllegalStateException("first failure");}public void start(Activity a,File f){}public String loadTank(File f,String s){return "";}public void stop(){}}
public static void main(String[] args)throws Exception {
String mode=args[0];
if(mode.equals("two_loaders")) {Class<?> a=child(args[1]),b=child(args[1]);check(a!=b&&a.getClassLoader()!=b.getClassLoader());begin(a,args[2]);begin(b,args[2]);check((Boolean)call(a,"ready")&&(Boolean)call(b,"ready"));check((Integer)call(a,"value")==7&&(Integer)call(b,"value")==7);call(a,"operations");call(b,"operations");begin(a,args[2]);check((Boolean)call(a,"ready"));}
if(mode.equals("bridge_failure")){System.setProperty("fixture.fail","yes");Class<?> a=child(args[1]);begin(a,args[2]);String original=(String)call(a,"error");check((Boolean)call(a,"library")&&!(Boolean)call(a,"ready")&&original.contains("first startup failure"));System.clearProperty("fixture.fail");begin(a,args[2]);check(original.equals(call(a,"error"))&&!(Boolean)call(a,"ready"));}
if(mode.equals("different_path")){Class<?> a=child(args[1]),b=child(args[1]);begin(a,args[2]);begin(b,args[2]+".changed");check((Boolean)call(a,"ready")&&!(Boolean)call(b,"ready"));check(((String)call(b,"error")).contains("更新后需完全退出"));}
if(mode.startsWith("session")){ModuleSession s=new ModuleSession();Stub stub=new Stub(mode.equals("session_failure"));int[] created={0};ModuleSession.Factory f=()->{created[0]++;return new ModuleSession.Loaded(stub,new File(args[2]),ModuleRun.class.getClassLoader());};if(stub.fail){String first=null;try{s.prepare(f);}catch(Exception e){first=e.getMessage();}check("first failure".equals(first));try{s.prepare(f);throw new AssertionError();}catch(IllegalStateException e){check(e.getCause()!=null&&e.getCause().getMessage().equals(first));}}else{check(s.prepare(f)==s.prepare(f));}check(created[0]==1&&stub.calls==1);}
System.out.println(mode+": passed");}}
'''
}
class ModuleLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.path=Path(cls.temp.name);src=cls.path/'src';cls.parent=cls.path/'parent';cls.child=cls.path/'child'
        for name,text in JAVA.items():
            f=src/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
        parent_sources=[src/'android/app/Activity.java',src/'com/hatch/loader/ModuleRun.java']+[ROOT/'loader/src/com/hatch/loader'/name for name in ['NativeHost.java','ModuleSession.java','HatchModule.java']]
        subprocess.run(['java','com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-d',str(cls.parent),*map(str,parent_sources)],check=True)
        subprocess.run(['java','com.sun.tools.javac.Main','--release','8','-encoding','UTF-8','-cp',str(cls.parent),'-d',str(cls.child),str(src/'com/luna17/aot/Probe.java'),str(ROOT/'mods/tankinvincible/src/com/luna17/aot/NativeBridge.java')],check=True)
        fixture=cls.path/'fixture.c';fixture.write_text(FIXTURE);cls.library=cls.path/'module.so'
        subprocess.run(['gcc','-shared','-fPIC','-O2','-I'+str(Path(ARGS.jni_include).resolve()),'-I'+str(ROOT/'native'),str(fixture),'-o',str(cls.library)],check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def execute(self,case):subprocess.run(['java','-cp',str(self.parent),'com.hatch.loader.ModuleRun',case,str(self.child),str(self.library)],check=True,capture_output=True,text=True)
    def test_two_real_class_loaders_share_parent_native_library(self):self.execute('two_loaders')
    def test_loaded_library_and_failed_initialization_are_separate(self):self.execute('bridge_failure')
    def test_different_library_path_requires_restart(self):self.execute('different_path')
    def test_session_success_initializes_only_once(self):self.execute('session_success')
    def test_session_failure_preserves_loader_and_first_cause(self):self.execute('session_failure')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--jni-include',required=True)
    ARGS,rest=p.parse_known_args();unittest.main(argv=['module-loading']+rest,verbosity=2)
