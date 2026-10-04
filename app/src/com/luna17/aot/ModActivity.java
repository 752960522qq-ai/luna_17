package com.luna17.aot;

import android.os.Bundle;
import com.unity3d.player.UnityPlayerActivity;

public final class ModActivity extends UnityPlayerActivity {
    private ModMenu menu;
    @Override protected void onCreate(Bundle state) {
        NativeBridge.start();
        super.onCreate(state);
        menu = new ModMenu(this);
        menu.attach();
    }
    @Override protected void onDestroy() {
        if (menu != null) menu.detach();
        super.onDestroy();
    }
}
