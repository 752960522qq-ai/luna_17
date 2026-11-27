package com.luna17.campaign;

import android.app.Activity;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import android.widget.Toast;
import java.lang.reflect.Field;

/**
 * The game ships a dedicated UnityMain Looper. Every scene operation is queued
 * on it.
 */
public final class CampaignLoop {
  private static final Handler ui = new Handler(Looper.getMainLooper());
  private static volatile int epoch;
  private static volatile int notice;
  private static volatile long expires, radioUntil;
  private static volatile String radio = "";
  private static volatile boolean live;
  private static int misses;
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
  public static void start(Activity activity) {
    stop();
    final int token = ++epoch;
    live = true;
    try {
      System.loadLibrary("hatchcampaign");
    } catch (LinkageError error) {
      Log.e("HatchCampaign", "Could not load campaign runtime", error);
      Toast
          .makeText(activity, "额外战役模块未加载，请重新安装完整 APK",
                    Toast.LENGTH_LONG)
          .show();
      return;
    }
    bind(activity, token);
  }
  private static void bind(final Activity activity, final int token) {
    if (!live || epoch != token)
      return;
    for (Thread t : Thread.getAllStackTraces().keySet()) {
      if (!"UnityMain".equals(t.getName()) ||
          !t.getClass().getName().startsWith("com.unity3d.player."))
        continue;
      for (Field f : t.getClass().getDeclaredFields()) {
        if (!Handler.class.isAssignableFrom(f.getType()))
          continue;
        try {
          f.setAccessible(true);
          Handler h = (Handler)f.get(t);
          if (h == null || h.getLooper().getThread() != t)
            continue;
          misses = 0;
          final Handler game = new Handler(h.getLooper());
          game.post(new Runnable() {
            public void run() {
              if (!live || epoch != token)
                return;
              int n = step();
              if (n > 0)
                signal(n);
              else if (n < 0)
                ui.post(()
                            -> Toast
                                   .makeText(activity,
                                             "未能确认战役阵营，请重新选择",
                                             Toast.LENGTH_SHORT)
                                   .show());
              game.postDelayed(this, 120);
            }
          });
          return;
        } catch (ReflectiveOperationException | SecurityException ex) {
          Log.w("HatchCampaign", "Unity loop unavailable", ex);
        }
      }
    }
    if (++misses == 25)
      Toast
          .makeText(activity, "正在等待游戏主线程，额外战役尚未就绪",
                    Toast.LENGTH_SHORT)
          .show();
    ui.postDelayed(() -> bind(activity, token), 300);
  }
  public static void stop() {
    live = false;
    epoch++;
    clear();
    misses = 0;
  }
}
