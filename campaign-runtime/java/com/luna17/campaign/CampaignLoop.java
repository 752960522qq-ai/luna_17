package com.luna17.campaign;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.widget.Toast;
import com.hatch.loader.GameFrameHost;

/** Scene operations only run inside a rendered, interactive Unity player. */
public final class CampaignLoop {
  private static final Handler ui = new Handler(Looper.getMainLooper());
  private static Session currentSession;
  private static volatile int notice;
  private static volatile long expires, radioUntil;
  private static volatile String radio = "";
  private static native int step();
  private CampaignLoop() {}
  public static synchronized void signal(int kind) {
    if (kind >= 20 && kind <= 25) {
      String[] lines = {"德军第二波出现，两侧都有敌车。守住村口！",
                        "敌机接近！",
                        "后方两辆 T-34 已到，协同守住阵地！",
                        "第二波已投入，从两侧向村口推进！",
                        "苏军飞机接近！",
                        "苏军两辆 T-34 正从后方增援，夺取村口！"};
      radio = lines[kind - 20];
      radioUntil = SystemClock.uptimeMillis() + 5500;
      return;
    }
    if (kind != 3 && kind != 4 && kind != 6 && kind != 7)
      return;
    long now = SystemClock.uptimeMillis();
    if (now < expires && notice == 6 && kind != 6)
      return;
    notice = kind;
    expires = now + (kind == 6 ? 2600 : 1400);
  }
  public static int current() {
    return SystemClock.uptimeMillis() < expires ? notice : 0;
  }
  public static String radio() {
    return SystemClock.uptimeMillis() < radioUntil ? radio : "";
  }
  public static synchronized void clear() {
    expires = radioUntil = 0;
    notice = 0;
    radio = "";
  }
  private static final class Session implements Runnable {
    final Activity activity;
    final GameFrameHost host;
    final FramePump pump;
    boolean loaded, reportedFaction;
    Session(Activity activity, GameFrameHost host) {
      this.activity = activity;
      this.host = host;
      this.pump = new FramePump(host, this::frame);
    }
    public void run() {
      if (currentSession != this) return;
      pump.tick();
      ui.postDelayed(this, host.frameSession() == 0 ? 350 : 120);
    }
    private void message(String text) {
      ui.post(() -> {
        if (currentSession == this && !activity.isFinishing() && !activity.isDestroyed())
          Toast.makeText(activity, text, Toast.LENGTH_SHORT).show();
      });
    }
    private void frame() {
      try {
        if (!loaded) {
          System.loadLibrary("hatchcampaign");
          loaded = true;
        }
        int n = step();
        if (n > 0) signal(n);
        if (n < 0 && !reportedFaction) message("未能确认战役阵营，请重新选择");
        reportedFaction = n < 0;
      } catch (RuntimeException | LinkageError failure) {
        Log.e("HatchCampaign", "Campaign frame failed", failure);
        pump.stop();
        message("额外战役未能启动，可继续使用原版模式");
        ui.post(() -> { if (currentSession == this) stop(); });
      }
    }
  }
  public static void start(Activity activity) {
    if (currentSession != null && currentSession.activity == activity) return;
    stop();
    if (!(activity instanceof GameFrameHost)) return;
    currentSession = new Session(activity, (GameFrameHost)activity);
    ui.post(currentSession);
  }
  public static void stop() {
    if (currentSession != null) {
      currentSession.pump.stop();
      ui.removeCallbacks(currentSession);
      currentSession = null;
    }
    clear();
  }
}
