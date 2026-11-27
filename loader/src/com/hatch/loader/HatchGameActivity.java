package com.hatch.loader;

import android.content.Intent;
import android.view.View;
import android.view.ViewGroup;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.MotionEvent;
import com.unity3d.player.UnityPlayerActivity;

/** Both the launcher and the component stored in an old Android task use this lifecycle. */
public class HatchGameActivity extends UnityPlayerActivity implements GameFrameHost {
    private final Handler ui = new Handler(Looper.getMainLooper());
    private boolean drawn, resumed, focused, interacted, attached, destroyed;
    private int sequence;
    private volatile int frameSession;
    private final Runnable confirm = () -> {
        if (attached && resumed && !destroyed) HatchLoader.confirmStartup(this);
    };

    private View waitButton;
    private final Runnable longWait = () -> {
        if (!destroyed && resumed && !drawn && !isFinishing() && waitButton == null)
            waitButton = HatchLoader.startupDiagnostic(this);
    };
    private void clearWait() {
        ui.removeCallbacks(longWait);
        if (waitButton != null && waitButton.getParent() instanceof ViewGroup)
            ((ViewGroup)waitButton.getParent()).removeView(waitButton);
        waitButton = null;
    }

    @Override protected void onCreate(Bundle state) {
        HatchLoader.prepareForUnity(this);
        super.onCreate(state);
    }
    @Override public void reportFullyDrawn() {
        // The shipped player's render loop calls this from UnityMain after its initial frames.
        runOnUiThread(() -> {
            if (destroyed || isFinishing()) return;
            super.reportFullyDrawn();
            drawn = true;
            clearWait();
            activate();
        });
    }
    private void activate() {
        if (destroyed || !drawn || !resumed || isFinishing()) return;
        if (!attached) {
            attached = true;
            HatchLoader.start(this);
        }
        ui.removeCallbacks(confirm);
        ui.postDelayed(confirm, 10000);
        updateFrameSession();
    }
    private void updateFrameSession() {
        if (destroyed || !drawn || !resumed || !focused || !interacted) frameSession = 0;
        else if (frameSession == 0) frameSession = ++sequence;
    }
    @Override public int frameSession() { return frameSession; }
    @Override public boolean postGameFrame(Runnable work) {
        if (frameSession == 0 || mUnityPlayer == null) return false;
        mUnityPlayer.invokeOnMainThread(work);
        return true;
    }
    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        if (!drawn) ui.postDelayed(longWait, 45000);
        activate();
    }
    @Override protected void onPause() {
        resumed = false;
        clearWait();
        updateFrameSession();
        ui.removeCallbacks(confirm);
        super.onPause();
    }
    @Override public void onWindowFocusChanged(boolean focus) {
        super.onWindowFocusChanged(focus);
        focused = focus;
        updateFrameSession();
    }
    private void onInteraction() {
        if (!destroyed && drawn && resumed && focused && !interacted) {
            interacted = true;
            updateFrameSession();
        }
    }
    @Override public boolean dispatchTouchEvent(MotionEvent event) {
        boolean handled = super.dispatchTouchEvent(event);
        if (handled && event.getActionMasked() == MotionEvent.ACTION_UP) onInteraction();
        return handled;
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        boolean handled = super.dispatchKeyEvent(event);
        if (handled && event.getAction() == KeyEvent.ACTION_UP &&
                event.getKeyCode() != KeyEvent.KEYCODE_BACK) onInteraction();
        return handled;
    }
    @Override protected void onUserLeaveHint() {
        super.onUserLeaveHint();
        if (drawn) HatchLoader.confirmStartup(this);
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        if (!HatchLoader.result(this, request, result, data))
            super.onActivityResult(request, result, data);
    }
    @Override protected void onDestroy() {
        destroyed = true;
        clearWait();
        updateFrameSession();
        ui.removeCallbacks(confirm);
        HatchLoader.stop(this);
        super.onDestroy();
    }
}
