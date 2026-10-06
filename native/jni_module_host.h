#pragma once
// The parent loader owns the library. Bind child module classes explicitly,
// rather than asking ART to load the same library for each DexClassLoader.
JNIEXPORT jboolean JNICALL Java_com_hatch_loader_NativeHost_bind(JNIEnv *env,jclass host,jclass bridge) {
    (void)host;
    if(!bridge)return JNI_FALSE;
    const JNINativeMethod methods[]={
#define NATIVE(name, signature) {#name,signature,(void *)Java_com_luna17_aot_NativeBridge_##name}
        NATIVE(init,"()V"),
        NATIVE(state,"()I"),
        NATIVE(initError,"()Ljava/lang/String;"),
        NATIVE(toggle,"(IZ)Z"),
        NATIVE(tanks,"(I)[Ljava/lang/String;"),
        NATIVE(switchTank,"(II)Z"),
        NATIVE(switchResult,"()I"),
        NATIVE(loadHatch,"(Ljava/lang/String;)Ljava/lang/String;"),
        NATIVE(hatchError,"()Ljava/lang/String;"),
        NATIVE(configureMagazine,"(Ljava/lang/String;IFF)Z")
#undef NATIVE
    };
    return (*env)->RegisterNatives(env,bridge,methods,sizeof(methods)/sizeof(methods[0]))==JNI_OK?JNI_TRUE:JNI_FALSE;
}
