package com.luna17.aot;

final class NativeBridge {
    static boolean loaded;
    static String error = "";
    static void start() {
        try {
            System.loadLibrary("aotmod");
            loaded = true;
            init();
        } catch (Throwable failure) {
            loaded = false;
            error = failure.getClass().getSimpleName();
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
}

