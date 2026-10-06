#include "track_material.h"
// Imported tank integration; the original controllers keep their state machines.
#include "t54_asset_config.h"
#include "custom_tanks.h"
static const CustomTank *tank_config(void *status) {
    char name[64];if(!status)return 0;utf8_name(P(status,0x68),name,sizeof(name));
    const CustomTank *external=hatch_find_config(name);if(external)return external;
    for(int i=0;i<CUSTOM_TANK_COUNT;i++){int j=0;while(name[j] && name[j]==custom_tanks[i].id[j])j++;if(!name[j] && !custom_tanks[i].id[j])return &custom_tanks[i];}
    return 0;
}
#include "magazine_runtime.h"
#include "ballistics_runtime.h"
static int is_custom_tank(void *status) { return tank_config(status)!=0; }
void set_stat(void *status,int offset,int number) {
    ObscuredInt v=FN(RVA_18F26B0,ObscuredInt (*)(int,const void *))(number,0);
    memcpy((uint8_t *)status+offset,&v,sizeof(v));
}
void apply_custom_stats(void *s) {
    const CustomTank *c=tank_config(s);if(!c)return;
    set_stat(s,0x78,c->penetration);set_stat(s,0x88,c->turret_armor[0]);set_stat(s,0x98,c->body_armor[0]);set_stat(s,0xa8,c->speed);
    set_stat(s,0xdc,c->reload);set_stat(s,0x104,c->power);set_stat(s,0x114,c->max_speed);set_stat(s,0x124,c->turret_speed);
    const int *body_armor=c->body_armor,*turret_armor=c->turret_armor;
    void *b=P(s,0x1b8),*t=P(s,0x1c0);
    if(b && I(b,0x18)==16)for(int row=0;row<4;row++)for(int col=0;col<4;col++)I(b,0x20+(row*4+col)*4)=body_armor[row];
    if(t && I(t,0x18)==8)for(int row=0;row<4;row++)for(int col=0;col<2;col++)I(t,0x20+(row*2+col)*4)=turret_armor[row];
    typedef struct {unsigned raw[5];} ObscuredFloat;
    ObscuredFloat acceleration=FN(RVA_OBSCURED_FLOAT,ObscuredFloat (*)(float,const void *))((c->power/c->weight)*.5f/17.8571434f,0);
    memcpy((uint8_t *)s+0x184,&acceleration,sizeof(acceleration));
    set_stat(s,0x198,(int)((c->power/c->weight)*35.f/17.8571434f));
    F(s,0x100)=c->weight;I(s,0xc0)=c->elevation;I(s,0xc4)=c->depression;
    I(s,0xcc)=c->elevation; // Camera uses the cached negative pitch limit.
    I(s,0x14c)=c->crew;I(s,0x150)=c->crew;
    uint64_t tier=FN(RVA_OBSCURED_BYTE,uint64_t (*)(uint8_t,const void *))(c->tier,0);memcpy((uint8_t *)s+0x174,&tier,8);
}
static void status_enable(void *s,const void *mi) {
    int custom=is_custom_tank(s);void *name=custom?P(s,0x68):0,*gun_name=custom?P(s,0x70):0;
    original_status_enable(s,mi);
    if(custom){managed_store(s,0x68,name);managed_store(s,0x70,gun_name);apply_custom_stats(s);}
}
static void status_start(void *s,const void *mi) {
    original_status_start(s,mi);
    const CustomTank *c=tank_config(s);if(!c)return;
    // Verified against UnitStatus.Start: InitHeatNum goes into slot 4.
    // enum Shell: AP=0, HE=1, APCR=2, WP=3, HEAT=4.
    const int *stocks=c->ammo;void *array=P(s,0xf0);
    if(array && I(array,0x18)>=5)for(int i=0;i<I(array,0x18) && i<32;i++)write_ammo_slot(array,i,i<5?stocks[i]:0);
    write_ammo_slot(P(s,0xf8),0,c->mg_ammo);
    I(s,0x1cc)=c->ammo[2];I(s,0x1d0)=c->ammo[3];I(s,0x1d4)=c->ammo[4];
    apply_custom_stats(s);
}
static void *(*original_attack_info)(void *,int,int,const void *);
static void *attack_info(void *launcher,int shell,int flag,const void *mi) {
    void *info=original_attack_info(launcher,shell,flag,mi);
    record_shell_profile(info,0);
    const CustomTank *c=tank_config(P(launcher,0x38));
    if(info && c && !B(launcher,0xa0)){
        if(shell>=0 && shell<5 && c->shell_penetration[shell]>0)I(info,0x1c)=c->shell_penetration[shell];
        // Keep the original ammunition speed multiplier (APCR/HE/HEAT).
        float launcher_speed=F(launcher,0x54);
        if(launcher_speed>0)F(info,0x18)=F(info,0x18)*(float)c->speed/launcher_speed;
        I(info,0x50)=c->caliber;
        record_shell_profile(info,F(info,0x18));
        managed_store(info,0x20,P(P(launcher,0x38),0x260));
    }
    if(launcher==firing_launcher && info)firing_info=info;
    return info;
}
static UpdateFn original_turret_update;
static void turret_update(void *self,const void *mi) {
    const CustomTank *c=tank_config(P(self,0x40));
    if(!c){original_turret_update(self,mi);return;}
    // The game stores reload as whole seconds. Its existing float delay
    // supplies the fractional part without replacing its reload state machine.
    float saved=F(self,0x80);uint8_t enabled=B(self,0xde);
    float offset=c->reload_offset;
    if(c->magazine_capacity>=2){
        float now=FN(RVA_GAME_TIME,float (*)(const void *))(0);
        float delay=magazine_delay(P(self,0x40),c,now);
        int whole=(int)delay;if((float)whole<delay)whole++;
        set_stat(P(self,0x40),0xdc,whole);offset=delay-whole;
    }
    F(self,0x80)=offset;B(self,0xde)=1;
    original_turret_update(self,mi);
    F(self,0x80)=saved;B(self,0xde)=enabled;
}
typedef struct { Vec3 point,normal;unsigned face;float distance;float uv[2];int collider; } GroundHit;
static float previous_compression[24];
static void *suspension_owner;
static float suspension_time;
typedef struct { unsigned updates,track_updates,suspension_skips,material_misses; float left_offset,right_offset; } TrackDiagnostics;
static TrackDiagnostics track_diagnostics;
static Vec3 call_vec(void *object,const char *name) {
    void *m=method(object,name,0);return m ? ((Vec3 (*)(void *,const void *))P(m,0))(object,m) : (Vec3){0,0,0};
}
static void set_vec(void *object,const char *name,Vec3 v) {
    void *m=method(object,name,1);if(m)((void (*)(void *,Vec3,const void *))P(m,0))(object,v,m);
}
static void body_update(void *self,const void *mi) {
    void *status=P(self,0x38);
    const CustomTank *c=tank_config(status);
    if(!c){original_body_update(self,mi);return;}
    if(!offline_mode())return;
    track_diagnostics.updates++;
    void *move=P(self,0x28),*body=move?P(move,0x28):0,*wheels=P(self,0x60),*centers=P(self,0x90);
    if(!unity_exists(move))return;
    float now=FN(RVA_GAME_TIME,float (*)(const void *))(0);
    if(suspension_owner!=self){suspension_owner=self;suspension_time=now;memset(previous_compression,0,sizeof(previous_compression));memset(&track_diagnostics,0,sizeof(track_diagnostics));}
    float dt=now-suspension_time;suspension_time=now;
    if(dt<=0 || B(status,0x206))return; // Pausing the game must not accumulate impulses.
    if(dt>.1f)dt=.1f;
    float speed=F(move,0x78),rotation=F(move,0x84)*.0174532925f;
    float left=speed-rotation*1.3f,right=speed+rotation*1.3f;
    const int wheel_arrays[]={0x50,0x58};
    for(int a=0;a<2;a++){
        void *array=P(self,wheel_arrays[a]);if(!array)continue;
        int n=I(array,0x18);if(n<0 || n>28)continue;
        for(int j=0;j<n;j++){
            void *wheel=P(array,0x20+j*8);if(!unity_exists(wheel))continue;
            Vec3 angle=call_vec(wheel,"get_localEulerAngles");
            angle.x+=(j<n/2?left:right)*dt/c->radius*57.2957795f;set_vec(wheel,"set_localEulerAngles",angle);
        }
    }
    // Resolve materials on the visible renderers, not the inherited cached
    // material instances. Track motion does not depend on suspension Start.
    void *rends=P(self,0x48),*mats=P(self,0x120);
    if(rends && I(rends,0x18)==2){
        for(int j=0;j<2;j++){
            int offset=j?0xe8:0xe4;float value=F(self,offset)+(j?right:left)*dt/c->track_length;
            while(value>=1.f)value-=1.f;while(value<0.f)value+=1.f;F(self,offset)=value;
            void *rend=P(rends,0x20+j*8),*get=unity_exists(rend)?method(rend,"get_material",0):0;
            void *mat=get?((void *(*)(void *,const void *))P(get,0))(rend,get):0;
            if(unity_exists(mat) && track_set_offset(mat,value)){
                if(mats && I(mats,0x18)==2)managed_store(mats,0x20+j*8,mat);
                track_diagnostics.track_updates++;
            }else if(++track_diagnostics.material_misses==1){
                __android_log_print(6,"TankInvincible","T54 track material binding failed on side %d",j);
            }
        }
        track_diagnostics.left_offset=F(self,0xe4);track_diagnostics.right_offset=F(self,0xe8);
    }
    void *audio_source=P(self,0x20),*pitch=method(audio_source,"set_pitch",1);
    if(pitch)((void (*)(void *,float,const void *))P(pitch,0))(audio_source,1.f+(speed<0?-speed:speed)/16.f,pitch);
    if(F(move,0x74)<-c->reverse_speed)F(move,0x74)=-c->reverse_speed;
    if(F(move,0x78)<-c->reverse_speed)F(move,0x78)=-c->reverse_speed;
    if(!unity_exists(body) || !wheels || !centers || I(wheels,0x18)!=c->wheel_count || I(centers,0x18)!=c->wheel_count){
        if(++track_diagnostics.suspension_skips==1)__android_log_print(5,"TankInvincible","T54 suspension cache unavailable; tracks remain active");
        return;
    }
    // Ground mask is injected by the reviewed assets adapter, excludes units.
    for(int i=0;i<c->wheel_count;i++){
        void *wheel=P(wheels,0x20+i*8);if(!unity_exists(wheel))continue;
        Vec3 local=*(Vec3 *)((uint8_t *)centers+0x20+i*sizeof(Vec3));
        set_vec(wheel,"set_localPosition",local);
        Vec3 position=call_vec(wheel,"get_position");position.y+=c->rest;
        GroundHit hit={0};
        bool contact=FN(RVA_GROUND_RAYCAST,bool (*)(Vec3,Vec3,GroundHit *,float,int,int,const void *))(position,(Vec3){0,-1,0},&hit,c->travel+c->radius,T54_GROUND_MASK,1,0);
        float compression=contact ? c->travel+c->radius-hit.distance : 0;
        if(compression<0)compression=0;if(compression>c->travel)compression=c->travel;
        // Original game Rigidbody owns hull physics; articulation adds no force.
        float target=compression-c->rest;
        float blend=dt/(.08f+dt);
        previous_compression[i]+=(target-previous_compression[i])*blend;
        if(previous_compression[i]>c->rest)previous_compression[i]=c->rest;
        if(previous_compression[i]<-c->rest)previous_compression[i]=-c->rest;
        local.y+=previous_compression[i];set_vec(wheel,"set_localPosition",local);
    }
}



