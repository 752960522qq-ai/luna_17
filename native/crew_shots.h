#pragma once
static CrewShot *crew_shot(void *info){if(!info)return 0;for(int i=0;i<128;i++)if((crew_shots[i].info==info||crew_shots[i].alternate_info==info))return crew_shots+i;return 0;}
static void crew_record_shot(void *info,void *status,int secondary){
 if(!crew_active()||status!=player_status||secondary||!info)return;
 if(firing_info&&firing_info!=info){CrewShot *first=crew_shot(firing_info);if(first){first->alternate_info=info;return;}}
 CrewShot *s=crew_shot(info);if(!s)s=crew_shots+crew_shot_cursor++%128;*s=(CrewShot){.info=info,.closest_error=INFINITY};
 if(unity_exists(crew_contact)){
  void *pc=player_control,*root=unity_exists(pc)?P(pc,0x20):0;
  if(unity_exists(root)){
   s->has_target=1;s->target_pos=bv(crew_contact_pos);s->origin=bv(call_vec(root,"get_position"));
   BteVec direction=bte_sub(s->target_pos,s->origin);float length=sqrtf(bte_dot(direction,direction));
   if(length>1){s->forward=bte_scale(direction,1/length);s->right=(BteVec){s->forward.z,0,-s->forward.x};}
   else s->has_target=0;
  }
 }
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
 if(!crew_active()||!initialized)return;
 CrewShot *sample=crew_shot(P(shell,0x90));
 if(sample&&sample->has_target){
  BteVec pos=bv(call_vec(P(shell,0x20),"get_position"));
  BteVec delta=bte_sub(pos,sample->target_pos);float depth=fabsf(bte_dot(delta,sample->forward));
  if(depth<sample->closest_error){sample->closest_error=depth;sample->closest=pos;}
 }
 if(B(shell,0x9c))return;
 CrewShot *s=crew_shot(P(shell,0x90));if(s&&!s->finished)s->finished=now_ms()+300;
}
static void crew_projectile_impact_observed(void *info){if(!crew_active())return;CrewShot *s=crew_shot(info);if(s&&!s->finished)s->finished=now_ms()+300;}
static UpdateFn original_crew_shell_reset;
static void crew_shell_reset(void *shell,const void *mi){
 CrewShot *s=crew_shot(P(shell,0x90));
 if(crew_active()&&s&&!s->finished){
  crew_observe_shell(shell,1);s->finished=now_ms()+300;
 }
 original_crew_shell_reset(shell,mi);
}
