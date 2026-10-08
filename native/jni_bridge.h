#pragma once
JNIEXPORT void JNICALL Java_com_luna17_aot_NativeBridge_init(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;
    static int started;
    if(__atomic_exchange_n(&started,1,__ATOMIC_ACQ_REL))return;
    // The launcher has loaded IL2CPP but has not started Unity yet.
    // Complete installation on this thread before allowing game startup.
    state=1;worker(0);
}
JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_initError(JNIEnv *env,jclass cls) {
    (void)cls;return (*env)->NewStringUTF(env,startup_error[0]?startup_error:"unknown native startup failure");
}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_state(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;
    if(state==3 && now_ms()-__atomic_load_n(&last_update_ms,__ATOMIC_ACQUIRE)>2000) return 2;
    return state;
}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_toggle(JNIEnv *env,jclass cls,jint id,jboolean enabled) {
    (void)env;(void)cls;if(ready!=1 || state==4)return JNI_FALSE;
    if(id==0)god=enabled;else if(id==1){ammo=enabled;memset(&ammo_snapshot,0,sizeof(ammo_snapshot));}else return JNI_FALSE;
    return JNI_TRUE;
}
JNIEXPORT jobjectArray JNICALL Java_com_luna17_aot_NativeBridge_tanks(JNIEnv *env,jclass cls,jint nation) {
    (void)cls;jclass str=(*env)->FindClass(env,"java/lang/String");
    int n=(nation>=0&&nation<6)?__atomic_load_n(&catalog_count[nation],__ATOMIC_ACQUIRE):0;
    jobjectArray out=(*env)->NewObjectArray(env,n,str,0);
    for(int i=0;i<n;i++) {jstring s=(*env)->NewStringUTF(env,catalog[nation][i]);(*env)->SetObjectArrayElement(env,out,i,s);(*env)->DeleteLocalRef(env,s);}
    return out;
}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_switchTank(JNIEnv *env,jclass cls,jint nation,jint index) {
    (void)env;(void)cls;
    if(ready!=1 || state!=3 || swap.new_go || enemy_pending>=0 || now_ms()-__atomic_load_n(&last_update_ms,__ATOMIC_ACQUIRE)>2000 ||
       nation<0 || nation>5 || index<0 || index>=catalog_count[nation]) return JNI_FALSE;
    switch_result=0;__atomic_store_n(&pending,(nation<<16)|index,__ATOMIC_RELEASE);return JNI_TRUE;
}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_switchResult(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;return switch_result;
}

JNIEXPORT jobjectArray JNICALL Java_com_luna17_aot_NativeBridge_enemyTanks(JNIEnv *env,jclass cls,jint nation) {
    (void)cls;jclass str=(*env)->FindClass(env,"java/lang/String");
    int n=(nation>=0&&nation<6)?__atomic_load_n(&enemy_count[nation],__ATOMIC_ACQUIRE):0;
    jobjectArray out=(*env)->NewObjectArray(env,n,str,0);
    for(int i=0;i<n;i++){jstring s=(*env)->NewStringUTF(env,enemy_catalog[nation][i]);(*env)->SetObjectArrayElement(env,out,i,s);(*env)->DeleteLocalRef(env,s);}
    return out;
}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_spawnEnemy(JNIEnv *env,jclass cls,jint nation,jint index) {
    (void)env;(void)cls;
    if(ready!=1 || state!=3 || swap.new_go || pending>=0 || now_ms()-__atomic_load_n(&last_update_ms,__ATOMIC_ACQUIRE)>2000 ||
       nation<0 || nation>5 || index<0 || index>=enemy_count[nation])return JNI_FALSE;
    if(__atomic_exchange_n(&enemy_request_lock,1,__ATOMIC_ACQ_REL))return JNI_FALSE;
    if(__atomic_load_n(&enemy_pending,__ATOMIC_ACQUIRE)>=0){
        __atomic_store_n(&enemy_request_lock,0,__ATOMIC_RELEASE);return JNI_FALSE;
    }
    enemy_result=0;
    __atomic_store_n(&enemy_pending,(nation<<16)|index,__ATOMIC_RELEASE);
    __atomic_store_n(&enemy_request_lock,0,__ATOMIC_RELEASE);
    return JNI_TRUE;
}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_spawnEnemyResult(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;return enemy_result;
}

JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_loadHatch(JNIEnv *env,jclass cls,jstring path){
    (void)cls;const char *p=(*env)->GetStringUTFChars(env,path,0);
    if(!p)return 0;int ok=hatch_load_file(p);(*env)->ReleaseStringUTFChars(env,path,p);
    return (*env)->NewStringUTF(env,ok?"":hatch_error);
}
JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_hatchError(JNIEnv *env,jclass cls){
    (void)cls;return (*env)->NewStringUTF(env,hatch_error);
}

JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_configureMagazine(JNIEnv *env,jclass cls,jstring id,jint capacity,jfloat interval,jfloat reload){
    (void)cls;
    if(!id || capacity<2 || capacity>200 || !isfinite(interval) || interval<.03f || interval>60.f || !isfinite(reload) || reload<interval || reload>300.f)return JNI_FALSE;
    const char *name=(*env)->GetStringUTFChars(env,id,0);if(!name)return JNI_FALSE;
    if(strlen(name)>=sizeof(staged_magazine.id) || hatch_find_config(name)){
        (*env)->ReleaseStringUTFChars(env,id,name);return JNI_FALSE;
    }
    snprintf(staged_magazine.id,sizeof(staged_magazine.id),"%s",name);
    staged_magazine.capacity=capacity;staged_magazine.interval=interval;staged_magazine.reload=reload;
    (*env)->ReleaseStringUTFChars(env,id,name);
    return JNI_TRUE;
}
