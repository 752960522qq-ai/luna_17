package com.hatch.loader;

import java.io.File;
import java.io.IOException;
import java.util.HashSet;
import java.util.Set;

/** Owns the prerequisite library in the application's native namespace. */
public final class NativeHost {
    private static String loadedPath;
    private static final Set<Class<?>> bindings = new HashSet<>();
    private NativeHost() {}
    public static synchronized void load(String path, Class<?> bridge) throws IOException {
        String canonical = new File(path).getCanonicalPath();
        if (loadedPath != null && !loadedPath.equals(canonical))
            throw new IllegalStateException("前置已在运行；更新后需完全退出游戏");
        if (loadedPath == null) {
            System.load(canonical);
            loadedPath = canonical;
        }
        if (!bindings.contains(bridge)) {
            if (!bind(bridge)) throw new IllegalStateException("无法注册前置原生接口");
            bindings.add(bridge);
        }
    }
    private static native boolean bind(Class<?> bridge);
}
