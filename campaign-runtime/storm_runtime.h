#pragma once
#include "storm_clock.h"
static struct {void *root,*rain,*cam,*audio[3];int sleeping,stopped;} storm_fx;
static void storm_reset(void){weather_clock=(StormClock){0};storm_fx=(__typeof__(storm_fx)){0};}
static void storm_assets(void *gc){
  int e=0;
  if(!live(storm_fx.root))storm_fx.root=find("Hatch Storm Weather");
  if(!live(storm_fx.rain)){
    void *g=find("Hatch Storm Rain");if(live(g))storm_fx.rain=call(goc,g,"get_transform",0,0,&e);
  }
  if(!live(storm_fx.cam)){
    void *cc=read_ref(controller,gc,"mCamCtrl");if(live(cc)){
      void *cam=read_ref(AT(cc,0,void*),cc,"myCamera");
      if(live(cam))storm_fx.cam=call(ctrl_ui,cam,"get_transform",0,0,&e);
    }
  }
  static void *ac;const char *names[]={"Hatch Storm Audio rain","Hatch Storm Audio roll","Hatch Storm Audio crack"};
  if(!ac)ac=hatch_class("UnityEngine","AudioSource");
  if(ac)for(int i=0;i<3;i++)if(!live(storm_fx.audio[i])){
    void *g=find(names[i]);if(live(g))storm_fx.audio[i]=component(g,ac);
  }
}
static void storm_step(int scene_no,void *gc,void *st,int ended,int dead){
  if(!storm_field(scene_no)||!live(gc)||!live(st))return;
  int id=number(obj,gc,"GetInstanceID",0);
  float now=scalar(timec,0,"get_time");if(!id||!isfinite(now))return;
  if(weather_clock.gc!=id||weather_clock.scene!=scene_no||now<weather_clock.last)storm_reset();
  storm_tick(&weather_clock,scene_no,id,now);
  if(ended||dead){
    if(!storm_fx.stopped&&live(storm_fx.root)){deactivate(storm_fx.root);storm_fx.stopped=1;}
    return;
  }
  storm_assets(gc);
  int pause=scalar(timec,0,"get_timeScale")<=0;
  if(storm_fx.sleeping!=pause){
    for(int i=0;i<3;i++){void *a=storm_fx.audio[i];if(live(a)){int err=0;call(AT(a,0,void*),a,pause?"Pause":"UnPause",0,0,&err);}}
    storm_fx.sleeping=pause;
  }
  if(pause)return;
  if(live(storm_fx.rain)&&live(storm_fx.cam)){
    int err=0;void *ct=AT(storm_fx.cam,0,void*),*boxed=call(ct,storm_fx.cam,"get_position",0,0,&err);
    if(!err&&boxed){
      float p[3];memcpy(p,(char*)boxed+16,sizeof p);p[1]+=7.f;
      if(isfinite(p[0])&&isfinite(p[1])&&isfinite(p[2])){void *a[]={p};call(AT(storm_fx.rain,0,void*),storm_fx.rain,"set_position",1,a,&err);}
    }
  }
  if(weather_clock.last-weather_clock.start<STORM_SECONDS||weather_clock.requested)return;
  int n=number(controller,gc,"get_CurrentEmyNum",-1);
  int decision=storm_verdict(&weather_clock,ended,dead,n);
  if(decision!=RUNNING){
    int err=0;call(controller,gc,decision==WON?"GameClear":"GameOver",0,0,&err);
    if(!err)weather_clock.requested=decision;
  }
}
