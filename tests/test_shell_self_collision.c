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
static void crew_projectile_impact_observed(void *p){(void)p;}
#include "../native/projectile_owner.h"
#include "../native/ballistics_runtime.h"
static void impact(void *s,void *c,const void *m){(void)s;(void)c;(void)m;impacts++;}
int main(void){
 unsigned char shell[512]={0},info[512]={0},owner[512]={0},root[512]={0},own[3][512]={{0}},tr[3][512]={{0}},enemy[512]={0},enemytr[512]={0},terrain[512]={0};
 P(shell,0x90)=info;P(info,0x20)=root;source_owner=owner;record_projectile_owner(info,root);P(owner,0x100)=root;original_shell_impact=impact;
 for(int i=0;i<3;i++){P(own[i],0x100)=tr[i];P(tr[i],0x100)=root;shell_impact(shell,own[i],0);}
 assert(impacts==0);P(enemy,0x100)=enemytr;shell_impact(shell,enemy,0);shell_impact(shell,terrain,0);assert(impacts==2);
 record_projectile_owner(info,0);shell_impact(shell,own[0],0);assert(impacts==3);record_projectile_owner(info,root);offline=0;shell_impact(shell,own[0],0);assert(impacts==4);
 offline=1;unsigned char bomb[512]={0},otherinfo[512]={0};P(bomb,0x88)=otherinfo;record_projectile_owner(otherinfo,root);original_he_trigger=impact;original_he_collision=impact;
 he_trigger(bomb,own[0],0);he_collision(bomb,own[1],0);assert(impacts==4);
 he_trigger(bomb,enemy,0);he_collision(bomb,terrain,0);assert(impacts==6);
 puts("Imported projectile ignores all own body/turret/info colliders, still hits enemies/terrain; stock and online unchanged");
}
