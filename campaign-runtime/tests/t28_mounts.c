/* Replay the hierarchy in the two serialized prefabs. The simulated clock and transforms
   let this test check the actual per-frame callback without requiring an Android device. */
#include <assert.h>
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define AT(ptr,o,t) (*(t*)((char*)(ptr)+(o)))
typedef struct Node Node;
struct Node {const char *name; Node *parent, *child[5]; int count; float angles[3];};
typedef struct {void *header[2]; float value[3];} Box;
static Box clockbox, v3box;
static struct {void *header[3]; size_t length; void *items[3];} units;
static int kind[6], probes, scans, writes, marker=1;
static void *timec=kind+0,*obj=kind+1,*uStatus=kind+2;
static void *hatch_class(const char *ns,const char *name){(void)ns;(void)name;return kind+3;}
static void *hatch_type_object(void *cl){return cl;}
static void *ha_string(const char *s){return (void*)s;}
static void *over(void *cl,const char *n,void *t){(void)t;assert(cl==obj && !strcmp(n,"FindObjectsOfType"));return obj;}
static void *invoke(void *m,void *self,void **arg,int *e){(void)self;(void)e;assert(m==obj&&arg[0]==uStatus);scans++;return &units;}
static void *find(const char *name){assert(!strcmp(name,"T28_AuxRig"));probes++;return marker?kind+3:0;}
static Node *child(Node *n,const char *path){
  const char *slash=strchr(path,'/');size_t len=slash?(size_t)(slash-path):strlen(path);
  if(!n)return NULL;
  for(int i=0;i<n->count;i++)if(strlen(n->child[i]->name)==len&&!strncmp(n->child[i]->name,path,len))
    return slash?child(n->child[i],slash+1):n->child[i];
  return NULL;
}
static void *call(void *cl,void *self,const char *n,int argc,void **arg,int *e){
  (void)cl;(void)argc;(void)e;Node *x=self;
  if(!strcmp(n,"get_time"))return &clockbox;
  if(!strcmp(n,"get_transform"))return x;
  if(!strcmp(n,"get_parent"))return x->parent;
  if(!strcmp(n,"Find"))return child(x,arg[0]);
  if(!strcmp(n,"get_localEulerAngles")){memcpy(v3box.value,x->angles,sizeof(x->angles));return &v3box;}
  if(!strcmp(n,"set_localEulerAngles")){memcpy(x->angles,arg[0],sizeof(x->angles));writes++;return NULL;}
  assert(0);return NULL;
}
#include "../t28_aux.h"

typedef struct {Node root, info, hull, main, gun, anchor, left, right, lp, rp;} Rig;
static void link_node(Node *p,Node *ch,const char *name){ch->name=name;ch->parent=p;assert(p->count<5);p->child[p->count++]=ch;}
static void rig(Rig *r,int player,int is_t28){
  link_node(&r->root,&r->info,"Unit Info");link_node(&r->root,&r->hull,"Hull");
  link_node(player?&r->root:&r->hull,&r->main,"Turret");link_node(&r->main,&r->gun,"Gun");
  if(!is_t28)return;
  link_node(&r->hull,&r->anchor,"T28_AuxRig");link_node(&r->anchor,&r->left,"T28_Aux_l");
  link_node(&r->anchor,&r->right,"T28_Aux_r");link_node(&r->left,&r->lp,"T28_DT_l");
  link_node(&r->right,&r->rp,"T28_DT_r");
}
static void near(float got,float want){assert(fabsf(got-want)<.002f);}
int main(void){
  Rig player={0},ai={0},other={0};rig(&player,1,1);rig(&ai,0,1);rig(&other,0,0);
  units.length=3;units.items[0]=&player.info;units.items[1]=&other.info;units.items[2]=&ai.info;
  player.main.angles[1]=80;ai.main.angles[1]=280;player.gun.angles[0]=340;ai.gun.angles[0]=16;
  for(int i=0;i<30;i++){clockbox.value[0]=i*.1f;t28_aux_step(22,1,0);}
  near(player.left.angles[1],13);near(player.right.angles[1],55);near(player.lp.angles[0],-8);
  near(ai.left.angles[1],-55);near(ai.right.angles[1],-13);near(ai.rp.angles[0],5);
  assert(writes==8*30 && probes<scans);
  int before=writes;t28_aux_step(22,1,0);assert(writes==before); /* paused game clock */
  clockbox.value[0]=4;t28_aux_step(22,0,0);t28_aux_step(22,1,1);assert(writes==before);
  marker=0;t28_aux_step(23,1,0);assert(writes==before);
  puts("T28: native player/AI hierarchy, per-vehicle motion, paused/offline/terminal gates OK");
}
