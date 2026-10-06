package com.hatch.loader;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.os.Bundle;
import android.widget.TextView;

/** The game is launched only after its prerequisite is ready. */
public final class HatchActivity extends Activity {
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView status = new TextView(this);
        status.setText("舱盖 0.2：正在初始化坦无敌3000…");
        status.setPadding(32,32,32,32);
        setContentView(status);
        HatchLoader.prepare(this, failure -> {
            if (isFinishing() || isDestroyed()) return;
            if (failure != null) {
                new AlertDialog.Builder(this).setTitle("舱盖启动失败")
                    .setMessage(failure).setCancelable(false)
                    .setPositiveButton("退出", (d,w) -> finish()).show();
                return;
            }
            startActivity(new Intent(this,HatchGameActivity.class));
            finish();
        });
    }
}
