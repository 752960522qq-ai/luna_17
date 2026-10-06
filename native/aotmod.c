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

#include "hatch_data.h"
static void utf8_name(void *,char *,size_t);
#include "hatch_engine.h"
void t54_stats(void *);
static void *player_tag(void) {
    // _GenerateUnit takes the managed string "Player", not a System.Type.
    // Reuse the exact metadata literal used by GeneratePlayerTank.
    void **literal=(void **)P((void *)base,RVA_394F100);
    if(!literal) return 0;
    FN(RVA_17CAA40,void (*)(void **))(literal);
    return *literal;
}

typedef struct { void *owner,*arrays[2]; int counts[2]; ObscuredInt slots[2][32]; } AmmoSnapshot;
static AmmoSnapshot ammo_snapshot;
static int plain_int(ObscuredInt v) { return (int)(((unsigned)v.hidden-(unsigned)v.key)^(unsigned)v.key); }
void write_ammo_slot(void *array,int index,int count) {
    if(!array || index<0 || index>=I(array,0x18) || I(array,0x18)>32 || count<0)return;
    ObscuredInt v=FN(RVA_18F26B0,ObscuredInt (*)(int,const void *))(count,0);
    memcpy((uint8_t *)array+0x20+index*sizeof(v),&v,sizeof(v));
}
void refill(void *status) {
    if(!status)return;
    if(ammo_snapshot.owner!=status){memset(&ammo_snapshot,0,sizeof(ammo_snapshot));ammo_snapshot.owner=status;}
    const int offsets[]={FIELD_UNITSTATUS_SHELLNUMS_K__BACKINGFIELD,FIELD_UNITSTATUS_SUBARMSNUMS_K__BACKINGFIELD};
    for(int a=0;a<2;a++){
        void *array=P(status,offsets[a]);if(!array)continue;
        int n=I(array,0x18);if(n<1 || n>32)continue;
        ObscuredInt *values=(ObscuredInt *)((uint8_t *)array+0x20);
        if(ammo_snapshot.arrays[a]!=array || ammo_snapshot.counts[a]!=n){
            ammo_snapshot.arrays[a]=array;ammo_snapshot.counts[a]=n;
            memcpy(ammo_snapshot.slots[a],values,n*sizeof(*values));
        }
        for(int i=0;i<n;i++)if(plain_int(ammo_snapshot.slots[a][i])>0 && plain_int(values[i])<plain_int(ammo_snapshot.slots[a][i]))
            memcpy(values+i,&ammo_snapshot.slots[a][i],sizeof(*values));
    }
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
        unsigned generation=__atomic_load_n(&hatch_count,__ATOMIC_ACQUIRE);
        if(catalog_source[nation]==a && catalog_stock[nation]==n && catalog_generation[nation]==generation) continue;
        catalog_count[nation]=0;
        for(int i=0;i<n;i++) {
            catalog_hatch[nation][i]=-1;
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
        catalog_stock[nation]=n;
        for(unsigned h=0;h<generation && n<MAX_TANKS;h++)if(hatch_tanks[h].disk.nation==(unsigned)nation){
            snprintf(catalog[nation][n],sizeof(catalog[nation][n]),"Hatch · %s",hatch_tanks[h].disk.id);
            catalog_hatch[nation][n++]=(int)h;
        }
        catalog_source[nation]=a;catalog_generation[nation]=generation;
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

typedef struct { void *game,*old_go,*old_status,*old_pc,*new_go,*new_status,*new_pc; int frames,battle_nation,vehicle_nation,phase,previous_vehicle_nation; } SwapTransaction;
static SwapTransaction swap;
static void bind_player(void *go,void *status,void *pc,void *old_go,void *old_status,void *old_pc,int nation) {
    void *game=swap.game;
    void *old[14]={old_go,old_status,old_pc},*fresh[14]={go,status,pc};
    static const int pc_offsets[]={0x20,0x28,0x30,0x38,0x40,0x48,0x50,0x58,0x60,0x68,0x78};
    for(int i=0;i<11;i++){old[i+3]=P(old_pc,pc_offsets[i]);fresh[i+3]=P(pc,pc_offsets[i]);}
    FN(RVA_1982C3C,void (*)(void *,void *,const void *))(game,go,0);
    FN(RVA_1982C54,void (*)(void *,void *,const void *))(game,status,0);
    void *camera=P(game,FIELD_GAMECONTROL_MCAMCTRL),*ui=P(game,FIELD_GAMECONTROL_UIMANAGER);
    replace_references(camera,old,fresh,14);replace_references(ui,old,fresh,14);
    replace_references(P(game,FIELD_GAMECONTROL_POSTPROCESSCTRL),old,fresh,14);
    player_control=pc;player_status=status;player_vehicle_nation=nation;vehicle_nation_owner=status;
    B(status,0x202)=1;
    if(unity_exists(camera))FN(RVA_191F324,void (*)(void *,void *,const void *))(camera,P(pc,0x28),0);
    rebuild_player_ui(ui,pc,status);
    memset(&ammo_snapshot,0,sizeof(ammo_snapshot));
}
static void discard_new(int error) {
    if(swap.phase && unity_exists(swap.old_go)){
        FN(RVA_3431140,void (*)(void *,bool,const void *))(swap.old_go,true,0);
        bind_player(swap.old_go,swap.old_status,swap.old_pc,swap.new_go,swap.new_status,swap.new_pc,swap.previous_vehicle_nation);
    }
    if(unity_exists(swap.new_go))FN(RVA_3431140,void (*)(void *,bool,const void *))(swap.new_go,false,0);
    switch_result=error;memset(&swap,0,sizeof(swap));
}
static int weapon_ready(void *pc,void *status,void *game) {
    void *array=P(pc,0x58);if(!array)return 0;
    int n=I(array,0x18);if(n<1 || n>8)return 0;
    int power=plain_int(*(ObscuredInt *)((uint8_t *)status+0x78));
    int speed=plain_int(*(ObscuredInt *)((uint8_t *)status+0xa8));
    if(power<=0 || speed<=0 || !P(status,0xf0))return 0;
    for(int i=0;i<n;i++){
        void *launcher=P(array,0x20+i*8);
        if(!unity_exists(launcher) || !unity_exists(P(launcher,0x20)))return 0;
        managed_store(launcher,0x38,status);managed_store(launcher,0xb0,game);
        if(!B(launcher,0xa0)){I(launcher,0x50)=power;F(launcher,0x54)=(float)speed;}
        if(I(launcher,0x50)<=0 || F(launcher,0x54)<=0)return 0;
    }
    return 1;
}
static void advance_swap(void *game) {
    if(!swap.new_go)return;
    if(game!=swap.game || state!=3 || !unity_exists(swap.old_go) || B(swap.old_status,0x206)){discard_new(-6);return;}
    if(++swap.frames<2)return; // Unity Start must run before handing over control.
    if(swap.phase){
        void *check=method(swap.old_go,"get_activeSelf",0);
        int active=check?((bool (*)(void *,const void *))P(check,0))(swap.old_go,check):1;
        if(active){discard_new(-8);return;}
        switch_result=1;memset(&swap,0,sizeof(swap));return;
    }
    if(!weapon_ready(swap.new_pc,swap.new_status,game)){
        if(swap.frames>=120)discard_new(-7);
        return;
    }
    if(!camera_binding_ready(swap.new_pc)){discard_new(-9);return;}
    // Mark the one-time handover before callbacks. Later frames only verify
    // retirement; they never rebind a camera that has switched to an aircraft.
    swap.phase=1;
    bind_player(swap.new_go,swap.new_status,swap.new_pc,swap.old_go,swap.old_status,swap.old_pc,swap.vehicle_nation);
    FN(RVA_3431140,void (*)(void *,bool,const void *))(swap.old_go,false,0);
    // Retain the attacker Transform while shells already in flight finish.
    // Do not destroy a retired unit whose projectiles may still reference it.
    // Scene unload reclaims inactive retired tanks and their shell pools.
    switch_result=0;
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
    int h=(catalog_generation[nation]>0 && index>=catalog_stock[nation])?catalog_hatch[nation][index]:-1,template_nation=nation,template_index=index;
    if(h>=0){
        template_nation=0;template_index=-1;
        for(int i=0;i<catalog_stock[0];i++)if(!strcmp(catalog[0][i],"T34_85_Player") || !strcmp(catalog[0][i],"T34_85")){template_index=i;break;}
        if(template_index<0){switch_result=-21;return;}
    }
    void *new_go=FN(RVA_1994A88,void *(*)(void *,void *,int,int,Vec3,Quat,bool,const void *))(gen,tag,template_nation,template_index,pos,rot,false,0);
    if(!unity_exists(new_go)) {switch_result=-3;return;}
    void *new_pc=get_component(new_go,pc_type);
    if(!unity_exists(new_pc)) {
        FN(RVA_3431140,void (*)(void *,bool,const void *))(new_go,false,0);
        switch_result=-4;return;
    }
    // Keep the serialized child UnitStatus reference.
    void *new_status=P(new_pc,FIELD_PLAYERCONTROL_USTATUS);
    if(!unity_exists(new_status)) {
        FN(RVA_3431140,void (*)(void *,bool,const void *))(new_go,false,0);
        switch_result=-5;return;
    }
    if(h>=0 && !hatch_apply_tank(&hatch_tanks[h],new_go,new_pc,new_status)){
        FN(RVA_3431140,void (*)(void *,bool,const void *))(new_go,false,0);
        FN(RVA_1982C3C,void (*)(void *,void *,const void *))(game,old_go,0);
        FN(RVA_1982C54,void (*)(void *,void *,const void *))(game,old_status,0);
        switch_result=-20;return;
    }
    if(h>=0)t54_stats(new_status);
    memcpy((uint8_t *)new_status+0x20,(uint8_t *)old_status+0x20,2);
    I(new_status,0x64)=I(old_status,0x64); // UnitNation is battle identity, separate from the catalog nationality.
    B(new_status,0x202)=0;
    // OnEnable chose a detection layer before we restored the battle identity.
    void *om=method(old_status,"get_gameObject",0),*nm=method(new_status,"get_gameObject",0);
    if(om && nm){
        void *og=((void *(*)(void *,const void *))P(om,0))(old_status,om);
        void *ng=((void *(*)(void *,const void *))P(nm,0))(new_status,nm);
        void *lm=method(og,"get_layer",0),*sm=method(ng,"set_layer",1);
        if(lm && sm)((void (*)(void *,int,const void *))P(sm,0))(ng,((int (*)(void *,const void *))P(lm,0))(og,lm),sm);
    }
    swap=(SwapTransaction){game,old_go,old_status,old_pc,new_go,new_status,new_pc,0,I(parameters,0x5c),nation,0,player_vehicle_nation};
    FN(RVA_1982C3C,void (*)(void *,void *,const void *))(game,old_go,0);
    FN(RVA_1982C54,void (*)(void *,void *,const void *))(game,old_status,0);
    switch_result=0;
}

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

static void emit_absolute(uint32_t **out,uintptr_t destination,unsigned reg) {
    *(*out)++=0xd2800000|((destination&0xffff)<<5)|reg;
    for(unsigned i=1;i<4;i++) *(*out)++=0xf2800000|(i<<21)|(((destination>>(i*16))&0xffff)<<5)|reg;
}
int install(uintptr_t rva,void *replacement,void **original) {
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
        } else if((instruction&0x7c000000)==0x14000000) {
            int64_t imm=instruction&0x3ffffff;
            if(imm&(1<<25))imm-=1<<26;
            uintptr_t target=base+rva+i*4+imm*4;
            if(target>=base+rva && target<base+rva+16){munmap(tramp,(size_t)page_size);return 0;}
            emit_absolute(&cursor,target,16);
            *cursor++=(instruction&0x80000000)?0xd63f0200:0xd61f0200;
        } else {
            // All selected prologues contain only ordinary instructions or ADRP.
            if((instruction&0x9f000000)==0x10000000 ||
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
#include "t54_runtime.h"
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
       *(uint32_t *)(base+RVA_1990828)!=0xd10183ff) {
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
    ok&=install(RVA_CAMERA_LATE_UPDATE,camera_late_update,(void **)&original_camera_late_update);
    ok&=install(RVA_UI_SIGHT,sight_type,(void **)&original_sight_type);
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
    if(ready!=1 || state!=3 || swap.new_go || now_ms()-__atomic_load_n(&last_update_ms,__ATOMIC_ACQUIRE)>2000 ||
       nation<0 || nation>5 || index<0 || index>=catalog_count[nation]) return JNI_FALSE;
    switch_result=0;__atomic_store_n(&pending,(nation<<16)|index,__ATOMIC_RELEASE);return JNI_TRUE;
}
JNIEXPORT jint JNICALL Java_com_luna17_aot_NativeBridge_switchResult(JNIEnv *env,jclass cls) {
    (void)env;(void)cls;return switch_result;
}


JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_loadHatch(JNIEnv *env,jclass cls,jstring path){
    (void)cls;const char *p=(*env)->GetStringUTFChars(env,path,0);
    if(!p)return 0;int ok=hatch_load_file(p);(*env)->ReleaseStringUTFChars(env,path,p);
    return (*env)->NewStringUTF(env,ok?"":hatch_error);
}
JNIEXPORT jstring JNICALL Java_com_luna17_aot_NativeBridge_hatchError(JNIEnv *env,jclass cls){
    (void)cls;return (*env)->NewStringUTF(env,hatch_error);
}

