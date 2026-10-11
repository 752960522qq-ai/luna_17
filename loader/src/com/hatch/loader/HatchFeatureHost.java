package com.hatch.loader;

/** Optional extension; existing API-2 tank modules remain binary compatible. */
public interface HatchFeatureHost {
    String[] capabilities();
    String loadFeatures(String id, String configuration) throws Exception;
}
