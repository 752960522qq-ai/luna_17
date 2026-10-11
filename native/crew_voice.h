#pragma once
// Semantic battle events. Stock RadioVoice indices are unrelated to tank crew
// conditions and must never be interpreted as repairs, fire or loading events.
#include "crew_gate.h"
static volatile int crew_enabled;
static unsigned crew_event_mask;
static void (*original_radio_voice)(void *,int,const void *);
static UpdateFn original_radio_reply;
typedef struct {void *info,*target;unsigned long finished;int hit,reported;} CrewShot;
static CrewShot crew_shots[128];static unsigned crew_shot_cursor;
static void *crew_battle,*crew_target_owner,*crew_shell_owner;
static int crew_last_shell=-1,crew_last_kills;
static unsigned long crew_scan_time,crew_contact_time;
static void *crew_contact;
static int crew_active(void){return __atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)&&state==3&&offline_mode();}
static CrewShot *crew_shot(void *info){if(!info)return 0;for(int i=0;i<128;i++)if(crew_shots[i].info==info)return crew_shots+i;return 0;}
static void crew_record_shot(void *info,void *status,int secondary){
 if(!crew_active()||status!=player_status||secondary||!info)return;
 CrewShot *s=crew_shot(info);if(!s)s=crew_shots+crew_shot_cursor++%128;*s=(CrewShot){.info=info};
}
static void crew_trigger(int event){
 if(!crew_active()||event<0||event>16||!(crew_event_mask&(1u<<event))||!crew_gate_begin())return;
 memset(crew_event,0,sizeof(crew_event));crew_event[0]=event;crew_gate_publish();
}
static void crew_radio_voice(void *self,int event,const void *mi){
 if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode())original_radio_voice(self,event,mi);
}
static void crew_radio_reply(void *self,const void *mi){
 if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode())original_radio_reply(self,mi);
}
static void crew_damage_result(void *damage,void *info,void *result){
 if(!crew_active()||!damage||!result||I(result,0x18)!=4)return;
 void *target=P(damage,0x38);if(!unity_exists(target))return;
 if(target==player_status){crew_trigger(4);return;}
 CrewShot *s=crew_shot(info);if(!s)return;
 void *friend=method(target,"get_IsMyFriend",0);
 if(!friend||((bool (*)(void *,const void *))P(friend,0))(target,friend))return;
 s->hit=1;s->target=target;
 if(!s->reported){s->reported=1;crew_trigger(I(result,0x20)<10?7:3);}
}
static void crew_observe_shell(void *shell,int initialized){
 if(!crew_active()||!initialized||B(shell,0x9c))return;
 CrewShot *s=crew_shot(P(shell,0x90));if(s&&!s->finished)s->finished=now_ms()+300;
}
static UpdateFn original_crew_shell_reset;
static void crew_shell_reset(void *shell,const void *mi){
 CrewShot *s=crew_shot(P(shell,0x90));
 if(crew_active()&&s&&!s->finished)s->finished=now_ms()+300;
 original_crew_shell_reset(shell,mi);
}
static void crew_battle_update(void *game,int previous){
 if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode())return;
 if(B(game,0x10c)&&previous==3){crew_trigger(5);return;}
 void *status=P(game,0x118);
 if(!unity_exists(status)||B(status,FIELD_UNITSTATUS_ISDESTROYED_K__BACKINGFIELD)||B(game,0x10c)||B(game,0x10d))return;
 if(crew_battle!=game||previous!=3){
  crew_battle=game;crew_contact=0;crew_scan_time=crew_contact_time=0;crew_shell_owner=0;crew_last_shell=-1;crew_last_kills=0;
  memset(crew_shots,0,sizeof(crew_shots));
  // Game.Update establishes state=3 immediately after this observer.
  player_status=status;state=3;crew_trigger(0);
 }
}
static void crew_acquire_target(void *pc,unsigned long now){
 if(now-crew_scan_time<250)return;crew_scan_time=now;
 void *turret=P(pc,0x50),*root=P(pc,0x20);if(!unity_exists(turret)||!unity_exists(root))return;
 Vec3 origin=call_vec(root,"get_position"),target=call_vec(turret,"get_TargetPos"),forward=call_vec(root,"get_forward");origin.y+=1;
 BteVec aim=bte_sub(bv(target),bv(origin));float length=sqrtf(bte_dot(aim,aim));if(length<1)return;aim=bte_scale(aim,1/length);
 const char *classes[]={"UnitStatus","AirUnitStatus"};float best=.997f;void *chosen=0;Vec3 pos={0};int type=0;
 for(int kind=0;kind<2;kind++){
  void *t=hatch_type_object(hatch_class("",classes[kind]));if(!t)continue;bool inactive=false;void *args[]={t,&inactive};int error=0;
  void *all=enemy_invoke(hatch_method(hatch_class("UnityEngine","Object"),"FindObjectsOfType",2,hatch_class("System","Type")),0,args,&error);
  int count=all?I(all,0x18):0;if(error||count<0||count>1024)continue;
  for(int i=0;i<count;i++){
   void *s=P(all,0x20+i*8);if(!unity_exists(s)||s==player_status)continue;
   void *m=method(s,"get_IsMyFriend",0);if(!m||((bool (*)(void *,const void *))P(m,0))(s,m))continue;
   m=method(s,"get_IsDestroyed",0);if(m&&((bool (*)(void *,const void *))P(m,0))(s,m))continue;
   void *tr=enemy_invoke(method(s,"get_transform",0),s,0,&error);if(error||!unity_exists(tr))continue;
   Vec3 p=call_vec(tr,"get_position");if(!kind)p.y+=1;
   BteVec delta=bte_sub(bv(p),bv(origin));float d=sqrtf(bte_dot(delta,delta));if(d<2||d>3000)continue;
   float cosine=bte_dot(aim,bte_scale(delta,1/d));if(cosine<best)continue;
   EnemyHit hit={0};if(bte_cast(origin,p,&hit)&&hit.distance<d-3)continue;
   best=cosine;chosen=s;pos=p;type=kind?2:1;
   if(!kind){char name[112];utf8_name(P(s,0x68),name,sizeof(name));if(strstr(name,"T34"))type=4;else if(strstr(name,"Tiger"))type=5;else if(strstr(name,"Panther"))type=6;}
  }
 }
 if(!chosen){crew_contact=0;return;}
 if(chosen==crew_contact)return;
 crew_contact=chosen;
 if(now-crew_contact_time<8000||!(crew_event_mask&(1u<<1))||!crew_gate_begin())return;
 crew_contact_time=now;
 Vec3 delta={pos.x-origin.x,pos.y-origin.y,pos.z-origin.z};
 float angle=atan2f(forward.z*delta.x-forward.x*delta.z,forward.x*delta.x+forward.z*delta.z);
 int clock=((int)lroundf(angle*6.f/3.14159265359f)+12)%12;
 crew_event[0]=1;crew_event[1]=type;crew_event[2]=clock?clock:12;crew_event[3]=(int)lroundf(sqrtf(delta.x*delta.x+delta.y*delta.y+delta.z*delta.z));crew_gate_publish();
}
static void crew_player_update(void *pc){
 if(!crew_active())return;unsigned long now=now_ms();
 int offset=bte_field_offset(player_status,"usingShell"),shell=offset>=0?I(player_status,offset):-1;
 if(crew_shell_owner!=player_status){crew_shell_owner=player_status;crew_last_shell=shell;}
 else if(shell!=crew_last_shell){crew_last_shell=shell;if(shell>=0&&shell<5)crew_trigger(12+shell);}
 void *ui=P(pc,0x98);offset=unity_exists(ui)?bte_field_offset(ui,"<KillNum>k__BackingField"):-1;
 if(offset>=0){int kills=I(ui,offset);if(kills>crew_last_kills){crew_last_kills=kills;crew_trigger(6);}}
 for(int i=0;i<128;i++){CrewShot *s=crew_shots+i;if(s->finished&&now>=s->finished){s->finished=0;if(!s->hit&&!s->reported){s->reported=1;crew_trigger(2);}}}
 crew_acquire_target(pc,now);
}
