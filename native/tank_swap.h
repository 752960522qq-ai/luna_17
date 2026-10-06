#pragma once
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
    return hatch_machine_gun_ready(pc);
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
    if(h>=0)apply_custom_stats(new_status);
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

