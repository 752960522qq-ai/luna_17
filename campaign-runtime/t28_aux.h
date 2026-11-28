/* Animate the T-28's two cosmetic DT mounts through ordinary Unity Transform
   accessors. Runs on the existing offline Unity frame callback; no object
   references survive a frame, and no firing or targeting controller is added. */
#pragma once
#include "t28_pose.h"
typedef struct {float x,y,z;} T28Vec;

static void *t28_child(void *trcl,void *tr,void *path) {
  if(!tr || !path) return 0;
  int e=0;void *a[]={path};
  return call(trcl,tr,"Find",1,a,&e);
}
static int t28_angles(void *trcl,void *tr,T28Vec *out){
  if(!tr)return 0;
  int e=0;void *q=call(trcl,tr,"get_localEulerAngles",0,0,&e);
  if(e || !q)return 0;
  memcpy(out,(const char*)q+sizeof(void*)*2,sizeof(*out));
  return isfinite(out->x)&&isfinite(out->y)&&isfinite(out->z);
}
static void t28_set_angles(void *trcl,void *tr,T28Vec v){
  if(!tr)return;
  int e=0;void *a[]={&v};call(trcl,tr,"set_localEulerAngles",1,a,&e);
}
static void t28_aux_step(int idx,int offline,int ended){
  static int last_scene=-1, present;
  static float last,probe;
  if(idx!=last_scene || !offline || ended){last_scene=idx;last=-1.f;probe=0.f;present=0;}
  if(!offline||ended)return;
  int e=0;void *clock=call(timec,0,"get_time",0,0,&e);
  if(e||!clock)return;
  float now=AT(clock,sizeof(void*)*2,float);
  if(!isfinite(now))return;
  if(now<last){last=-1.f;probe=0.f;present=0;}
  if(now>=probe){
    present=find("T28_AuxRig")!=0;
    probe=now+(present?.48f:.85f);
  }
  if(!present || (last>=0 && now-last<.055f))return;
  float dt=last<0?.10f:now-last;last=now;
  void *tc=hatch_class("UnityEngine","Transform"),*cc=hatch_class("UnityEngine","Component");
  void *sys=hatch_class("System","Type"),*type=hatch_type_object(uStatus);
  if(!tc||!cc||!sys||!type)return;
  void *args[]={type};
  void *list=invoke(over(obj,"FindObjectsOfType",sys),0,args,&e);
  if(e||!list)return;
  size_t n=AT(list,3*sizeof(void*),size_t);
  if(n>1024)return;
  void *anchor=ha_string("Hull/T28_AuxRig"),*under=ha_string("Hull/Turret"),*atroot=ha_string("Turret"),*gun=ha_string("Gun");
  void *left=ha_string("T28_Aux_l"),*right=ha_string("T28_Aux_r"),*lg=ha_string("T28_DT_l"),*rg=ha_string("T28_DT_r");
  for(size_t i=0;i<n;i++){
    void *st=AT(list,4*sizeof(void*)+i*sizeof(void*),void*);
    if(!st)continue;
    int err=0;void *tr=call(cc,st,"get_transform",0,0,&err);
    void *owner=tr?call(tc,tr,"get_parent",0,0,&err):0;
    void *mount=t28_child(tc,owner,anchor);
    if(!mount||err)continue;
    /* Authored AI and garage tanks keep the new Turret under Hull; native
       player assets use the stock camera's direct child of the same owner. */
    void *main=t28_child(tc,owner,under);
    if(!main)main=t28_child(tc,owner,atroot);
    T28Vec yaw,pitch;
    if(!t28_angles(tc,main,&yaw)||!t28_angles(tc,t28_child(tc,main,gun),&pitch))continue;
    for(int j=0;j<2;j++){
      void *aux=t28_child(tc,mount,j?right:left);T28Vec prev;
      if(!t28_angles(tc,aux,&prev))continue;
      t28_set_angles(tc,aux,(T28Vec){0,t28_yaw(yaw.y,t28_signed(prev.y),!j,dt),0});
      t28_set_angles(tc,t28_child(tc,aux,j?rg:lg),(T28Vec){t28_pitch(pitch.x),0,0});
    }
  }
}
