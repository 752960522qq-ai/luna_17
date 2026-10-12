package com.luna17.aot;
import org.json.JSONObject;
/** Validate the whole charge table before publishing entries to native code. */
final class AmmunitionSettings {
 static String apply(JSONObject ammo) throws Exception {
 if(ammo==null)return "";

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

 return "";
 }
}
