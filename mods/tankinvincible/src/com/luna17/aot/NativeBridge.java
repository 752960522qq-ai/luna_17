package com.luna17.aot;

import com.hatch.loader.NativeHost;

final class NativeBridge {
    static boolean loaded;
    static boolean libraryLoaded;
    static String error = "";
    static synchronized void start(String path) {
        if (loaded || !error.isEmpty()) return;
        try {
            NativeHost.load(path,NativeBridge.class);
            libraryLoaded = true;
            init();
            if (state() != 2) throw new IllegalStateException("原生钩子初始化失败: "+initError());
            loaded = true;
        } catch (Exception | LinkageError failure) {
            loaded = false;
            error = failure.getClass().getSimpleName() + ": " + failure.getMessage();
        }
    }
    private static native void init();
    static native int state();
    private static native String initError();
    static native boolean toggle(int feature, boolean enabled);
    static native String[] tanks(int nation);
    static native boolean switchTank(int nation, int index);
    static native int switchResult();
    static native String[] enemyTanks(int nation);
    static native boolean spawnEnemy(int nation, int index);
    static native int spawnEnemyResult();
    static native String loadHatch(String path);
    static native String hatchError();
    static native boolean configureMagazine(String id, int capacity, float interval, float reload);
}


