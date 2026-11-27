package com.hatch.loader;

import android.content.SharedPreferences;

/** Count interrupted cold launches, never Activity recreations. Only store boot information. */
final class StartupHistory {
    final boolean recovery;
    final String previousStage;
    private final SharedPreferences prefs;
    private boolean confirmed;
    StartupHistory(SharedPreferences prefs) {
        this.prefs = prefs;
        int attempts = prefs.getInt("attempts", 0);
        previousStage = prefs.getString("stage", "启动中");
        recovery = attempts >= 2;
        prefs.edit().putInt("attempts", Math.min(2, attempts + 1))
             .putString("stage", recovery ? "恢复启动" : "准备前置模组").commit();
    }
    void stage(String name) {
        if (!confirmed) prefs.edit().putString("stage", name).commit();
    }
    void requestRecovery() {
        confirmed = true;  // Do not clear an explicit request if a late frame arrives.
        prefs.edit().putInt("attempts", 2).putString("stage", "玩家在等待画面时请求恢复启动").commit();
    }
    void confirm() {
        if (!confirmed) {
            confirmed = prefs.edit().remove("attempts").remove("stage").commit();
        }
    }
}
