#pragma once

typedef struct {
    void *status;
    int remaining;
    float last_shot, observed_time;
} MagazineState;
static MagazineState magazine_state;
static void *firing_launcher, *firing_info;
static void (*original_launcher_fire)(void *,int,int,const void *);

static MagazineState *magazine_for(void *status,const CustomTank *config,float now) {
    if(!config || config->magazine_capacity<2)return 0;
    if(magazine_state.status!=status || now<magazine_state.observed_time){
        magazine_state=(MagazineState){status,config->magazine_capacity,now,now};
    }
    magazine_state.observed_time=now;
    if(magazine_state.remaining==0 && now-magazine_state.last_shot>=config->magazine_reload)
        magazine_state.remaining=config->magazine_capacity;
    return &magazine_state;
}
static float magazine_delay(void *status,const CustomTank *config,float now) {
    MagazineState *state=magazine_for(status,config,now);
    return state && state->remaining==0?config->magazine_reload:config->shot_interval;
}
// Reserve an inactive object before the game's Fire path plays any effects.
// Never recycle an active shot; it may still be travelling toward its target.
static int magazine_reserve_shell(void *launcher,int shell){
    int offset=shell==1?0x80:0x78;
    void *pool=P(launcher,offset);int count=pool?I(pool,0x18):0;
    if(count<1 || count>256)return 0;
    for(int i=0;i<count;i++){
        void *go=P(pool,0x20+i*8);if(!unity_exists(go))continue;
        void *m=method(go,"get_activeSelf",0);
        if(m && !((bool (*)(void *,const void *))P(m,0))(go,m))return 1;
    }
    if(count==256 || !hatch_engine_ok)return 0;
    void *object=hatch_class("UnityEngine","Object"),*gameobject=hatch_class("UnityEngine","GameObject");
    void *instantiate=hatch_method(object,"Instantiate",1,object);
    if(!instantiate || !gameobject)return 0;
    void *source=P(pool,0x20),*args[]={source},*exception=0;
    void *clone=ha_invoke(instantiate,0,args,&exception);
    if(exception || !unity_exists(clone))return 0;
    FN(RVA_3431140,void (*)(void *,bool,const void *))(clone,false,0);
    void *expanded=ha_array(gameobject,count+1);
    if(!expanded){
        void *destroy=class_method(object,"Destroy",1),*cleanup[]={clone};
        if(destroy)ha_invoke(destroy,0,cleanup,&exception);
        return 0;
    }
    for(int i=0;i<count;i++)managed_store(expanded,0x20+i*8,P(pool,0x20+i*8));
    managed_store(expanded,0x20+count*8,clone);managed_store(launcher,offset,expanded);
    return 1;
}
static void launcher_fire(void *launcher,int shell,int flag,const void *mi) {
    void *status=P(launcher,0x38);
    const CustomTank *config=tank_config(status);
    int tracked=config && config->magazine_capacity>=2 && !B(launcher,0xa0) && shell>=0 && shell<5;
    if(tracked && offline_mode() && !magazine_reserve_shell(launcher,shell))return;
    void *saved_launcher=firing_launcher,*saved_info=firing_info;
    firing_launcher=!B(launcher,0xa0)?launcher:0;firing_info=0;
    original_launcher_fire(launcher,shell,flag,mi);
    // Speech comes from actual outcomes, not every shot.
    if(tracked && firing_info){
        float now=FN(RVA_GAME_TIME,float (*)(const void *))(0);
        MagazineState *state=magazine_for(status,config,now);
        if(state && state->remaining>0){state->remaining--;state->last_shot=now;}
    }
    firing_launcher=saved_launcher;firing_info=saved_info;
}
