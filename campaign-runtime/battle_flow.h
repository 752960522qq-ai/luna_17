#pragma once
#include <math.h>
/* Per player, scaled Unity time. Only the main gun's accepted shot or actual
   pool activation commits a round. AI, MG presses, and UI taps are not rounds. */
typedef struct {int spent, pending; float next, issued; int before; unsigned pool;} ClipClock;
static inline void gun_tick(ClipClock *g,float now){
  if(g->spent==10 && now+.00001f>=g->next)g->spent=0;
}
static inline int gun_can(ClipClock *g,float now){gun_tick(g,now);return !g->pending&&g->spent<10&&now+.00001f>=g->next;}
static inline void gun_accept(ClipClock *g,float now){
  g->pending=0;if(g->spent>=10)return;
  g->spent++;g->next=now+(g->spent==10?4.85f:.4f);
}
enum {RUNNING, LOST, WON};
static inline int mission_terminal(int cleared,int lost,int destroyed){
  return cleared?WON:(lost||destroyed?LOST:RUNNING);
}
