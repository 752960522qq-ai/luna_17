package com.luna17.aot;

final class NativeBridge {
    static boolean loaded;
    static String error = "";
    static void start(String path) {
        try {
            System.load(path);
            init();
            if (state() != 2) throw new IllegalStateException("原生钩子初始化失败");
            loaded = true;
        } catch (Throwable failure) {
            loaded = false;
            error = failure.getClass().getSimpleName() + ": " + failure.getMessage();
        }
    }
    private static native void init();
    static native int state();
    static native boolean toggle(int feature, boolean enabled);
    static native String[] tanks(int nation);
    static native boolean switchTank(int nation, int index);
    static native int switchResult();
    static native String loadHatch(String path);
    static native String hatchError();
    static native boolean configureMagazine(String id, int capacity, float interval, float reload);
}


