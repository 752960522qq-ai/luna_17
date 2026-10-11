"""Run the production Android utterance player with media/scheduler boundary doubles."""
import shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
STUBS={
'android/media/AudioAttributes.java':'''package android.media;public class AudioAttributes {public static int USAGE_GAME=14,CONTENT_TYPE_SPEECH=1;public static class Builder {public Builder setUsage(int n){return this;}public Builder setContentType(int n){return this;}public AudioAttributes build(){return new AudioAttributes();}}}''',
'android/media/MediaPlayer.java':'''package android.media;import java.util.*;public class MediaPlayer {public interface OnPreparedListener{void onPrepared(MediaPlayer p);}public interface OnCompletionListener{void onCompletion(MediaPlayer p);}public interface OnErrorListener{boolean onError(MediaPlayer p,int a,int b);}public static List<String> played=new ArrayList<>();public static MediaPlayer live;String file;OnPreparedListener prepared;OnCompletionListener completed;OnErrorListener error;public void setAudioAttributes(AudioAttributes a){}public void setDataSource(String s){file=new java.io.File(s).getName();}public void setOnPreparedListener(OnPreparedListener l){prepared=l;}public void setOnCompletionListener(OnCompletionListener l){completed=l;}public void setOnErrorListener(OnErrorListener l){error=l;}public void prepareAsync(){live=this;prepared.onPrepared(this);}public void start(){played.add(file);}public void release(){if(live==this)live=null;}public static void complete(){MediaPlayer p=live;p.completed.onCompletion(p);}public static void fail(){MediaPlayer p=live;p.error.onError(p,1,0);}}''',
'android/os/Looper.java':'''package android.os;public class Looper {public static Looper getMainLooper(){return new Looper();}}''',
'android/os/Handler.java':'''package android.os;public class Handler {public static Runnable pending;public Handler(Looper l){}public void post(Runnable r){r.run();}public void postDelayed(Runnable r,long ms){pending=r;}public void removeCallbacks(Runnable r){if(pending==r)pending=null;}public static void tick(){Runnable r=pending;pending=null;if(r!=null)r.run();}}''',
'org/json/JSONObject.java':'''package org.json;import java.util.*;public class JSONObject {Map<String,Object> values=new LinkedHashMap<>();public JSONObject put(String k,Object v){values.put(k,v);return this;}public String getString(String k){return (String)values.get(k);}public JSONObject getJSONObject(String k){return (JSONObject)values.get(k);}public JSONArray getJSONArray(String k){return (JSONArray)values.get(k);}public JSONArray optJSONArray(String k){return (JSONArray)values.get(k);}public Iterator<String> keys(){return values.keySet().iterator();}}''',
'org/json/JSONArray.java':'''package org.json;import java.util.*;public class JSONArray {List<String> items=new ArrayList<>();public JSONArray put(String s){items.add(s);return this;}public int length(){return items.size();}public String getString(int i){return items.get(i);}}''',
'com/luna17/aot/NativeBridge.java':'''package com.luna17.aot;final class NativeBridge {static int[] event;static int finished;static int[] crewEvent(){int[] e=event;event=null;return e;}static void crewFinished(){finished++;}}''',
'com/luna17/aot/CrewVoiceTest.java':'''package com.luna17.aot;import java.io.*;import java.nio.file.*;import java.util.*;import android.media.MediaPlayer;import android.os.Handler;import org.json.*;public class CrewVoiceTest {
static void clip(File d,String n)throws Exception{new File(d,n).createNewFile();}
static void check(boolean condition){if(!condition)throw new AssertionError();}
public static void main(String[] args)throws Exception{
 File d=Files.createTempDirectory("crew-player").toFile();String prefix="voice_message_commander_target";
 for(String type:new String[]{"enemy","tank","aircraft","vehicle","t34","tiger","panther"})clip(d,prefix+"_"+type+".wav");
 for(int i=1;i<=12;i++)clip(d,prefix+"_"+i+"_h.wav");
 clip(d,prefix+".wav");clip(d,prefix+"_distance_v1.wav");clip(d,prefix+"_450_m.wav");clip(d,"voice_message_gunner_fire_v1.wav");
 JSONObject config=new JSONObject().put("mode","drop-while-speaking").put("targetPrefix",prefix+".wav").put("distancePrefix",prefix+"_distance_v1.wav").put("events",new JSONObject().put("10",new JSONArray().put("voice_message_gunner_fire_v1.wav")));
 CrewVoicePlayer player=new CrewVoicePlayer(d,config);NativeBridge.event=new int[]{1,2,3,450};player.start();
 check(MediaPlayer.played.equals(Arrays.asList(prefix+".wav")));check(NativeBridge.finished==0);
 // A second arrival is discarded, including while fragments are changing.
 NativeBridge.event=new int[]{10,0,0,0};Handler.tick();check(MediaPlayer.played.size()==1);check(NativeBridge.finished==0);
 for(int i=0;i<4;i++){MediaPlayer.complete();check(NativeBridge.finished==0);}
 check(MediaPlayer.played.equals(Arrays.asList(prefix+".wav",prefix+"_aircraft.wav",prefix+"_3_h.wav",prefix+"_distance_v1.wav",prefix+"_450_m.wav")));
 MediaPlayer.complete();check(NativeBridge.finished==1);Handler.tick();check(MediaPlayer.played.size()==5);
 NativeBridge.event=new int[]{10,0,0,0};Handler.tick();check(MediaPlayer.played.size()==6);MediaPlayer.fail();check(NativeBridge.finished==2);
 NativeBridge.event=new int[]{10,0,0,0};Handler.tick();player.stop();check(NativeBridge.finished==3);check(MediaPlayer.live==null);check(Handler.pending==null);
 System.out.println("Crew player: target/type/clock/distance sequence; busy arrivals dropped; no queued replay; errors and stop release gate");
}}'''
}
class CrewVoicePlayback(unittest.TestCase):
    @unittest.skipUnless(shutil.which('java'),'JDK required')
    def test_production_player_sequence_and_busy_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);sources=[]
            for name,source in STUBS.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(source);sources.append(str(path))
            sources.append(str(ROOT/'mods/tankinvincible/src/com/luna17/aot/CrewVoicePlayer.java'))
            classes=root/'classes';classes.mkdir()
            subprocess.run(['java','com.sun.tools.javac.Main','--release','8','-d',str(classes),*sources],check=True)
            subprocess.run(['java','-cp',str(classes),'com.luna17.aot.CrewVoiceTest'],check=True)
if __name__=='__main__':unittest.main()
