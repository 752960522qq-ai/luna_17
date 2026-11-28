#pragma once
/* One local player's clock. A trigger request alone never advances the magazine. */
typedef struct {int rounds; float available; int heldShot;} PlayerClip;
static inline void clip_reset(PlayerClip *m){*m=(PlayerClip){0,0,0};}
static inline int clip_request(PlayerClip *m,float now,int held,int clicked,int freeShell){
  int edge=clicked && !m->heldShot;
  if(!held)m->heldShot=0;
  return (held||edge) && freeShell && now+0.00001f>=m->available;
}
static inline void clip_launched(PlayerClip *m,float now,int held){
  if(held)m->heldShot=1;
  if(++m->rounds==10){m->rounds=0;m->available=now+4.85f;}
  else m->available=now+.4f;
}
static inline int clip_ack(unsigned before,unsigned after,int reserve,int left,float start,float cycle){
  return (after & ~before)!=0 || (reserve>=0 && left>=0 && left<reserve && start>=0 && cycle>start);
}
/* Restore exactly one attributed debit, never overwrite an ammo change from a
 * resupply or another shell type while a shot was in flight. */
static inline int clip_failed_slot(const int *before,const int *after){
  for(int k=0;k!=2;k++)if(before[k]>0 && after[k]==before[k]-1 && after[1-k]==before[1-k])return k;
  return -1;
}
