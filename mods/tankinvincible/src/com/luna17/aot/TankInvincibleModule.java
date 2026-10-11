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
            if(doc.length()!=3||!doc.has("voiceDirectory"))return "成员语音资源或配置字段无效";
            CrewVoicePlayer candidate=new CrewVoicePlayer(new File(doc.getString("voiceDirectory")),voice);
            int mask=(1<<1)|(1<<3);
            java.util.Iterator<String> events=voice.getJSONObject("events").keys();
            while(events.hasNext())mask|=1<<Integer.parseInt(events.next());
            if(!NativeBridge.configureCrew(true,mask))return "请在进入战斗前加载成员体验";
            crew=candidate;if(menu!=null)crew.start();return "";
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
        if(ammo!=null){
            if(ammo.length()>512)return "装药配置车辆数超限";
            String[] kinds={"AP","HE","APCR","WP","HEAT"};
            java.util.Map<String,float[]> values=new java.util.LinkedHashMap<>();
            java.util.Map<String,Integer> masks=new java.util.LinkedHashMap<>();
            java.util.Iterator<String> ids=ammo.keys();
            while(ids.hasNext()){
                String vehicle=ids.next();if(!vehicle.matches("[A-Za-z0-9_-]{1,111}"))return "装药配置车辆ID无效";
                JSONObject shells=ammo.getJSONObject(vehicle);float[] grams=new float[5];int mask=0;
                java.util.Iterator<String> types=shells.keys();while(types.hasNext())if(!java.util.Arrays.asList(kinds).contains(types.next()))return "未知装药弹种";
                for(int i=0;i<5;i++)if(shells.has(kinds[i])&&!shells.isNull(kinds[i])){
                    double value=shells.getDouble(kinds[i]);if(!Double.isFinite(value)||value<0||value>100000)return "装药量应为0–100000克或null";
                    grams[i]=(float)value;mask|=1<<i;
                }
                values.put(vehicle,grams);masks.put(vehicle,mask);
            }
            for(String vehicle:values.keySet())if(!NativeBridge.configureAmmunition(vehicle,values.get(vehicle),masks.get(vehicle)))return "装药配置加载失败";
        }
        if(!NativeBridge.configureExperience(flags|claimedFlags,k,khe))return "玩法配置加载失败";
        for(int bit=1;bit<=4;bit<<=1)if((flags&bit)!=0)featureOwners.put(bit,id);
        claimedFlags|=flags;damageK=k;damageKhe=khe;return "";
    }
    @Override public void stop() { if (menu != null) menu.detach(); if(hud!=null)hud.detach(); if(crew!=null)crew.stop(); }
}
