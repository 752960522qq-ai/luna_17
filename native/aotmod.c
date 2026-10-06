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
#define F(o,n) (*(float *)((uint8_t *)(o)+(n)))
typedef void (*UpdateFn)(void *, const void *);
typedef void *(*MethodFn)(void *, const char *, int);
typedef void *(*FieldsFn)(void *, void **);

static uintptr_t base;
static int offline_mode(void);
static __attribute__((noinline)) void rebuild_player_ui(void *,void *,void *);
static int camera_binding_ready(void *);
static int player_vehicle_nation=-1;
static void *vehicle_nation_owner;
static volatile int ready, state, god, ammo, pending=-1, switch_result;
static void *player_control, *player_status;
static char catalog[6][MAX_TANKS][112];
static volatile int catalog_count[6];
static void *catalog_source[6];
static int catalog_stock[6],catalog_hatch[6][MAX_TANKS];
static unsigned catalog_generation[6];
static MethodFn class_method;
static FieldsFn class_fields;
static UpdateFn original_game_update, original_player_update, original_status_enable, original_status_start, original_body_update, original_title_start;
void *original_damage, *original_set_damage, *original_engine_hit;
static long page_size=4096;
static volatile unsigned long last_update_ms;
static unsigned long now_ms(void) {
    Timespec t;
    return clock_gettime(1,&t)==0 ? (unsigned long)t.seconds*1000+t.nanoseconds/1000000 : 0;
}

#include "runtime_support.h"

#include "hatch_data.h"
static void utf8_name(void *,char *,size_t);
#include "hatch_engine.h"
void apply_custom_stats(void *);
static void *player_tag(void) {
    // _GenerateUnit takes the managed string "Player", not a System.Type.
    // Reuse the exact metadata literal used by GeneratePlayerTank.
    void **literal=(void **)P((void *)base,RVA_394F100);
    if(!literal) return 0;
    FN(RVA_17CAA40,void (*)(void **))(literal);
    return *literal;
}

#include "ammo_runtime.h"

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
#include "tank_catalog.h"

#include "tank_swap.h"

static void game_update(void *self,const void *mi) {
    original_game_update(self,mi);
    if(ready!=1)return;
    __atomic_store_n(&last_update_ms,now_ms(),__ATOMIC_RELEASE);
    void *parameters=FN(RVA_1931CFC,void *(*)(const void *))(0);
    if(!parameters) {state=2;return;}
    int mode=I(parameters,FIELD_GAMEPARAMMANAGER_GAMEMODE_K__BACKINGFIELD);
    if(mode==2) {state=4;pending=-1;discard_new(-6);player_status=0;return;}
    void *status=P(self,0x118);
    if(!unity_exists(status) || B(self,0x10c) || B(self,0x10d) || B(status,FIELD_UNITSTATUS_ISDESTROYED_K__BACKINGFIELD)) {state=2;pending=-1;discard_new(-6);return;}
    player_status=status;state=3;
    if(vehicle_nation_owner!=status && !swap.new_go){player_vehicle_nation=I(parameters,0x5c);vehicle_nation_owner=status;}
    void *gen=P(self,0x48);
    if(gen) build_catalog(gen);
    int command=__atomic_exchange_n(&pending,-1,__ATOMIC_ACQ_REL);
    if(command>=0 && !swap.new_go) switch_tank(self,parameters,command);
    advance_swap(self);
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

#include "hook_installer.h"

extern void damage_hook(void),set_damage_hook(void),engine_hook(void);
static void *original_environment_check;
static int offline_mode(void);
static bool environment_check(void *self,const void *mi) {
    if(!offline_mode())return ((bool (*)(void *,const void *))original_environment_check)(self,mi);
    (void)self;(void)mi;
    // The repackaged APK has a development certificate. Keep the game's
    // post-process initialization flag while allowing this local build to run.
    FN(RVA_1990580,void (*)(bool,const void *))(true,0);
    return true;
}
#include "offline_launch.h"
#include "imported_tanks.h"
#include "view_runtime.h"

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
       *(uint32_t *)(base+RVA_1990828)!=0xd10183ff ||
       *(uint32_t *)(base+RVA_LAUNCHER_FIRE)!=0xd10283ff ||
       *(uint32_t *)(base+RVA_SHELL_FIXED_UPDATE)!=0xd10443ff) {
        ready=-1;state=-1;return 0;
    }
    if(!hatch_bind(lib)){ready=-1;state=-1;return 0;}
    long n=getpagesize();if(n==4096 || n==16384)page_size=n;
    int ok=install(RVA_1978CF0,damage_hook,&original_damage);
    ok&=install(RVA_197AA98,set_damage_hook,&original_set_damage);
    ok&=install(RVA_197B638,engine_hook,&original_engine_hit);
    ok&=install(RVA_195D1D4,player_update,(void **)&original_player_update);
    ok&=install(RVA_1984348,game_update,(void **)&original_game_update);
    ok&=install(RVA_1990828,environment_check,&original_environment_check);
    ok&=install(RVA_TITLE_START,title_start,(void **)&original_title_start);
    ok&=install(RVA_IS_PRODUCT,product_check,(void **)&original_product_check);
    ok&=install(RVA_LOAD_FLAG,load_flag,(void **)&original_load_flag);
    ok&=install(RVA_IS_HNZ2,hnz_check,(void **)&original_hnz_check);
    ok&=install(RVA_IAP_SANITY,iap_sanity,(void **)&original_iap_sanity);
    ok&=install(RVA_STATUS_ENABLE,status_enable,(void **)&original_status_enable);
    ok&=install(RVA_STATUS_START,status_start,(void **)&original_status_start);
    ok&=install(RVA_BODY_UPDATE,body_update,(void **)&original_body_update);
    ok&=install(RVA_ATTACK_INFO,attack_info,(void **)&original_attack_info);
    ok&=install(RVA_TURRET_UPDATE,turret_update,(void **)&original_turret_update);
    ok&=install(RVA_LAUNCHER_FIRE,launcher_fire,(void **)&original_launcher_fire);
    ok&=install(RVA_SHELL_FIXED_UPDATE,shell_fixed_update,(void **)&original_shell_fixed_update);
    ok&=install(RVA_CAMERA_LATE_UPDATE,camera_late_update,(void **)&original_camera_late_update);
    ok&=install(RVA_UI_SIGHT,sight_type,(void **)&original_sight_type);
    ready=ok?1:-1;state=ok?2:-1;
    __android_log_print(ok?4:6,"Luna17","Attack on Tank 5.1.0 module %s",ok?"ready":"failed");
    return 0;
}

#include "jni_bridge.h"

