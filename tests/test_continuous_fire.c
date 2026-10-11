#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
#define F(o,n) (*(float *)((uint8_t *)(o)+(n)))
#include "../native/custom_tanks.h"
static CustomTank config;
static unsigned char pc[1024],status[1024],ui[1024],camera[1024],buttons[128],button[128];
static unsigned char count_box[32],inside_box[32],active_box[32],touches[10][96],rect[32];
static void *player_status=status;
static int state=3,offline=1,fire_calls;
static int unity_exists(void *o){return o!=0;}
static int offline_mode(void){return offline;}
static const CustomTank *tank_config(void *s){(void)s;return &config;}
static int bte_field_offset(void *o,const char *name){(void)o;return !strcmp(name,"isMenuPopUp")?0x200:0x100;}
static void *method(void *o,const char *n,int c){(void)o;(void)c;return (void *)n;}
static void *hatch_class(const char *ns,const char *n){(void)ns;return (void *)n;}
static void *hatch_type_object(void *o){return o;}
static void *hatch_method(void *o,const char *n,int c,void *k){(void)o;(void)c;(void)k;return (void *)n;}
static void *class_method(void *o,const char *n,int c){(void)o;(void)c;return (void *)n;}
static void *enemy_invoke(void *method,void *object,void **args,int *error){
    (void)object;*error=0;const char *name=method;
    if(!strcmp(name,"get_activeInHierarchy"))return active_box;
    if(!strcmp(name,"GetComponent"))return rect;
    if(!strcmp(name,"get_touchCount"))return count_box;
    if(!strcmp(name,"GetTouch"))return touches[*(int *)args[0]];
    if(!strcmp(name,"RectangleContainsScreenPoint")){
        float *pos=args[1];B(inside_box,0x10)=pos[0]>=100 && pos[0]<=200 && pos[1]>=100 && pos[1]<=200;
        assert(args[0]==rect && args[2]==0);return inside_box;
    }
    assert(0);return 0;
}
static void button_fire(void *object,int arms,const void *mi){(void)mi;assert(object==ui && arms==0);fire_calls++;}
#define FN(r,t) ((t)button_fire)
#include "../native/continuous_fire.h"
static void touch(int index,float x,float y,int phase){
    F(touches[index],0x14)=x;F(touches[index],0x18)=y;I(touches[index],0x10+36)=phase;
}
int main(void){
    config.magazine_capacity=10;config.continuous_fire=1;P(pc,0x98)=ui;P(ui,0x2f8)=camera;P(ui,0x100)=buttons;
    I(buttons,0x18)=1;P(buttons,0x20)=button;B(active_box,0x10)=1;
    I(count_box,0x10)=2;touch(0,20,20,2);touch(1,150,150,0);
    continuous_fire_update(pc);assert(fire_calls==1);
    touch(1,150,150,2);continuous_fire_update(pc);assert(fire_calls==2);
    touch(1,150,150,3);continuous_fire_update(pc);assert(fire_calls==2);
    touch(1,150,150,4);continuous_fire_update(pc);assert(fire_calls==2);
    touch(1,300,150,1);continuous_fire_update(pc);assert(fire_calls==2);
    touch(1,150,150,2);B(ui,0x200)=1;continuous_fire_update(pc);assert(fire_calls==2);B(ui,0x200)=0;
    offline=0;continuous_fire_update(pc);assert(fire_calls==2);offline=1;
    I(camera,0x38)=1;continuous_fire_update(pc);assert(fire_calls==2);I(camera,0x38)=0;
    B(active_box,0x10)=0;continuous_fire_update(pc);assert(fire_calls==2);B(active_box,0x10)=1;
    config.continuous_fire=0;continuous_fire_update(pc);assert(fire_calls==2);
    config.magazine_capacity=0;config.continuous_fire=1;continuous_fire_update(pc);assert(fire_calls==3);
    puts("Continuous fire: two fingers, hold/release/cancel, drag out, menus, offline scope, aircraft and stock tanks passed");
}
