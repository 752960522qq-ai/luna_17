#pragma once
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_configureExperience(JNIEnv *env,jclass cls,jint flags,jfloat k,jfloat khe){
    (void)env;(void)cls;
    if(flags<0 || flags>7 || !isfinite(k) || k<=0 || k>1000 || !isfinite(khe) || khe<=0 || khe>1000 || state==3)return JNI_FALSE;
    experience_k=k;experience_khe=khe;
    __atomic_store_n(&experience_flags,flags,__ATOMIC_RELEASE);return JNI_TRUE;
}
JNIEXPORT jfloatArray JNICALL Java_com_luna17_aot_NativeBridge_experienceSnapshot(JNIEnv *env,jclass cls){
    (void)cls;float values[BTE_SNAPSHOT_SIZE];
    bte_lock(&bte_snapshot_lock);memcpy(values,bte_snapshot,sizeof(values));bte_unlock(&bte_snapshot_lock);
    jfloatArray result=(*env)->NewFloatArray(env,BTE_SNAPSHOT_SIZE);
    if(result)(*env)->SetFloatArrayRegion(env,result,0,BTE_SNAPSHOT_SIZE,values);return result;
}
JNIEXPORT void JNICALL Java_com_luna17_aot_NativeBridge_experienceInput(JNIEnv *env,jclass cls,jint cycle,jfloat dx,jfloat dy,jfloat zoom,jfloat tilt){
    (void)env;(void)cls;
    if(cycle<0||cycle>1||!isfinite(dx)||!isfinite(dy)||!isfinite(zoom)||!isfinite(tilt))return;
    bte_lock(&bte_command_lock);bte_next_mode=(bte_next_mode+cycle)%3;
    bte_pan_x+=bte_limit(dx,-1,1);bte_pan_y+=bte_limit(dy,-1,1);bte_zoom+=bte_limit(zoom,-1,1);bte_tilt+=bte_limit(tilt,-20,20);
    bte_unlock(&bte_command_lock);
}
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

JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_configureFilling(JNIEnv *env,jclass cls,jstring id,jfloatArray grams,jint mask){
    (void)cls;
    if(!id || !grams || mask<1 || mask>31 || state==3 || (*env)->GetArrayLength(env,grams)!=5)return JNI_FALSE;
    float values[5];(*env)->GetFloatArrayRegion(env,grams,0,5,values);
    for(int i=0;i<5;i++)if(!isfinite(values[i]) || values[i]<0 || values[i]>100000)return JNI_FALSE;
    const char *name=(*env)->GetStringUTFChars(env,id,0);if(!name)return JNI_FALSE;
    if(!name[0] || strlen(name)>=sizeof(staged_filling.id) || hatch_find_config(name)){
        (*env)->ReleaseStringUTFChars(env,id,name);return JNI_FALSE;
    }
    snprintf(staged_filling.id,sizeof(staged_filling.id),"%s",name);
    (*env)->ReleaseStringUTFChars(env,id,name);
    memcpy(staged_filling.grams,values,sizeof(values));staged_filling.mask=mask;return JNI_TRUE;
}

JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_configureAmmunition(JNIEnv *env,jclass cls,jstring id,jfloatArray grams,jint mask){
    (void)cls;if(!id||!grams||state==3||mask<0||mask>31||(*env)->GetArrayLength(env,grams)!=5)return JNI_FALSE;
    float values[5];(*env)->GetFloatArrayRegion(env,grams,0,5,values);
    for(int i=0;i<5;i++)if(!isfinite(values[i])||values[i]<0||values[i]>100000)return JNI_FALSE;
    const char *name=(*env)->GetStringUTFChars(env,id,0);if(!name)return JNI_FALSE;
    unsigned at=0;for(;at<ammunition_count;at++)if(!strcmp(ammunition_configs[at].id,name))break;
    int ok=name[0]&&strlen(name)<sizeof(ammunition_configs[0].id)&&at<512;
    if(ok){snprintf(ammunition_configs[at].id,sizeof(ammunition_configs[at].id),"%s",name);memcpy(ammunition_configs[at].grams,values,sizeof(values));ammunition_configs[at].mask=mask;if(at==ammunition_count)ammunition_count++;}
    (*env)->ReleaseStringUTFChars(env,id,name);return ok?JNI_TRUE:JNI_FALSE;
}

JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_configureCrew(JNIEnv *env,jclass cls,jboolean enabled,jint mask){
    (void)env;(void)cls;if(state==3||mask<0||mask>131071)return JNI_FALSE;
    crew_event_mask=(unsigned)mask;
    __atomic_store_n(&crew_enabled,enabled!=0,__ATOMIC_RELEASE);return JNI_TRUE;
}
JNIEXPORT jintArray JNICALL Java_com_luna17_aot_NativeBridge_crewEvent(JNIEnv *env,jclass cls){
    (void)cls;if(!crew_gate_take())return 0;
    jintArray out=(*env)->NewIntArray(env,4);
    if(out)(*env)->SetIntArrayRegion(env,out,0,4,crew_event);else crew_gate_finish();
    return out;
}
JNIEXPORT void JNICALL Java_com_luna17_aot_NativeBridge_crewFinished(JNIEnv *env,jclass cls){
    (void)env;(void)cls;crew_gate_finish();
}

JNIEXPORT void JNICALL Java_com_luna17_aot_NativeBridge_clearTankConfiguration(JNIEnv *env,jclass cls){
    (void)env;(void)cls;memset(&staged_filling,0,sizeof(staged_filling));memset(&staged_magazine,0,sizeof(staged_magazine));memset(&staged_fire,0,sizeof(staged_fire));
}

JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_configureContinuousFire(JNIEnv *env,jclass cls,jstring id,jboolean enabled,jboolean unity_uv){
 (void)cls;if(!id)return JNI_FALSE;const char *name=(*env)->GetStringUTFChars(env,id,0);if(!name)return JNI_FALSE;
 int valid=strlen(name)<sizeof(staged_fire.id) && !hatch_find_config(name);
 if(valid){snprintf(staged_fire.id,sizeof(staged_fire.id),"%s",name);staged_fire.enabled=enabled?1:0;staged_fire.uv_unity=unity_uv?1:0;staged_fire.configured=1;}
 (*env)->ReleaseStringUTFChars(env,id,name);return valid?JNI_TRUE:JNI_FALSE;
}
