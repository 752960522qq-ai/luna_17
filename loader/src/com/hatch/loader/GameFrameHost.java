package com.hatch.loader;

/** Valid only for a visible, interactive Unity player. Zero means suspended. */
public interface GameFrameHost {
    int frameSession();
    boolean postGameFrame(Runnable work);
}
