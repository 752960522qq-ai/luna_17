package com.luna17.aot;

import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.os.Handler;
import android.os.Looper;
import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import org.json.JSONArray;
import org.json.JSONObject;

/** One utterance owns the native gate until all its clips finish. */
final class CrewVoicePlayer {
    private final File directory;
    private final JSONObject configuration;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private MediaPlayer player;
    private volatile boolean stopped=true;
    private List<String> clips;
    private int index,generation;
    private final Random random=new Random();
    CrewVoicePlayer(File directory,JSONObject configuration) throws Exception {
        this.directory=directory;this.configuration=configuration;
        if(!directory.isDirectory()||!("queue-while-speaking".equals(configuration.getString("mode"))||"drop-while-speaking".equals(configuration.getString("mode"))))throw new IllegalArgumentException("语音资源或播放模式无效");
        JSONObject events=configuration.getJSONObject("events");
        java.util.Iterator<String> keys=events.keys();
        while(keys.hasNext()){
            String key=keys.next();int event=Integer.parseInt(key);
            if(event<0||event>17)throw new IllegalArgumentException("未知成员语音事件");
            JSONArray items=events.getJSONArray(key);if(items.length()<1||items.length()>32)throw new IllegalArgumentException("语音片段数量无效");
            for(int i=0;i<items.length();i++)requireClip(items.getString(i));
        }
        if(configuration.has("targetTypes")){
            JSONObject types=configuration.getJSONObject("targetTypes");requireClip(types.getString("tank"));requireClip(types.getString("aircraft"));
            requirePool(configuration.getJSONArray("distancePrefixPool"));requirePool(configuration.getJSONArray("nearPool"));
        }else{
            requireClip(configuration.getString("targetPrefix"));requireClip(configuration.getString("distancePrefix"));
            for(String type:new String[]{"enemy","tank","aircraft","vehicle","t34","tiger","panther"})requireClip("voice_message_commander_target_"+type+".wav");
        }
        for(int i=1;i<=12;i++)requireClip("voice_message_commander_target_"+i+"_h.wav");
    }
    private void requireClip(String name){
        if(!name.matches("[A-Za-z0-9_.-]{1,160}\\.wav")||name.contains("..")||!new File(directory,name).isFile())throw new IllegalArgumentException("缺少语音: "+name);
    }
    void start(){if(!stopped)return;stopped=false;handler.post(poll);}
    void stop(){stopped=true;generation++;handler.removeCallbacks(poll);release();clips=null;NativeBridge.crewClear();}
    private void release(){if(player!=null){player.release();player=null;}}
    private final Runnable poll=new Runnable(){public void run(){
        if(stopped)return;
        int[] event=clips==null?NativeBridge.crewEvent():null;
        if(event!=null){
            try{clips=compose(event);index=0;playNext(generation);}catch(Exception failure){finish();}
        }
        handler.postDelayed(this,30);
    }};
    private List<String> compose(int[] event) throws Exception {
        List<String> result=new ArrayList<>();
        if(event.length!=4)return result;
        if(event[0]==17 || event[0]==1){
            if(configuration.has("targetTypes")){
                result.add(configuration.getJSONObject("targetTypes").getString(event[1]==2?"aircraft":"tank"));
            }else{
                result.add(configuration.getString("targetPrefix"));
                String[] types={"enemy","tank","aircraft","vehicle","t34","tiger","panther"};
                result.add("voice_message_commander_target_"+types[Math.max(0,Math.min(types.length-1,event[1]))]+".wav");
            }
            if(event[2]>=1&&event[2]<=12)result.add("voice_message_commander_target_"+event[2]+"_h.wav");
            if(event[3]<300 && configuration.has("nearPool"))result.add(pick(configuration.getJSONArray("nearPool")));
            else{
                String distance=distanceClip(event[3]);
                if(distance!=null){
                    result.add(configuration.has("distancePrefixPool")?pick(configuration.getJSONArray("distancePrefixPool")):configuration.getString("distancePrefix"));
                    result.add(distance);
                }
            }
        }else{
            JSONArray items=configuration.getJSONObject("events").optJSONArray(Integer.toString(event[0]));
            if(items!=null){
                if("random-pool".equals(configuration.optString("selection","")))result.add(pick(items));
                else for(int i=0;i<items.length();i++)result.add(items.getString(i));
            }
        }
        return result;
    }
    private String distanceClip(int metres){
        if(metres<300||metres>2000)return null;
        // Only speak an available distance fragment; never invent a number.
        int closest=0,error=Integer.MAX_VALUE;
        String[] files=directory.list();if(files==null)return null;
        for(String name:files){
            java.util.regex.Matcher m=java.util.regex.Pattern.compile("voice_message_commander_target_(\\d+)_m\\.wav").matcher(name);
            if(m.matches()){
                int value=Integer.parseInt(m.group(1)),difference=Math.abs(value-metres);
                if(difference<error){closest=value;error=difference;}
            }
        }
        if(closest==0)return null;
        return "voice_message_commander_target_"+closest+"_m.wav";
    }
    private void requirePool(JSONArray pool) throws Exception {
        if(pool.length()<1||pool.length()>32)throw new IllegalArgumentException("语音池数量无效");
        for(int i=0;i<pool.length();i++)requireClip(pool.getString(i));
    }
    private String pick(JSONArray pool) throws Exception {return pool.getString(random.nextInt(pool.length()));}
    private void playNext(final int token){
        if(stopped||token!=generation)return;
        release();
        if(clips==null||index>=clips.size()){finish();return;}
        try{
            String name=clips.get(index++);requireClip(name);
            final MediaPlayer current=new MediaPlayer();player=current;
            current.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build());
            current.setDataSource(new File(directory,name).getAbsolutePath());
            current.setOnPreparedListener(p->{if(!stopped&&token==generation&&player==p)p.start();});
            current.setOnCompletionListener(p->{if(token==generation&&player==p)playNext(token);});
            current.setOnErrorListener((p,what,extra)->{if(token==generation&&player==p)finish();return true;});
            current.prepareAsync();
        }catch(Exception failure){finish();}
    }
    private void finish(){release();clips=null;index=0;NativeBridge.crewFinished();}
}
