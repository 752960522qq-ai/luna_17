package com.hatch.loader;

import android.os.Bundle;
import android.content.Intent;
import com.unity3d.player.UnityPlayerActivity;

public final class HatchGameActivity extends UnityPlayerActivity {
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        HatchLoader.start(this);
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        if (!HatchLoader.result(this, request, result, data))
            super.onActivityResult(request, result, data);
    }
    @Override protected void onDestroy() {
        HatchLoader.stop();
        super.onDestroy();
    }
}
