#pragma once
// Semantic battle events. Stock RadioVoice indices are unrelated to tank crew
// conditions and must never be interpreted as repairs, fire or loading events.
#include "crew_gate.h"
#include "crew_notice.h"
static volatile int crew_enabled;
static unsigned crew_event_mask;
static void (*original_radio_voice)(void *,int,const void *);
static UpdateFn original_radio_reply;
typedef struct {void *info,*alternate_info,*target;unsigned long finished;int hit,reported,has_target;BteVec target_pos,origin,forward,right,closest;float closest_error;} CrewShot;
static CrewShot crew_shots[128];static unsigned crew_shot_cursor;
static void *crew_battle,*crew_target_owner,*crew_shell_owner;
static int crew_last_shell=-1,crew_last_kills;
static unsigned long crew_scan_time,crew_contact_time;
static void *crew_contact;
static Vec3 crew_contact_pos;
static unsigned long crew_contact_lost;
static int crew_active(void){return __atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)&&state==3&&offline_mode();}
static void crew_trigger(int event);
#include "crew_shots.h"
static void crew_trigger(int event){
 if(!crew_active()||event<0||event>17||!(crew_event_mask&(1u<<event))||!crew_gate_begin())return;
 memset(crew_pending,0,sizeof(crew_pending));crew_pending[0]=event;crew_gate_publish();
}
static void crew_radio_voice(void *self,int event,const void *mi){
 if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode())original_radio_voice(self,event,mi);
}
static void crew_radio_reply(void *self,const void *mi){
 if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode())original_radio_reply(self,mi);
}
static void crew_battle_update(void *game,int previous){
 if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode())return;
 if(B(game,0x10c)&&previous==3){crew_trigger(5);return;}
 void *status=P(game,0x118);
 if(!unity_exists(status)||B(status,FIELD_UNITSTATUS_ISDESTROYED_K__BACKINGFIELD)||B(game,0x10c)||B(game,0x10d))return;
 if(crew_battle!=game||previous!=3){
  crew_battle=game;crew_contact=0;crew_scan_time=crew_contact_time=0;crew_shell_owner=0;crew_last_shell=-1;crew_last_kills=0;
  crew_gate_clear();crew_notice_clear();memset(crew_shots,0,sizeof(crew_shots));
  // Game.Update establishes state=3 immediately after this observer.
  player_status=status;state=3;crew_trigger(0);
 }
}
#include "crew_contact.h"
static void crew_player_update(void *pc){
 if(!crew_active())return;unsigned long now=now_ms();
 if(crew_target_owner!=player_status){crew_target_owner=player_status;crew_contact=0;crew_contact_lost=crew_scan_time=crew_contact_time=0;}
 int offset=bte_field_offset(player_status,"usingShell"),shell=offset>=0?I(player_status,offset):-1;
 if(crew_shell_owner!=player_status){crew_shell_owner=player_status;crew_last_shell=shell;}
 else if(shell!=crew_last_shell){crew_last_shell=shell;if(shell>=0&&shell<5)crew_trigger(12+shell);}
 void *ui=P(pc,0x98);offset=unity_exists(ui)?bte_field_offset(ui,"<KillNum>k__BackingField"):-1;
 if(offset>=0){int kills=I(ui,offset);if(kills>crew_last_kills){crew_last_kills=kills;crew_trigger(6);}}
 for(int i=0;i<128;i++){CrewShot *s=crew_shots+i;if(s->finished&&now>=s->finished){s->finished=0;if(!s->hit&&!s->reported){s->reported=1;
   int event=2;
   if(s->has_target&&isfinite(s->closest_error)){
    BteVec delta=bte_sub(s->closest,s->target_pos);
    float side=bte_dot(delta,s->right),up=delta.y;
    event=fabsf(side)>fabsf(up)?(side>0?10:11):(up>0?8:9);
   }
   crew_trigger(event);}}}
 crew_acquire_target(pc,now);
}
