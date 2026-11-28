#pragma once
#include <math.h>
/* Unity scene-space only. Position is advanced in the same fixed ticks as the
   pooled Rigidbody. Query the collider on each segment instead of drawing
   from a long chord across nearby scenery. */
typedef struct { float x,y,z; } SceneVec;
static inline SceneVec dv(SceneVec a,SceneVec b){return (SceneVec){a.x-b.x,a.y-b.y,a.z-b.z};}
static inline SceneVec plus(SceneVec a,SceneVec b,float k){return (SceneVec){a.x+k*b.x,a.y+k*b.y,a.z+k*b.z};}
static inline float length(SceneVec a){return sqrtf(a.x*a.x+a.y*a.y+a.z*a.z);}
typedef int (*SceneCast)(void *,SceneVec,SceneVec,SceneVec *);
static inline int preview_ticks(SceneVec p,SceneVec direction,float speed,float g,float dt,void *world,SceneCast cast,SceneVec *impact){
  if(!isfinite(speed)||speed<=0||!isfinite(g)||g<0||!isfinite(dt)||dt<.002f||dt>.12f)return 0;
  SceneVec start=p,v=plus((SceneVec){0},direction,speed);
  for(int n=0;n<1800;n++){
    v.y-=g*dt;SceneVec end=plus(p,v,dt);
    float range=length(dv(end,start));int limit=range>3000;
    if(limit){float k=(3000-length(dv(p,start)))/fmaxf(.00001f,range-length(dv(p,start)));end=plus(p,dv(end,p),fminf(1,fmaxf(0,k)));}
    int hit=cast(world,p,end,impact);if(hit!=0)return hit>0;
    if(limit||end.y<start.y-500)return 0;
    p=end;
  }return 0;
}
