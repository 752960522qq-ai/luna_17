#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define F(o,n) (*(float *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
typedef void (*UpdateFn)(void *,const void *);
static void crew_observe_shell(void *s,int i){(void)s;(void)i;}
static int offline=1,custom=1,impacts;
static int offline_mode(void){return offline;}
static int unity_exists(void *p){return p!=0;}
static void *tank_config(void *p){return custom?p:0;}
static void *source_owner;
static void *hatch_call(void *p,const char *n,int c,void **args){(void)n;(void)c;(void)args;return p;}
static void *hatch_get_child_component(void *p,const char *ns,const char *n){(void)p;(void)ns;(void)n;return source_owner;}
static void *hatch_weapon_mount(void *p){return P(p,0x100);}
static int hatch_belongs_to(void *tr,void *root){return P(tr,0x100)==root;}
#include "../native/ballistics_runtime.h"
static void impact(void *s,void *c,const void *m){(void)s;(void)c;(void)m;impacts++;}
int main(void){
 unsigned char shell[512]={0},info[512]={0},owner[512]={0},root[512]={0},own[3][512]={{0}},tr[3][512]={{0}},enemy[512]={0},enemytr[512]={0},terrain[512]={0};
 P(shell,0x90)=info;P(info,0x20)=root;source_owner=owner;P(owner,0x100)=root;original_shell_impact=impact;
 for(int i=0;i<3;i++){P(own[i],0x100)=tr[i];P(tr[i],0x100)=root;shell_impact(shell,own[i],0);}
 assert(impacts==0);P(enemy,0x100)=enemytr;shell_impact(shell,enemy,0);shell_impact(shell,terrain,0);assert(impacts==2);
 custom=0;shell_impact(shell,own[0],0);assert(impacts==3);custom=1;offline=0;shell_impact(shell,own[0],0);assert(impacts==4);
 puts("Imported projectile ignores all own body/turret/info colliders, still hits enemies/terrain; stock and online unchanged");
}
