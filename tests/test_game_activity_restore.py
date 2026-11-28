"""Run the shipped Java lifecycle and campaign loop with deterministic Android and Unity queues."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
D = {
    "android/os/Bundle": "package android.os; public class Bundle {}",
    "android/os/Looper": "package android.os; public class Looper { public static Looper getMainLooper(){ return null; } }",
    "android/os/SystemClock": "package android.os; public class SystemClock {public static long uptimeMillis(){return Handler.now;}}",
    "android/os/Handler": """package android.os; import java.util.*;
    public class Handler {
        public static long now;
        private static final TreeMap<Long,List<Runnable>> jobs=new TreeMap<>();
        public Handler(Looper l) {}
        public void post(Runnable r){postDelayed(r,0);}
        public void postDelayed(Runnable r,long d){jobs.computeIfAbsent(now+d,i->new ArrayList<>()).add(r);}
        public void removeCallbacks(Runnable r){for(List<Runnable> list:jobs.values())list.removeIf(x->x==r);}
        public static void advance(long d){ long end=now+d;
          while(!jobs.isEmpty()&&jobs.firstKey()<=end){now=jobs.firstKey();for(Runnable r:jobs.pollFirstEntry().getValue())r.run();}
          now=end;
        }
    }""",
    "android/content/Intent": "package android.content; public class Intent {}",
    "android/content/SharedPreferences": """package android.content; public interface SharedPreferences {
        int getInt(String k,int d); String getString(String k,String d); Editor edit();
        interface Editor { Editor putInt(String k,int n); Editor putString(String k,String v); Editor remove(String k); boolean commit(); }
    }""",
    "android/app/Activity": """package android.app; import android.view.*; import android.os.*; import android.content.Intent;
    public class Activity {
       boolean destroyed; public boolean isDestroyed(){return destroyed;} public boolean isFinishing(){return false;}
       public void runOnUiThread(Runnable r){new Handler(null).post(r);}
       protected void onCreate(Bundle b){} public void reportFullyDrawn(){} protected void onResume(){} protected void onPause(){}
       public void onWindowFocusChanged(boolean f){} protected void onDestroy(){destroyed=true;}
       protected void onActivityResult(int r,int c,Intent i){} protected void onUserLeaveHint(){}
       public boolean dispatchTouchEvent(MotionEvent e){return true;} public boolean dispatchKeyEvent(KeyEvent e){return true;}
    }""",
    "android/view/View": "package android.view; public class View {public ViewGroup parent; public Object getParent(){return parent;}}",
    "android/view/ViewGroup": "package android.view; public class ViewGroup extends View {public void removeView(View v){v.parent=null;}}",
    "android/view/MotionEvent": "package android.view; public class MotionEvent {public static final int ACTION_UP=1;public int getActionMasked(){return ACTION_UP;}}",
    "android/view/KeyEvent": "package android.view; public class KeyEvent {public static final int ACTION_UP=1,KEYCODE_BACK=4;public int getAction(){return ACTION_UP;}public int getKeyCode(){return 23;}}",
    "android/util/Log": "package android.util; public class Log {public static int e(String tag,String s,Throwable t){throw new AssertionError(s,t);}}",
    "android/widget/Toast": """package android.widget; import android.app.Activity; public class Toast {
       public static int shown; public static final int LENGTH_SHORT=0;
       public static Toast makeText(Activity a,String s,int n){return new Toast();} public void show(){shown++;}
    }""",
    "com/unity3d/player/UnityPlayerForActivityOrService": """package com.unity3d.player; import java.util.*;
       public class UnityPlayerForActivityOrService {
         public final Queue<Runnable> jobs=new ArrayDeque<>();
         public void invokeOnMainThread(Runnable job){jobs.add(job);}
         public void frame(){for(Runnable r;(r=jobs.poll())!=null;)r.run();}
       }""",
    "com/unity3d/player/UnityPlayerActivity": """package com.unity3d.player;
       import com.hatch.loader.HatchLoader; import android.os.Bundle;
       public class UnityPlayerActivity extends android.app.Activity {
         protected UnityPlayerForActivityOrService mUnityPlayer;
         public UnityPlayerForActivityOrService player(){return mUnityPlayer;}
         protected void onCreate(Bundle b){
           if(!HatchLoader.prepared)throw new AssertionError("Unity constructed before preload");
           mUnityPlayer=new UnityPlayerForActivityOrService();
         }
       }""",
    "com/hatch/loader/HatchLoader": """package com.hatch.loader; import android.app.Activity; import android.view.*; import com.luna17.campaign.CampaignLoop;
       public class HatchLoader {
         static int starts, confirmations, diagnostics; static Activity owner; public static boolean prepared; static View last;
         static String prepareForUnity(Activity a){prepared=true;return null;}
         static void start(Activity a){ starts++; owner=a; CampaignLoop.start(a); }
         static void stop(Activity a){if(owner==a){owner=null;CampaignLoop.stop();}}
         static void confirmStartup(Activity a){if(owner==a)confirmations++;}
         static View startupDiagnostic(Activity a){diagnostics++;last=new View();last.parent=new ViewGroup();return last;}
         static boolean result(Activity a,int r,int c,android.content.Intent i){return false;}
       }""",
    "com/hatch/loader/LifecycleRun": """package com.hatch.loader;
       import android.os.*; import android.view.*; import android.content.SharedPreferences; import java.util.*;
       import com.luna17.campaign.CampaignLoop;
       public class LifecycleRun {
         static void check(boolean b,String s){if(!b)throw new AssertionError(s);}
         static class Prefs implements SharedPreferences,SharedPreferences.Editor {
           Map<String,Object> m=new HashMap<>();
           public int getInt(String k,int d){return (Integer)m.getOrDefault(k,d);}
           public String getString(String k,String d){return (String)m.getOrDefault(k,d);}
           public Editor edit(){return this;}public Editor putInt(String k,int v){m.put(k,v);return this;}
           public Editor putString(String k,String v){m.put(k,v);return this;}
           public Editor remove(String k){m.remove(k);return this;} public boolean commit(){return true;}
         }
         public static void main(String[] args){
           String mode=args[0]; if(mode.equals("history")){
             Prefs p=new Prefs();
             StartupHistory h=new StartupHistory(p); check(!h.recovery,"first cold boot"); h.stage("waiting");
             h=new StartupHistory(p); check(!h.recovery,"second boot");h.stage("engine");
             h=new StartupHistory(p);check(h.recovery&&h.previousStage.equals("engine"),"third boot/reason");
             h.confirm();h=new StartupHistory(p);check(!h.recovery,"normal launch after recovery");
             h.requestRecovery();h.confirm();h=new StartupHistory(p);check(h.recovery,"manual recovery survived late draw");
             return;
           }
           HatchGameActivity a=mode.equals("restored")?new HatchGameActivity():new HatchActivity();
           a.onCreate(new Bundle());check(a.player()!=null&&HatchLoader.starts==0,"must wait for draw");
           a.onWindowFocusChanged(true);
           if(mode.equals("destroyed")){
             a.reportFullyDrawn();a.onDestroy();Handler.advance(60000);
             check(HatchLoader.starts==0&&HatchLoader.diagnostics==0,"stale callback attached a destroyed window");return;
           }
           if(mode.equals("slow")){
             a.onResume();Handler.advance(44000);check(HatchLoader.diagnostics==0,"diagnostic too early");
             a.onPause();Handler.advance(60000);check(HatchLoader.diagnostics==0,"background popup");
             a.onResume();Handler.advance(90000);check(HatchLoader.diagnostics==1&&HatchLoader.starts==0,"single wait button");
             a.reportFullyDrawn();Handler.advance(0);check(HatchLoader.last.parent==null&&HatchLoader.starts==1,"late draw removes diagnostic");return;
           }
           if(mode.equals("restored")){
             a.reportFullyDrawn();Handler.advance(0);check(HatchLoader.starts==0,"background window attached early");
             a.onResume();
           } else {
             a.onResume();a.dispatchTouchEvent(new MotionEvent());Handler.advance(1000);
             check(a.frameSession()==0&&HatchLoader.starts==0,"splash input must not arm the campaign");
             a.reportFullyDrawn();Handler.advance(0);
           }
           a.reportFullyDrawn();Handler.advance(0);a.onPause();a.onResume();Handler.advance(1200);
           check(HatchLoader.starts==1&&a.player().jobs.isEmpty(),"duplicate menu or scene work before input");
           if(mode.equals("frames")){
             a.dispatchTouchEvent(new MotionEvent());Handler.advance(2000);
             check(a.player().jobs.size()==1&&CampaignLoop.current()==0,"too many pending tasks / ran on Android UI");
             a.onPause();a.player().frame();check(CampaignLoop.current()==0,"stale paused frame");
             a.onResume();Handler.advance(500);a.onWindowFocusChanged(false);a.onWindowFocusChanged(true);
             a.player().frame();check(CampaignLoop.current()==0,"stale focus generation");
             Handler.advance(500);a.player().frame();check(CampaignLoop.current()==6,"campaign feedback did not resume");
             Handler.advance(500);a.onDestroy();a.player().frame();
             check(CampaignLoop.current()==0&&android.widget.Toast.shown==0,"dead window called native or repeated toast");
           } else {
             Handler.advance(10000);check(HatchLoader.confirmations>0,"healthy launch never confirmed");
             a.dispatchKeyEvent(new KeyEvent());check(a.frameSession()!=0,"controller cannot activate campaign");
           }
         }
       }""",
}


class BootLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        for name, body in D.items():
            p = cls.out / (name + ".java")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        actual = [ROOT / "loader/src/com/hatch/loader" / (n + ".java") for n in
                  ("HatchGameActivity", "HatchActivity", "GameFrameHost", "StartupHistory")]
        campaign = ROOT / "campaign-runtime/java/com/luna17/campaign"
        subprocess.run(["java", "com.sun.tools.javac.Main", "-source", "8", "-target", "8", "-Xlint:-options",
                        "-d", cls.out, *actual, campaign / "FramePump.java", campaign / "CampaignLoop.java",
                        *cls.out.rglob("*.java")], check=True)
        # A test JNI callback returns a fixed in-game message. No Unity/game binary is executed.
        subprocess.run(["cc", "-shared", "-fPIC", "-x", "c", "-", "-o", cls.out / "libhatchcampaign.so"],
                       input="""int Java_com_luna17_campaign_CampaignLoop_step(void *e, void *c){return 6;}
int Java_com_luna17_campaign_CampaignLoop_extraSide(void *e, void *c){return 1;}
unsigned char Java_com_luna17_campaign_CampaignLoop_postMessage(void *e, void *c, void *s,int n){return 1;}
unsigned char Java_com_luna17_campaign_CampaignLoop_sample(void *e, void *c,void *a,int p,unsigned char aim){return 0;}""", text=True, check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_case(self, case):
        subprocess.run(["java", "-Djava.library.path=" + str(self.out), "-cp", self.out,
                        "com.hatch.loader.LifecycleRun", case], check=True)

    def test_launcher(self): self.run_case("launcher")
    def test_restored_task(self): self.run_case("restored")
    def test_destroyed_before_draw_callback(self): self.run_case("destroyed")
    def test_slow_draw_diagnostic(self): self.run_case("slow")
    def test_campaign_uses_interactive_frames(self): self.run_case("frames")
    def test_recovery_requires_two_interrupted_processes(self): self.run_case("history")


if __name__ == "__main__":
    unittest.main()
