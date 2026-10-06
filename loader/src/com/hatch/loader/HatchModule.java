package com.hatch.loader;

import android.app.Activity;
import java.io.File;

/** Contract shared by the loader and prerequisite modules. */
public interface HatchModule {
    int apiVersion();
    void prepare(File nativeLibrary) throws Exception;
    void start(Activity activity, File nativeLibrary) throws Exception;
    String loadTank(File runtime, String manifest) throws Exception;
    void stop();
}
