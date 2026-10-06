package com.luna17.aot;

import android.app.Activity;
import com.hatch.loader.HatchModule;
import java.io.File;
import org.json.JSONObject;

public final class TankInvincibleModule implements HatchModule {
    private ModMenu menu;
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
    @Override public void stop() { if (menu != null) menu.detach(); }
}
