#pragma once
// The lock spans one entire utterance, including every multipart clip.
#include "crew_gate.h"
static volatile int crew_enabled;
static unsigned crew_event_mask;
static void (*original_radio_voice)(void *,int,const void *);
static UpdateFn original_radio_reply;
static void crew_target(int *data){
    if(!unity_exists(player_control))return;
    void *turret=P(player_control,0x50),*root=P(player_control,0x20);
    if(!unity_exists(turret)||!unity_exists(root))return;
    Vec3 target=call_vec(turret,"get_TargetPos"),origin=call_vec(root,"get_position"),forward=call_vec(root,"get_forward");
    Vec3 delta={target.x-origin.x,target.y-origin.y,target.z-origin.z};
    float distance=sqrtf(delta.x*delta.x+delta.y*delta.y+delta.z*delta.z);
    if(!isfinite(distance)||distance<50||distance>3000)return;
    float angle=atan2f(forward.z*delta.x-forward.x*delta.z,forward.x*delta.x+forward.z*delta.z);
    int clock=((int)lroundf(angle*6.f/3.14159265359f)+12)%12;
    data[2]=clock?clock:12;data[3]=(int)lroundf(distance);
    const char *classes[]={"UnitStatus","AirUnitStatus"};float best=30.f*30.f;
    for(int kind=0;kind<2;kind++){
        void *type=hatch_type_object(hatch_class("",classes[kind]));if(!type)continue;
        bool inactive=false;void *args[]={type,&inactive};int error=0;
        void *all=enemy_invoke(hatch_method(hatch_class("UnityEngine","Object"),"FindObjectsOfType",2,hatch_class("System","Type")),0,args,&error);
        int count=all?I(all,0x18):0;if(error||count<0||count>1024)continue;
        for(int i=0;i<count;i++){
            void *status=P(all,0x20+i*8);if(!unity_exists(status)||status==player_status)continue;
            void *friend=method(status,"get_IsMyFriend",0);if(!friend||((bool (*)(void *,const void *))P(friend,0))(status,friend))continue;
            void *tr=enemy_invoke(method(status,"get_transform",0),status,0,&error);if(error||!unity_exists(tr))continue;
            Vec3 p=call_vec(tr,"get_position");float x=p.x-target.x,y=p.y-target.y,z=p.z-target.z,d=x*x+y*y+z*z;
            if(d>best)continue;best=d;data[1]=kind?2:1;
            if(!kind){char name[112];utf8_name(P(status,0x68),name,sizeof(name));
                if(strstr(name,"T34"))data[1]=4;else if(strstr(name,"Tiger"))data[1]=5;else if(strstr(name,"Panther"))data[1]=6;
            }
        }
    }
}
static void crew_trigger(int event){
    if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||state!=3||!offline_mode()||event<0||event>16||!(crew_event_mask&(1u<<event)))return;
    if(!crew_gate_begin())return;
    memset(crew_event,0,sizeof(crew_event));crew_event[0]=event;
    if(event==1||event==3)crew_target(crew_event);
    crew_gate_publish();
}
static void crew_radio_voice(void *self,int event,const void *mi){
    if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode()){original_radio_voice(self,event,mi);return;}
    crew_trigger(event);
}
static void crew_radio_reply(void *self,const void *mi){
    if(!__atomic_load_n(&crew_enabled,__ATOMIC_ACQUIRE)||!offline_mode())original_radio_reply(self,mi);
    // The stock reply is an automatic follow-up. Do not queue it behind speech.
}
static void *crew_loading_owner;
static int crew_was_loading;
static void crew_player_update(void *pc){
    void *turret=P(pc,0x50);if(!unity_exists(turret))return;
    int loading=!B(turret,0xe0);
    if(crew_loading_owner!=pc){crew_loading_owner=pc;crew_was_loading=loading;return;}
    if(crew_was_loading&&!loading)crew_trigger(11);
    if(!crew_was_loading&&loading){
        int offset=bte_field_offset(player_status,"usingShell");
        int shell=offset>=0?I(player_status,offset):-1;
        if(shell>=0&&shell<5)crew_trigger(12+shell);
    }
    crew_was_loading=loading;
}
