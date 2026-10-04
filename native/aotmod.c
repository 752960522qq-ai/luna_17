#include "profile_config.h"
#include <jni.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
typedef struct { const char *name; void *base; const char *symbol; void *address; } DlInfo;
extern int dladdr(const void *, DlInfo *);
extern void *mmap(void *, size_t, int, int, int, long);
extern int mprotect(void *, size_t, int);
extern int munmap(void *, size_t);
extern void *memcpy(void *, const void *, size_t);
extern void *memset(void *, int, size_t);
extern int getpagesize(void);
typedef struct { long seconds, nanoseconds; } Timespec;
extern int clock_gettime(int, Timespec *);
extern int usleep(unsigned);
extern int pthread_create(unsigned long *, const void *, void *(*)(void *), void *);
extern int pthread_detach(unsigned long);
extern int __android_log_print(int, const char *, const char *, ...);

static void clear_cache(void *start,void *end) {
    uintptr_t ctr; __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
    uintptr_t dline=4UL<<((ctr>>16)&15), iline=4UL<<(ctr&15);
    for(uintptr_t p=(uintptr_t)start&~(dline-1);p<(uintptr_t)end;p+=dline)
        __asm__ volatile("dc cvau, %0" :: "r"(p) : "memory");
    __asm__ volatile("dsb ish" ::: "memory");
    for(uintptr_t p=(uintptr_t)start&~(iline-1);p<(uintptr_t)end;p+=iline)
        __asm__ volatile("ic ivau, %0" :: "r"(p) : "memory");
    __asm__ volatile("dsb ish\nisb" ::: "memory");
}

#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
#define FN(r,t) ((t)(base+(r)))
#define MAX_TANKS 256
typedef struct { float x,y,z; } Vec3;
typedef struct { float x,y,z,w; } Quat;
typedef struct { int hash,hidden,key,fake; } ObscuredInt;
typedef void (*UpdateFn)(void *, const void *);
typedef void *(*MethodFn)(void *, const char *, int);
typedef void *(*FieldsFn)(void *, void **);

static uintptr_t base;
static volatile int ready, state, god, ammo, pending=-1, switch_result;
static void *player_control, *player_status;
static char catalog[6][MAX_TANKS][112];
static volatile int catalog_count[6];
static void *catalog_source[6];
static MethodFn class_method;
static FieldsFn class_fields;
static UpdateFn original_game_update, original_player_update;
void *original_damage, *original_set_damage, *original_engine_hit;
static long page_size=4096;
static volatile unsigned long last_update_ms;
static unsigned long now_ms(void) {
    Timespec t;
    return clock_gettime(1,&t)==0 ? (unsigned long)t.seconds*1000+t.nanoseconds/1000000 : 0;
}

static void *method(void *object,const char *name,int parameters) {
    return object && P(object,0) ? class_method(P(object,0),name,parameters) : 0;
}
static void *get_type(void *object) {
    void *m=method(object,"GetType",0);
    return m ? ((void *(*)(void *,const void *))P(m,0))(object,m) : 0;
}
static void *get_component(void *go,void *type) {
    void *m=method(go,"GetComponent",1);
    return m && type ? ((void *(*)(void *,void *,const void *))P(m,0))(go,type,m) : 0;
}
static int unity_exists(void *object) {
    return object && P(object,0x10)!=0;
}
static void managed_store(void *object,int offset,void *value) {
    P(object,offset)=value;
    FN(RVA_17CA9E4,void (*)(void **,void *))((void **)((uint8_t *)object+offset),value);
}

static void *player_tag(void) {
    // _GenerateUnit takes the managed string "Player", not a System.Type.
    // Reuse the exact metadata literal used by GeneratePlayerTank.
    void **literal=(void **)P((void *)base,RVA_394F100);
    if(!literal) return 0;
    FN(RVA_17CAA40,void (*)(void **))(literal);
    return *literal;
}

void refill_array(void *array) {
    if (!array) return;
    int n=I(array,0x18);
    if (n<1 || n>32) return;
    ObscuredInt v=FN(RVA_18F26B0,ObscuredInt (*)(int,const void *))(999,0);
    for (int i=0;i<n;i++) memcpy((uint8_t *)array+0x20+i*sizeof(v),&v,sizeof(v));
}
static void refill(void *status) {
    refill_array(P(status,FIELD_UNITSTATUS_SHELLNUMS_K__BACKINGFIELD));
    refill_array(P(status,FIELD_UNITSTATUS_SUBARMSNUMS_K__BACKINGFIELD));
}

// Return early only for the local player's current UnitStatus in an offline match.
int mod_ignore_damage(void *self) {
    return ready==1 && state==3 && god && self && player_status && P(self,0x38)==player_status;
}
int mod_ignore_engine(void *self) {
    return ready==1 && state==3 && god && self && player_status && P(self,0x40)==player_status;
}

static void utf8_name(void *text,char *out,size_t capacity) {
    size_t used=0;
    if (text) {
        int n=I(text,0x10);
        const uint16_t *chars=(const uint16_t *)((uint8_t *)text+0x14);
        if(n>0 && n<512) for(int i=0;i<n && used+4<capacity;i++) {
            unsigned c=chars[i];
            if(c<0x80) out[used++]=(char)c;
            else if(c<0x800) { out[used++]=(char)(0xc0|(c>>6)); out[used++]=(char)(0x80|(c&63)); }
            else { out[used++]=(char)(0xe0|(c>>12)); out[used++]=(char)(0x80|((c>>6)&63)); out[used++]=(char)(0x80|(c&63)); }
        }
    }
    out[used]=0;
}
static void build_catalog(void *gen) {
    static const int offsets[]={0x28,0x30,0x40,0x48,0x50,0x58};
    for(int nation=0;nation<6;nation++) {
        void *a=P(gen,offsets[nation]);
        if(!a) continue;
        int n=I(a,0x18);
        if(n<0 || n>MAX_TANKS) continue;
        if(catalog_source[nation]==a && catalog_count[nation]==n) continue;
        catalog_count[nation]=0;
        for(int i=0;i<n;i++) {
            void *go=P(a,0x20+i*8);
            void *m=method(go,"get_name",0);
            void *str=m ? ((void *(*)(void *,const void *))P(m,0))(go,m) : 0;
            utf8_name(str,catalog[nation][i],sizeof(catalog[nation][i]));
            if(!catalog[nation][i][0]) {
                char *q=catalog[nation][i];
                q[0]='#'; int v=i+1;
                q[1]=(char)('0'+v/100);q[2]=(char)('0'+v/10%10);q[3]=(char)('0'+v%10);q[4]=0;
            }
        }
        catalog_source[nation]=a;
        __atomic_store_n(&catalog_count[nation],n,__ATOMIC_RELEASE);
    }
}

static void replace_references(void *object,void **old,void **fresh,int count) {
    if(!unity_exists(object)) return;
    void *iter=0,*field;
    while((field=class_fields(P(object,0),&iter))) {
        int offset=I(field,0x18);
        if(offset<0x10 || offset>0x1800) continue;
        void *type=P(field,8);
        if(type && (I(type,8)&0x10)) continue; // static fields do not live on the instance
        int kind=type ? (I(type,8)>>16)&255 : 0;
        if(kind!=0x12 && kind!=0x1d && kind!=0x14 && kind!=0x15 && kind!=0x1c) continue;
        void *v=P(object,offset);
        if(!v) continue;
        for(int j=0;j<count;j++) if(old[j] && v==old[j]) {
            managed_store(object,offset,fresh[j]);break;
        }
    }
}

static void switch_tank(void *game,void *parameters,int command) {
    int nation=(command>>16)&255,index=command&0xffff;
    void *gen=P(game,FIELD_GAMECONTROL_TANKGENMANAGER),*old_go=P(game,FIELD_GAMECONTROL_PLAYERGO_K__BACKINGFIELD),*old_status=P(game,FIELD_GAMECONTROL_PLAYERSTATUS_K__BACKINGFIELD),*old_pc=player_control;
    if(!gen || nation>5 || index>=catalog_count[nation] || !unity_exists(old_go) || !unity_exists(old_pc) || P(old_pc,FIELD_PLAYERCONTROL_USTATUS)!=old_status) {switch_result=-1;return;}
    Vec3 pos=FN(RVA_343DBC4,Vec3 (*)(void *,const void *))(P(old_pc,FIELD_PLAYERCONTROL_THISTRF),0);
    Quat rot=FN(RVA_343DE40,Quat (*)(void *,const void *))(P(old_pc,FIELD_PLAYERCONTROL_THISTRF),0);
    void *pc_type=get_type(old_pc);
    void *tag=player_tag();
    if(!pc_type || !tag) {switch_result=-2;return;}
    void *new_go=FN(RVA_1994A88,void *(*)(void *,void *,int,int,Vec3,Quat,bool,const void *))(gen,tag,nation,index,pos,rot,false,0);
    if(!unity_exists(new_go)) {switch_result=-3;return;}
    void *new_pc=get_component(new_go,pc_type);
    if(!unity_exists(new_pc)) {
        FN(RVA_3431140,void (*)(void *,bool,const void *))(new_go,false,0);
        switch_result=-4;return;
    }
    // PlayerControl is on the prefab root; UnitStatus is on "Unit Info".
    // Use the controller's serialized reference instead of a root-only lookup.
    void *new_status=P(new_pc,FIELD_PLAYERCONTROL_USTATUS);
    if(!unity_exists(new_status)) {
        FN(RVA_3431140,void (*)(void *,bool,const void *))(new_go,false,0);
        switch_result=-5;return;
    }
    // Preserve friend/enemy identity when replacing a tank in Duel or Exercise.
    memcpy((uint8_t *)new_status+0x20,(uint8_t *)old_status+0x20,2);
    void *old[14]={old_go,old_status,old_pc},*fresh[14]={new_go,new_status,new_pc};
    static const int pc_offsets[]={0x20,0x28,0x30,0x38,0x40,0x48,0x50,0x58,0x60,0x68,0x78};
    for(int i=0;i<11;i++){old[i+3]=P(old_pc,pc_offsets[i]);fresh[i+3]=P(new_pc,pc_offsets[i]);}
    FN(RVA_1982C3C,void (*)(void *,void *,const void *))(game,new_go,0);
    FN(RVA_1982C54,void (*)(void *,void *,const void *))(game,new_status,0);
    replace_references(P(game,FIELD_GAMECONTROL_MCAMCTRL),old,fresh,14);
    replace_references(P(game,FIELD_GAMECONTROL_UIMANAGER),old,fresh,14);
    replace_references(P(game,FIELD_GAMECONTROL_POSTPROCESSCTRL),old,fresh,14);
    // The camera setter also recalculates offsets for the new turret geometry.
    if(unity_exists(P(game,FIELD_GAMECONTROL_MCAMCTRL)) && unity_exists(P(new_pc,FIELD_PLAYERCONTROL_TURRETTRF)))
        FN(RVA_191F324,void (*)(void *,void *,const void *))(P(game,FIELD_GAMECONTROL_MCAMCTRL),P(new_pc,FIELD_PLAYERCONTROL_TURRETTRF),0);
    I(parameters,FIELD_GAMEPARAMMANAGER_PLAYERNATION_K__BACKINGFIELD)=nation;I(parameters,FIELD_GAMEPARAMMANAGER_PLAYERUNITINDEX_K__BACKINGFIELD)=index;
    player_control=new_pc;player_status=new_status;
    FN(RVA_3431140,void (*)(void *,bool,const void *))(old_go,false,0);
    // Delayed destruction allows Unity to finish the current update safely.
    void *destroy=method(old_go,"Destroy",2);
    if(destroy) ((void (*)(void *,float,const void *))P(destroy,0))(old_go,0.05f,destroy);
    switch_result=1;
}

static void game_update(void *self,const void *mi) {
    original_game_update(self,mi);
    if(ready!=1)return;
    __atomic_store_n(&last_update_ms,now_ms(),__ATOMIC_RELEASE);
    void *parameters=FN(RVA_1931CFC,void *(*)(const void *))(0);
    if(!parameters) {state=2;return;}
    int mode=I(parameters,FIELD_GAMEPARAMMANAGER_GAMEMODE_K__BACKINGFIELD);
    if(mode==2) {state=4;pending=-1;player_status=0;return;}
    void *status=P(self,0x118);
    if(!unity_exists(status) || B(self,0x10c) || B(self,0x10d) || B(status,FIELD_UNITSTATUS_ISDESTROYED_K__BACKINGFIELD)) {state=2;pending=-1;return;}
    player_status=status;state=3;
    void *gen=P(self,0x48);
    if(gen) build_catalog(gen);
    int command=__atomic_exchange_n(&pending,-1,__ATOMIC_ACQ_REL);
    if(command>=0) switch_tank(self,parameters,command);
    if(ammo && player_status) refill(player_status);
}
static void player_update(void *self,const void *mi) {
    if(ready!=1) {original_player_update(self,mi);return;}
    void *s=P(self,FIELD_PLAYERCONTROL_USTATUS);
    if(state==3 && s && s==player_status) {
        player_control=self;
        if(ammo) refill(s);
    }
    original_player_update(self,mi);
    if(state==3 && s==player_status && ammo) refill(s);
}

static void emit_absolute(uint32_t **out,uintptr_t destination,unsigned reg) {
    *(*out)++=0xd2800000|((destination&0xffff)<<5)|reg;
    for(unsigned i=1;i<4;i++) *(*out)++=0xf2800000|(i<<21)|(((destination>>(i*16))&0xffff)<<5)|reg;
}
static int install(uintptr_t rva,void *replacement,void **original) {
    uint32_t *entry=(uint32_t *)(base+rva);
    uint32_t *tramp=mmap(0,(size_t)page_size,3,0x22,-1,0);
    if(tramp==(void *)-1) return 0;
    uint32_t *cursor=tramp;
    for(int i=0;i<4;i++) {
        uint32_t instruction=entry[i];
        if((instruction&0x9f000000)==0x90000000) {
            int64_t imm=((instruction>>29)&3)|(((instruction>>5)&0x7ffff)<<2);
            if(imm&(1<<20)) imm-=1<<21;
            uintptr_t target=((base+rva+i*4)&~(uintptr_t)0xfff)+(imm*4096);
            emit_absolute(&cursor,target,instruction&31);
        } else {
            // All selected prologues contain only ordinary instructions or ADRP.
            if((instruction&0x7c000000)==0x14000000 || (instruction&0x9f000000)==0x10000000 ||
               (instruction&0x3b000000)==0x18000000 || (instruction&0xff000010)==0x54000000 ||
               (instruction&0x7e000000)==0x34000000 || (instruction&0x7e000000)==0x36000000) {
                munmap(tramp,(size_t)page_size);return 0;
            }
            *cursor++=instruction;
        }
    }
    *cursor++=0x58000050;*cursor++=0xd61f0200;
    uintptr_t resume=base+rva+16;memcpy(cursor,&resume,8);
    clear_cache(tramp,(uint8_t *)cursor+8);
    if(mprotect(tramp,(size_t)page_size,5)) {munmap(tramp,(size_t)page_size);return 0;}
    *original=tramp;
    uintptr_t page=(uintptr_t)entry&~((uintptr_t)page_size-1);
    size_t span=((((uintptr_t)entry+16+page_size-1)&~((uintptr_t)page_size-1))-page);
    if(mprotect((void *)page,span,7)) return 0;
    uint32_t patch[4]={0x58000050,0xd61f0200,0,0};memcpy(patch+2,&replacement,8);
    memcpy(entry,patch,16);clear_cache(entry,(uint8_t *)entry+16);
    return mprotect((void *)page,span,5)==0;
}

extern void damage_hook(void),set_damage_hook(void),engine_hook(void);
static void *original_environment_check;
static bool environment_check(void *self,const void *mi) {
    (void)self;(void)mi;
    // The repackaged APK has a development certificate. Keep the game's
    // post-process initialization flag while allowing this local build to run.
    FN(RVA_1990580,void (*)(bool,const void *))(true,0);
    return true;
}
static void *worker(void *unused) {
    (void)unused;
    void *lib=0,*symbol=0;
    for(int i=0;i<600;i++) {
        lib=dlopen("libil2cpp.so",2|4);
        if(lib && (symbol=dlsym(lib,SYMBOL_BASE_ANCHOR))) break;
        usleep(100000);
    }
    DlInfo info;
    if(!symbol || !dladdr(symbol,&info)) {ready=-1;state=-1;return 0;}
    base=(uintptr_t)info.base;
    class_method=(MethodFn)dlsym(lib,SYMBOL_CLASS_METHOD);
    class_fields=(FieldsFn)dlsym(lib,SYMBOL_CLASS_FIELDS);
    if(!class_method || !class_fields || *(uint32_t *)(base+RVA_195D1D4)!=0xd10143ff ||
       *(uint32_t *)(base+RVA_1978CF0)!=0xd10243ff || *(uint32_t *)(base+RVA_197AA98)!=0xd10303ff ||
       *(uint32_t *)(base+RVA_197B638)!=0xfc1e0fe8 || *(uint32_t *)(base+RVA_1984348)!=0xa9be57fe ||
       *(uint32_t *)(base+RVA_1990828)!=0xd10183ff) {
        ready=-1;state=-1;return 0;
    }
    long n=getpagesize();if(n==4096 || n==16384)page_size=n;
    int ok=install(RVA_1978CF0,damage_hook,&original_damage);
    ok&=install(RVA_197AA98,set_damage_hook,&original_set_damage);
    ok&=install(RVA_197B638,engine_hook,&original_engine_hit);
    ok&=install(RVA_195D1D4,player_update,(void **)&original_player_update);
    ok&=install(RVA_1984348,game_update,(void **)&original_game_update);
    ok&=install(RVA_1990828,environment_check,&original_environment_check);
    ready=ok?1:-1;state=ok?2:-1;
    __android_log_print(ok?4:6,"Luna17","Attack on Tank 5.1.0 module %s",ok?"ready":"failed");
    return 0;
}

JNIEXPORT void JNICALL Java_com_luna17_aot_NativeBridge_init(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;
    static int started;
    if(__atomic_exchange_n(&started,1,__ATOMIC_ACQ_REL))return;
    state=1;unsigned long thread;
    if(pthread_create(&thread,0,worker,0)) {ready=-1;state=-1;} else pthread_detach(thread);
}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_state(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;
    if(state==3 && now_ms()-__atomic_load_n(&last_update_ms,__ATOMIC_ACQUIRE)>2000) return 2;
    return state;
}
JNIEXPORT jboolean JNICALL Java_com_luna17_aot_NativeBridge_toggle(JNIEnv *env,jclass cls,jint id,jboolean enabled) {
    (void)env;(void)cls;if(ready!=1 || state==4)return JNI_FALSE;
    if(id==0)god=enabled;else if(id==1)ammo=enabled;else return JNI_FALSE;
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
    if(ready!=1 || state!=3 || now_ms()-__atomic_load_n(&last_update_ms,__ATOMIC_ACQUIRE)>2000 ||
       nation<0 || nation>5 || index<0 || index>=catalog_count[nation]) return JNI_FALSE;
    switch_result=0;__atomic_store_n(&pending,(nation<<16)|index,__ATOMIC_RELEASE);return JNI_TRUE;
}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_switchResult(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;return switch_result;
}
