#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
static _Alignas(16) uint8_t array[128],one[32],two[32],get_method[32],set_method[32];
static int hatch_engine_error,missing,writes;
static bool get_enabled(void *collider,const void *method){(void)method;return I(collider,16)!=0;}
static void set_enabled(void *collider,bool enabled,const void *method){(void)method;I(collider,16)=enabled;writes++;}
static void *method(void *collider,const char *name,int count){(void)collider;(void)count;if(missing)return 0;return !strcmp(name,"get_enabled")?get_method:set_method;}
static int unity_exists(void *object){return object!=0;}
static void *hatch_class(const char *ns,const char *name){(void)ns;(void)name;return one;}
static void *hatch_all(void *go,void *klass){(void)go;(void)klass;return array;}
#include "../native/swap_collision.h"
int main(void){
    P(get_method,0)=get_enabled;P(set_method,0)=set_enabled;I(array,24)=2;P(array,32)=one;P(array,40)=two;
    I(one,16)=1;I(two,16)=0;SwapCollisionGuard guard={0};hatch_engine_error=7;
    assert(swap_collisions(one,&guard,0));assert(!I(one,16)&&!I(two,16));assert(guard.enabled[0]&&!guard.enabled[1]);assert(hatch_engine_error==7);
    assert(swap_collisions(one,&guard,0));assert(swap_collisions(one,&guard,1));assert(I(one,16)&&!I(two,16));
    int old_writes=writes;I(array,24)=3;assert(!swap_collisions(one,&guard,0));assert(writes==old_writes);I(array,24)=2;
    missing=1;assert(!swap_collisions(one,&guard,0));assert(writes==old_writes);assert(I(one,16));
    puts("Swap collisions: staged body isolated; original enabled states restored; failures do not partially mutate");
}
