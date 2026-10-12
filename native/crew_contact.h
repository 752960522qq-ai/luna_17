#pragma once
static void crew_acquire_target(void *pc,unsigned long now){
 if(now-crew_scan_time<250)return;crew_scan_time=now;
 void *turret=P(pc,0x50),*root=P(pc,0x20);if(!unity_exists(turret)||!unity_exists(root))return;
 Vec3 origin=call_vec(root,"get_position"),forward=call_vec(root,"get_forward");origin.y+=1;
 Vec3 target={0};
 if(bte_mode==2&&bte_target_valid)target=bte_target_world;
 else {void *ct=unity_exists(bte_camera)?hatch_call(bte_camera,"get_transform",0,0):0;if(!unity_exists(ct))return;origin=call_vec(ct,"get_position");target=uv(bte_add(bv(origin),bte_scale(bv(call_vec(ct,"get_forward")),3000)));}
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
   EnemyHit hit={0};if(bte_cast(origin,p,&hit)&&hit.distance<d-.1f&&!bte_hit_belongs_to(&hit,tr))continue;
   best=cosine;chosen=s;pos=p;type=kind?2:1;

  }
 }
 if(!chosen){
  if(!crew_contact_lost)crew_contact_lost=now;
  if(now-crew_contact_lost>=500)crew_contact=0;
  return;
 }
 crew_contact_lost=0;crew_contact_pos=pos;
 if(chosen==crew_contact)return;
 crew_contact=chosen;
 int event=(crew_event_mask&(1u<<17))?17:1;
 crew_contact_time=now;
 Vec3 hull=call_vec(root,"get_position");
 Vec3 delta={pos.x-hull.x,pos.y-hull.y,pos.z-hull.z};
 float angle=atan2f(forward.z*delta.x-forward.x*delta.z,forward.x*delta.x+forward.z*delta.z);
 int clock=((int)lroundf(angle*6.f/3.14159265359f)+12)%12;
 float range=sqrtf(delta.x*delta.x+delta.y*delta.y+delta.z*delta.z);
 crew_notice_publish(type,clock?clock:12,(int)lroundf(range));
 if(!(crew_event_mask&(1u<<event))||!crew_gate_begin())return;
 crew_pending[0]=event;crew_pending[1]=type;crew_pending[2]=clock?clock:12;float distance=sqrtf(delta.x*delta.x+delta.y*delta.y+delta.z*delta.z);
 crew_pending[3]=distance<300?((int)distance):(int)lroundf(distance);crew_gate_publish();
}
