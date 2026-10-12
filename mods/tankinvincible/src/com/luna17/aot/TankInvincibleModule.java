package com.luna17.aot;

import android.app.Activity;
import com.hatch.loader.HatchModule;
import com.hatch.loader.HatchFeatureHost;
import java.io.File;
import org.json.JSONObject;

public final class TankInvincibleModule implements HatchModule, HatchFeatureHost {
    private ModMenu menu;
    private ExperienceHud hud;
    private CrewVoicePlayer crew;
    private int claimedFlags;
    private float damageK=20,damageKhe=10;
    private final java.util.Map<Integer,String> featureOwners=new java.util.HashMap<>();
    @Override public int apiVersion() { return 2; }
    @Override public void prepare(File library) {
        if (!NativeBridge.loaded) NativeBridge.start(library.getAbsolutePath());
        if (!NativeBridge.loaded) throw new IllegalStateException(NativeBridge.error);
    }
    @Override public void start(Activity activity, File library) {
        if (!NativeBridge.loaded) throw new IllegalStateException("前置尚未完成启动初始化");
        if (menu != null) menu.detach();
        menu = new ModMenu(activity);
        menu.attach();
        if(hud!=null)hud.detach();
        hud=new ExperienceHud(activity);hud.attach();
        if(crew!=null)crew.start();
    }
    @Override public String loadTank(File runtime, String manifest) throws Exception {
        NativeBridge.clearTankConfiguration();
        try {
        JSONObject doc = new JSONObject(manifest);
        JSONObject filling=doc.optJSONObject("shell_filling_grams");
        if(filling!=null){
            String[] shells={"AP","HE","APCR","WP","HEAT"};float[] grams=new float[5];int mask=0;
            for(int i=0;i<5;i++)if(filling.has(shells[i])){grams[i]=(float)filling.getDouble(shells[i]);mask|=1<<i;}
            if(mask!=0 && !NativeBridge.configureFilling(doc.getString("id"),grams,mask))return "装药配置无效";
        }
        JSONObject magazine = doc.optJSONObject("magazine");
        if(!NativeBridge.configureContinuousFire(doc.getString("id"),doc.optBoolean("continuous_fire",magazine!=null),doc.optString("texture_uv_convention", "").contains("converted")))return "连发开关无效";
        if (magazine != null && !NativeBridge.configureMagazine(doc.getString("id"),
                magazine.getInt("capacity"), (float)magazine.getDouble("shotInterval"),
                (float)magazine.getDouble("reloadTime")))
            return "弹匣配置无效";
        return NativeBridge.loadHatch(runtime.getAbsolutePath());
        } finally { NativeBridge.clearTankConfiguration(); }
    }
    @Override public String[] capabilities() {
        return new String[]{"ballistic-preview-v1","damage-formula-v1","artillery-sight-v1","crew-voice-v1"};
    }
    @Override public synchronized String loadFeatures(String id,String configuration) throws Exception {
        JSONObject doc=new JSONObject(configuration);
        if(doc.getInt("schema")!=1)return "玩法配置版本不兼容";
        java.util.Iterator<String> keys=doc.keys();
        java.util.Set<String> allowed=new java.util.HashSet<>(java.util.Arrays.asList("schema","aim","damage","artillery","ammunition","crew","voiceDirectory"));
        while(keys.hasNext())if(!allowed.contains(keys.next()))return "未知玩法配置字段";
        JSONObject voice=doc.optJSONObject("crew");
        if(voice!=null){
            if(crew!=null)return "成员语音能力已被占用";
            if(!doc.has("voiceDirectory"))return "成员语音资源或配置字段无效";
            CrewVoicePlayer candidate=new CrewVoicePlayer(new File(doc.getString("voiceDirectory")),voice);
            int mask=1<<voice.optInt("lockEvent",1);
            java.util.Iterator<String> events=voice.getJSONObject("events").keys();
            while(events.hasNext())mask|=1<<Integer.parseInt(events.next());
            if(!NativeBridge.configureCrew(true,mask))return "请在进入战斗前加载成员体验";
            crew=candidate;if(menu!=null)crew.start();
            if(!doc.has("aim")&&!doc.has("damage")&&!doc.has("artillery"))return "";
        }
        int flags=0;
        if(doc.optBoolean("aim",false))flags|=1;
        if(doc.optBoolean("artillery",false))flags|=4;
        JSONObject damage=doc.optJSONObject("damage");float k=damageK,khe=damageKhe;
        if(damage!=null){
            if(!"two-stage-0.1".equals(damage.getString("formula")))return "不支持的伤害公式";
            // Legacy global filling fields are accepted but no longer override vehicle ammunition.
            k=(float)damage.getDouble("K");khe=(float)damage.getDouble("K_HE");flags|=2;
        }
        if((flags&claimedFlags)!=0)return "扩展能力冲突: "+featureOwners;
        if(flags==0 || NativeBridge.state()==3 || !Float.isFinite(k)||k<=0||k>1000||!Float.isFinite(khe)||khe<=0||khe>1000)return "玩法配置无效，或战斗已开始；请在进入战斗前加载";
        JSONObject ammo=doc.optJSONObject("ammunition");
        String ammunitionError=AmmunitionSettings.apply(ammo);if(!ammunitionError.isEmpty())return ammunitionError;
        if(!NativeBridge.configureExperience(flags|claimedFlags,k,khe))return "玩法配置加载失败";
        for(int bit=1;bit<=4;bit<<=1)if((flags&bit)!=0)featureOwners.put(bit,id);
        claimedFlags|=flags;damageK=k;damageKhe=khe;return "";
    }
    @Override public void stop() { if (menu != null) menu.detach(); if(hud!=null)hud.detach(); if(crew!=null)crew.stop(); }
}
