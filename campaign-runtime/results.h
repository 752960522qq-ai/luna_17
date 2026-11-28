#pragma once
#include "storm_clock.h"
static StormClock weather_clock;
/* The stock GameControl owns persistence, audio, and the end coroutine.
   The fallback below invokes only its presentation function. */
static struct {int owner,outcome,requested,displayed,died;float at;} finish;
static int result_panel(void *hud){
  void *panel=hud?read_ref(ui,hud,"mResultGo"):0;
  return live(panel)&&flag(goc,panel,"get_activeInHierarchy");
}
static int stock_result(void *hud,void *gc,int won,int idx){
  if(!live(hud))return 0;
  void *m=lookup(ui,"SetMissionResulet",2);if(!m)return 0;
  void **params=AT(m,0x30,void**);if(!params||ha_param_class(params[1])!=intc)return 0;
  void *enum_type=hatch_type_object(ha_param_class(params[0]));
  void *enumc=hatch_class("System","Enum");if(!enum_type||!enumc)return 0;
  const char *label=won?(idx==23?"InvadedByFriend":"NoEnemy"):(finish.died?"Destroyed":(idx==22?"InvadedByEnemy":"NoFriend"));
  if(storm_field(idx)&&weather_clock.requested&&!finish.died&&number(controller,gc,"get_CurrentEmyNum",0)>0)label="TimeLimit";
  int e=0;void *a[]={enum_type,ha_string(label)};
  void *value=call(enumc,0,"Parse",2,a,&e);if(!value||e)return 0;
  int reason=AT(value,16,int),remaining=number(controller,gc,"get_CurrentFndNum",0);
  void *args[]={&reason,&remaining};invoke(m,hud,args,&e);return !e;
}
static int result_step(int idx,void *gc,void *hud,int destroyed){
  if(idx<22||idx>25)return 0;
  int owner=number(obj,gc,"GetInstanceID",0);if(!owner)return 0;
  if(owner!=finish.owner)finish=(__typeof__(finish)){.owner=owner};
  int clear=flag(controller,gc,"get_IsGameClear"),overnow=flag(controller,gc,"get_IsGameOver");
  int end=mission_terminal(clear,overnow,destroyed);
  float now=scalar(timec,0,"get_unscaledTime");
  if(!finish.outcome&&end){finish.outcome=end;finish.at=now;finish.died=destroyed;}
  if(!finish.outcome)return 0;
  if(!clear&&!overnow&&destroyed&&!finish.requested){
    int e=0;call(controller,gc,"GameOver",0,0,&e);if(!e)finish.requested=1;
  }
  if(storm_field(idx)&&weather_clock.requested&&!finish.displayed&&!finish.died)
    finish.displayed=stock_result(hud,gc,finish.outcome==WON,idx);
  if(result_panel(hud)) finish.displayed=1;
  if(!finish.displayed&&isfinite(now)&&now-finish.at>=3.5f){
    if(stock_result(hud,gc,finish.outcome==WON,idx))finish.displayed=1;
    else finish.at=now; /* stock coroutine can still complete; bound fallback attempts */
  }
  return 1;
}
