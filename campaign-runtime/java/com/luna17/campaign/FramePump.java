package com.luna17.campaign;

import com.hatch.loader.GameFrameHost;
import java.util.concurrent.atomic.AtomicBoolean;

/** Poll from the Android UI; at most one task may wait in the player's own frame queue. */
final class FramePump {
    private final GameFrameHost host;
    private final Runnable step;
    private final AtomicBoolean queued = new AtomicBoolean();
    private volatile boolean live = true;
    FramePump(GameFrameHost host, Runnable step) { this.host = host; this.step = step; }
    void tick() {
        final int session = host.frameSession();
        if (!live || session == 0 || !queued.compareAndSet(false, true)) return;
        if (!host.postGameFrame(() -> {
            try {
                if (live && session == host.frameSession()) step.run();
            } finally { queued.set(false); }
        })) queued.set(false);
    }
    void stop() { live = false; }
}
