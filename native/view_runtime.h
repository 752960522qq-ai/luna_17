#pragma once
// Offsets and modes reviewed against the 5.1.0 ARM64 implementation.
static UpdateFn original_camera_late_update;
static void (*original_sight_type)(void *,int,const void *);
static unsigned camera_binding_failures;

static int camera_binding_ready(void *pc) {
    if(!unity_exists(pc) || !unity_exists(P(pc,0x28)) || !unity_exists(P(pc,0x30)))return 0;
    void **literal=(void **)P((void *)base,0x394f0b8);
    if(!literal)return 0;
    FN(RVA_17CAA40,void (*)(void **))(literal);
    void *gun=FN(0x343fb40,void *(*)(void *,void *,const void *))(P(pc,0x28),*literal,0);
    if(unity_exists(gun))return 1;
    camera_binding_failures++;
    __android_log_print(6,"TankInvincible","Swap cancelled: turret has no direct Gun child");
    return 0;
}

static void sight_active(void *transform,bool enabled) {
    if(!unity_exists(transform))return;
    void *go=FN(0x342de34,void *(*)(void *,const void *))(transform,0);
    if(unity_exists(go))FN(RVA_3431140,void (*)(void *,bool,const void *))(go,enabled,0);
}
static int current_ui(void *ui) {
    void *game=unity_exists(ui)?P(ui,0x300):0;
    return offline_mode() && unity_exists(game) && P(game,0x118)==player_status;
}
static void sight_type(void *ui,int kind,const void *mi) {
    if(current_ui(ui)){
        sight_active(P(ui,0x218),false);managed_store(ui,0x218,0);
    }
    original_sight_type(ui,kind,mi);
    if(!current_ui(ui) || kind!=0 || vehicle_nation_owner!=player_status || player_vehicle_nation<0 || player_vehicle_nation>5)return;
    void *sights=P(ui,0x200);
    if(!sights || I(sights,0x18)<=player_vehicle_nation)return;
    void *scope=P(sights,0x20+player_vehicle_nation*8);
    if(!unity_exists(scope))return;
    sight_active(P(ui,0x210),false);managed_store(ui,0x210,scope);sight_active(scope,true);
}
static void rebuild_player_ui(void *ui,void *pc,void *status) {
    if(!unity_exists(ui))return;
    sight_active(P(ui,0x218),false);managed_store(ui,0x218,0);
    managed_store(ui,0x320,P(pc,0x30));managed_store(ui,0x328,0);
    void *tm=P(pc,0x50);managed_store(ui,0x290,tm);
    void *guns=unity_exists(tm)?P(tm,0x48):0;
    if(B(status,0x23) && guns && I(guns,0x18)>=2 && I(guns,0x18)<=8 && unity_exists(P(guns,0x28)))managed_store(ui,0x328,P(guns,0x28));
    B(ui,0x278)=0;F(ui,0x2bc)=0; // Trajectory must be derived again.
    void *camera=P(ui,0x2f8);
    if(unity_exists(camera))I(camera,0x58)=I(status,0xcc);
    void *sights=P(ui,0x200);
    if(sights && I(sights,0x18)>=10 && original_sight_type)sight_type(ui,I(ui,0x2c),0);
}
static float pitch_limit(float value,float low,float high) {
    return value<low?low:value>high?high:value;
}
static void camera_late_update(void *camera,const void *mi) {
    void *pc=player_control,*status=player_status;
    const CustomTank *c=unity_exists(status)?tank_config(status):0;
    void *ui=unity_exists(camera)?P(camera,0xe8):0;
    // DisplayMode 2 = gun scope; Camera viewMode 0 = tank. Never override
    // air/ship/free views or a target selected by the original game.
    int scoped=c && state==3 && offline_mode() && unity_exists(pc) && unity_exists(ui) &&
        I(ui,0x30)==2 && I(camera,0x38)==0 && P(camera,0x68)==P(pc,0x28) && unity_exists(P(pc,0x30));
    float a=0,b=0;
    if(scoped){
        // Unity +X pitch points down: allowable local pitch is [-17,+4].
        I(camera,0x58)=c->elevation;
        float low=-(float)c->elevation,high=(float)c->depression;
        F(camera,0xa8)=pitch_limit(F(camera,0xa8),low,high);
        a=F(camera,0xd4);b=F(camera,0xdc);
        int width=FN(0x3402abc,int (*)(const void *))(0);
        float factor=width>0?F(camera,0x50)/width*F(camera,0x4c):0;
        if(factor!=0){
            float wanted=pitch_limit(F(camera,0xa8)-(a+b)*factor,low,high);
            F(camera,0xd4)=(F(camera,0xa8)-wanted)/factor;F(camera,0xdc)=0;
        }
    }
    original_camera_late_update(camera,mi);
    if(scoped){
        F(camera,0xd4)=a;F(camera,0xdc)=b;
        F(camera,0xa8)=pitch_limit(F(camera,0xa8),-(float)c->elevation,(float)c->depression);
        // Copy the actual gun's WORLD rotation each frame. Its parent carries
        // terrain pitch/roll; no spawn-time quaternion is frozen or flattened.
        void *transform=P(camera,0x20),*gun=P(pc,0x30);
        void *set=unity_exists(transform)?method(transform,"set_rotation",1):0;
        if(set){
            Quat q=FN(RVA_343DE40,Quat (*)(void *,const void *))(gun,0);
            ((void (*)(void *,Quat,const void *))P(set,0))(transform,q,set);
        }
    }
}
