/* Cosmetic game pose. Unity yaw is positive to the right, local pitch positive down.
   Each front turret has its own pivot and a smaller inboard sector near the driver. */
#pragma once
#include <math.h>
static inline float t28_signed(float v) {
  float x=fmodf(v+180.0f,360.0f);
  return (x<0 ? x+360.0f : x)-180.0f;
}
static inline float t28_limit(float v,float lo,float hi) {return fmaxf(lo,fminf(hi,v));}
static inline float t28_yaw(float main,float old,int left,float seconds) {
  float bearing=t28_signed(main);
  /* A rear-facing main turret is outside both front arcs. Let each return home,
     blending over 85..135 deg so the -180/180 wrap cannot reverse the mount. */
  float fade=t28_limit((135.f-fabsf(bearing))/50.f,0.f,1.f);
  float target=t28_limit(bearing,left?-55.f:-13.f,left?13.f:55.f)*fade;
  float max_step=36.f*t28_limit(seconds,0.f,.25f);
  return old+t28_limit(target-old,-max_step,max_step);
}
static inline float t28_pitch(float main){return t28_limit(t28_signed(main),-8.f,5.f);}
