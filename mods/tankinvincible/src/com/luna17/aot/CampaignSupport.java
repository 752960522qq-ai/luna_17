package com.luna17.aot;

import android.app.Activity;
import java.lang.reflect.Method;

/**
 * The base Hatch builder also ships this module without the optional campaign
 * APK.
 */
final class CampaignSupport {
  private static Method start, stop, clear, current, signal, radio;
  static {
    try {
      Class<?> c = Class.forName("com.luna17.campaign.CampaignLoop", false,
                                 CampaignSupport.class.getClassLoader());
      start = c.getMethod("start", Activity.class);
      stop = c.getMethod("stop");
      clear = c.getMethod("clear");
      current = c.getMethod("current");
      signal = c.getMethod("signal", int.class);
      radio = c.getMethod("radio");
    } catch (ReflectiveOperationException
                 ignored) { /* ordinary non-campaign build */
    }
  }
  private static Object run(Method m, Object... args) {
    if (m != null)
      try {
        return m.invoke(null, args);
      } catch (ReflectiveOperationException ex) {
        android.util.Log.e("HatchCampaign", "Campaign callback failed", ex);
      }
    return null;
  }
  static void start(Activity a) { run(start, a); }
  static void stop() { run(stop); }
  static void clear() { run(clear); }
  static void signal(int i) { run(signal, i); }
  static int current() {
    Object n = run(current);
    return n instanceof Integer ? (Integer)n : 0;
  }
  static String radio() {
    Object s = run(radio);
    return s instanceof String ? (String)s : "";
  }
}
