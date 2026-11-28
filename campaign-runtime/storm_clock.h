#pragma once
#include <math.h>
#include "battle_flow.h"
enum { STORM_SO=24, STORM_GE=25, STORM_SECONDS=780 };
static inline int storm_field(int i){return i==STORM_SO||i==STORM_GE;}
typedef struct {int gc,scene,requested;float start,last;} StormClock;
/* Time.time freezes on pause. A new controller (also on same-side Retry) owns a new deadline. */
static inline void storm_tick(StormClock *s,int scene,int id,float now){
  if(!storm_field(scene)||!id||!isfinite(now))return;
  if(s->gc!=id||s->scene!=scene||now<s->last)*s=(StormClock){.gc=id,.scene=scene,.start=now};
  s->last=now;
}
static inline int storm_verdict(const StormClock *s,int ended,int dead,int enemies){
  if(!s->gc||ended||dead||s->requested||s->last-s->start<STORM_SECONDS||enemies<0)return RUNNING;
  return s->scene==STORM_SO||enemies==0?WON:LOST;
}
