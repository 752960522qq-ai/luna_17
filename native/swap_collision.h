#pragma once
// Re-enumerate on each call instead of retaining an unrooted managed array
// across frames. Unity component order stays fixed during this transaction.
typedef struct {int count;uint8_t enabled[256];} SwapCollisionGuard;
static int swap_collisions(void *go,SwapCollisionGuard *guard,int restore){
    int saved_error=hatch_engine_error;hatch_engine_error=0;
    void *colliders=hatch_all(go,hatch_class("UnityEngine","Collider"));
    int count=colliders?I(colliders,0x18):0;
    int ok=!hatch_engine_error && count>0 && count<=256 && (!guard->count||guard->count==count);
    if(ok){
        for(int i=0;i<count;i++){
            void *collider=P(colliders,0x20+i*8);
            void *get=method(collider,"get_enabled",0),*set=method(collider,"set_enabled",1);
            if(!unity_exists(collider)||!get||!set){ok=0;break;}
        }
    }
    if(ok){
        for(int i=0;i<count;i++){
            void *collider=P(colliders,0x20+i*8);
            if(!guard->count){void *get=method(collider,"get_enabled",0);guard->enabled[i]=((bool (*)(void *,const void *))P(get,0))(collider,get);}
            void *set=method(collider,"set_enabled",1);
            ((void (*)(void *,bool,const void *))P(set,0))(collider,restore&&guard->enabled[i],set);
        }
        guard->count=count;
    }
    hatch_engine_error=saved_error;return ok;
}
