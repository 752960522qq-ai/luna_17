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
  private static native int extraSide();
  private static native boolean postMessage(String s, int seconds);
  private static native boolean sample(float[] values, int profiles, boolean aim);
  private static volatile float[] last;
  private static volatile int profiles;
  private static volatile boolean aim;
  public static float[] instruments() { return last; }
  public static synchronized void registerVehicle(String id) {
    if ("T26".equals(id)) profiles|=1;
    if ("Panzer_II_Ausf_F".equals(id)) profiles|=2;
  }
  public static void setAim(boolean enabled) { aim=enabled; }
  private static volatile int extra;
  public static boolean isExtra() { return extra != 0; }
  private static final java.util.ArrayDeque<String> orders = new java.util.ArrayDeque<>();
  private static String feedback="", lastLine="";
  private static long nextLine, lastFeedback, feedbackTime;
  private static synchronized void side(int value) {
    if (extra == value) return;
    resetMessages(); extra=value;
    if (value != 0) orders.add(value == 1 ? "炼狱之门 · 驾驶 T26，守住村口阵地！" : "炼狱之门 · 驾驶二号 F 型，夺取村口阵地！");
  }
  private static void resetMessages() {
    orders.clear(); feedback=""; lastLine=""; nextLine=lastFeedback=feedbackTime=0;
  }
  public static synchronized void contact(String text) {
    if (extra != 0 && text != null && !text.isEmpty() && !orders.contains(text) && orders.size()<8) orders.addLast(text);
  }
  private static synchronized void deliver(long now) {
    if (extra==0 || now<nextLine) return;
    if (now-feedbackTime>2200) feedback="";
    boolean combat=!feedback.isEmpty() && (orders.isEmpty() || now-lastFeedback>4000);
    String text=combat?feedback:orders.peekFirst();
    if(text==null || text.isEmpty())return;
    int seconds=combat?2:3;
    if(postMessage(text,seconds)){
      lastLine=text;nextLine=now+seconds*1000L;
      if(combat){feedback="";lastFeedback=now;}else orders.removeFirst();
    }
  }
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
      if (extra != 0 && !orders.contains(radio)) orders.addLast(radio);
      radioUntil = SystemClock.uptimeMillis() + 5500;
      return;
    }
    if (kind != 3 && kind != 4 && kind != 6 && kind != 7)
      return;
    long now = SystemClock.uptimeMillis();
    if (now < expires && notice == 6 && kind != 6)
      return;
    String text=kind==6?"敌车已击毁":kind==4?"我车中弹":"命中敌车";
    if(extra!=0 && !(text.equals(lastLine) && now<nextLine) && !(feedback.equals("敌车已击毁") && now-feedbackTime<2000)){
      feedback=text;feedbackTime=now;
    }
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
    volatile boolean firing;
    long nextPoll;
    Session(Activity activity, GameFrameHost host) {
      this.activity = activity;
      this.host = host;
      this.pump = new FramePump(host, this::frame);
    }
    public void run() {
      if (currentSession != this) return;
      pump.tick();
      ui.postDelayed(this, host.frameSession() == 0 ? 350 : firing ? 16 : 90);
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
        long now=SystemClock.uptimeMillis();
        if(now>=nextPoll) {
          nextPoll=now+100;
          int n=step();side(extraSide());
          if(n>0)signal(n);
          if(n<0 && !reportedFaction)message("未能确认战役阵营，请重新选择");
          reportedFaction=n<0;deliver(now);
        }
        float[] values=new float[7];
        firing=sample(values,profiles,aim);
        last=firing?values:null;
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
    last=null;side(0);clear();
  }
}
