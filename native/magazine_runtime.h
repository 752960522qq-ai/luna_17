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
static void launcher_fire(void *launcher,int shell,int flag,const void *mi) {
    void *status=P(launcher,0x38);
    const CustomTank *config=tank_config(status);
    int tracked=config && config->magazine_capacity>=2 && !B(launcher,0xa0) && shell>=0 && shell<5;
    void *saved_launcher=firing_launcher,*saved_info=firing_info;
    firing_launcher=tracked?launcher:0;firing_info=0;
    original_launcher_fire(launcher,shell,flag,mi);
    if(tracked && firing_info){
        float now=FN(RVA_GAME_TIME,float (*)(const void *))(0);
        MagazineState *state=magazine_for(status,config,now);
        if(state && state->remaining>0){state->remaining--;state->last_shot=now;}
    }
    firing_launcher=saved_launcher;firing_info=saved_info;
}
