package com.hatch.loader;

import java.io.File;

/** Keeps code ownership and the first startup result for the whole process. */
final class ModuleSession {
    interface Factory { Loaded create() throws Exception; }
    static final class Loaded {
        final HatchModule module;
        final File library;
        final ClassLoader loader;
        Loaded(HatchModule module, File library, ClassLoader loader) {
            this.module=module; this.library=library; this.loader=loader;
        }
    }
    private Loaded resident;
    private Throwable failure;
    private boolean ready;
    synchronized Loaded prepare(Factory factory) throws Exception {
        if (failure != null)
            throw new IllegalStateException("前置启动失败（保留首次原因）: " + failure.getMessage(),failure);
        if (ready) return resident;
        try {
            if (resident == null) resident=factory.create();
            if (resident == null) return null;
            resident.module.prepare(resident.library);
            ready=true;
            return resident;
        } catch (Exception | LinkageError error) {
            failure=error;
            throw error;
        }
    }
}
