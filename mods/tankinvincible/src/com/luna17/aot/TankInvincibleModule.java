package com.luna17.aot;

import android.app.Activity;
import com.hatch.loader.HatchModule;
import com.hatch.loader.HatchFeatureHost;
import java.io.File;
import org.json.JSONObject;

public final class TankInvincibleModule implements HatchModule, HatchFeatureHost {
    private ModMenu menu;
    private ExperienceHud hud;
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
    }
    @Override public String loadTank(File runtime, String manifest) throws Exception {
        JSONObject doc = new JSONObject(manifest);
        JSONObject magazine = doc.optJSONObject("magazine");
        if (magazine != null && !NativeBridge.configureMagazine(doc.getString("id"),
                magazine.getInt("capacity"), (float)magazine.getDouble("shotInterval"),
                (float)magazine.getDouble("reloadTime")))
            return "弹匣配置无效";
        return NativeBridge.loadHatch(runtime.getAbsolutePath());
    }
    @Override public String[] capabilities() {
        return new String[]{"ballistic-preview-v1","damage-formula-v1","artillery-sight-v1"};
    }
    @Override public synchronized String loadFeatures(String id,String configuration) throws Exception {
        JSONObject doc=new JSONObject(configuration);
        if(doc.getInt("schema")!=1)return "玩法配置版本不兼容";
        java.util.Iterator<String> keys=doc.keys();
        java.util.Set<String> allowed=new java.util.HashSet<>(java.util.Arrays.asList("schema","aim","damage","artillery"));
        while(keys.hasNext())if(!allowed.contains(keys.next()))return "未知玩法配置字段";
        int flags=0;
        if(doc.optBoolean("aim",false))flags|=1;
        if(doc.optBoolean("artillery",false))flags|=4;
        JSONObject damage=doc.optJSONObject("damage");float k=damageK,khe=damageKhe;
        if(damage!=null){
            if(!"two-stage-0.1".equals(damage.getString("formula")))return "不支持的伤害公式";
            if(damage.getDouble("apFillingGrams")!=155 || damage.getDouble("apcrFillingGrams")!=0 || damage.getDouble("heFillingGrams")!=710)return "装药配置不兼容";
            k=(float)damage.getDouble("K");khe=(float)damage.getDouble("K_HE");flags|=2;
        }
        if((flags&claimedFlags)!=0)return "扩展能力冲突: "+featureOwners;
        if(flags==0 || !NativeBridge.configureExperience(flags|claimedFlags,k,khe))return "玩法配置无效，或战斗已开始；请在进入战斗前加载";
        for(int bit=1;bit<=4;bit<<=1)if((flags&bit)!=0)featureOwners.put(bit,id);
        claimedFlags|=flags;damageK=k;damageKhe=khe;return "";
    }
    @Override public void stop() { if (menu != null) menu.detach(); if(hud!=null)hud.detach(); }
}
