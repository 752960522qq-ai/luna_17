#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>
#include <stdio.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((o)+(n)))
#define RVA_3431140 1
#define RVA_GAME_TIME 2
static void set_active(void *go,bool enabled,const void *mi){(void)mi;I(go,16)=enabled;}
static float clock_time(const void *mi){(void)mi;return 1;}
static void *fake_fn(int rva){return rva==1?(void *)set_active:(void *)clock_time;}
#define FN(r,t) ((t)fake_fn(r))
typedef struct {int magazine_capacity;float magazine_reload,shot_interval;} CustomTank;
static CustomTank config={10,5,.1f};
static void *player_status;
static int hatch_engine_ok=1,allocation_fail,clones,fires,voices;
static _Alignas(16) uint8_t active_method[32],instance_method[32],destroy_method[32];
static bool active(void *go,const void *mi){(void)mi;return I(go,16)!=0;}
static int unity_exists(void *go){return go!=0;}
static void managed_store(void *go,int offset,void *value){P(go,offset)=value;}
static const CustomTank *tank_config(void *status){return status==player_status?&config:0;}
static int offline_mode(void){return 1;}
static void crew_trigger(int event){assert(event==10);voices++;}
static void *method(void *go,const char *name,int count){(void)go;(void)name;(void)count;return active_method;}
static void *hatch_class(const char *ns,const char *name){(void)ns;(void)name;return instance_method;}
static void *hatch_method(void *klass,const char *name,int count,void *first){(void)klass;(void)name;(void)count;(void)first;return instance_method;}
static void *class_method(void *klass,const char *name,int count){(void)klass;(void)name;(void)count;return destroy_method;}
static void *ha_array(void *klass,uintptr_t n){(void)klass;if(allocation_fail)return 0;void *out=calloc(1,32+n*8);I(out,24)=n;return out;}
static void *ha_invoke(void *mi,void *self,void **args,void **exception){(void)self;(void)exception;if(mi==destroy_method){free(args[0]);return 0;}void *out=calloc(1,32);memcpy(out,args[0],32);clones++;return out;}
#include "../native/magazine_runtime.h"
static void fire(void *launcher,int shell,int flag,const void *mi){(void)flag;(void)mi;void *pool=P(launcher,shell==1?0x80:0x78);for(int i=0;i<I(pool,24);i++){void *go=P(pool,32+i*8);if(!I(go,16)){I(go,16)=1;fires++;firing_info=go;return;}}assert(0&&"original fire must receive a reserved object");}
int main(void){
 _Alignas(16) uint8_t launcher[256]={0},status[1024]={0},shot1[32]={0},shot2[32]={0};
 P(active_method,0)=active;player_status=status;P(launcher,0x38)=status;original_launcher_fire=fire;
 void *pool=ha_array(0,2);P(pool,32)=shot1;P(pool,40)=shot2;P(launcher,0x78)=pool;
 assert(magazine_reserve_shell(launcher,0)&&clones==0);
 launcher_fire(launcher,0,0,0);launcher_fire(launcher,0,0,0);
 assert(fires==2&&I(shot1,16)&&I(shot2,16));
 launcher_fire(launcher,0,0,0);assert(fires==3&&clones==1&&voices==0);assert(I(P(launcher,0x78),24)==3);assert(I(shot1,16)&&I(shot2,16));
 allocation_fail=1;assert(!magazine_reserve_shell(launcher,0));assert(I(P(launcher,0x78),24)==3);assert(I(shot1,16)&&I(shot2,16));
 puts("Magazine pool: original fire always receives a free object; active shots preserved; growth failure leaves pool intact");
}
