/* Built-in F triggers use the stock EventSystem PointerDown/Up/Exit/Cancel.
   For ordinary fields, the same loader and trigger driver as the Luchs own fire. */
#include "battle_flow.h"
static int bound,owner,last_count,am_player_f,am_t26;
static void *bound_gc,*bound_st,*bound_hud,*bound_pc,*bound_gun,*bound_turret,*bound_stats;
static ClipClock magazine;
static float f_last,cycle_before;
static int button_locked;
static void *locked_button;
static void unlock_button(void){
  if(button_locked&&live(locked_button)){bool on=true;int e=0;void *args[]={&on};call(goc,locked_button,"SetActive",1,args,&e);}
  button_locked=0;locked_button=0;
}
static int unit_offset=-1,pool_offset=-1, exclusive;
static void reset_instruments(void);
static void fire_binding(int idx,int mode,void *gc,void *st){
  int e=0;
  if(!ready || mode<0 || mode==2 || !live(gc)||!live(st)||deadoff<16||AT(st,deadoff,uint8_t))gc=st=0;
  int ident=st?number(obj,st,"GetInstanceID",0):0;
  if(ident==owner&&idx==bound&&live(bound_gun)&&live(bound_turret)&&live(bound_hud))return;
  if(ident!=owner||idx!=bound){
    if(idx==bound)unlock_button();else{button_locked=0;locked_button=0;}
    magazine=(ClipClock){0};f_last=0;last_count=-1;exclusive=0;reset_instruments();
  }
  owner=ident;bound=idx;bound_gc=gc;bound_st=st;bound_pc=bound_gun=bound_stats=bound_turret=0;am_player_f=am_t26=0;
  if(!owner||boardoff<16)return;
  if(unit_offset<16)unit_offset=field(uStatus,"unitName");
  if(unit_offset<16)return;
  void *name=AT(st,unit_offset,void*);am_player_f=named(name,"Panzer_II_Ausf_F");am_t26=named(name,"T26");
  if(!am_player_f&&idx!=23&&!(idx==22&&am_t26))return;
  bound_hud=AT(gc,boardoff,void*);if(!live(bound_hud))return;
  void *player=call(controller,gc,"get_PlayerGo",0,0,&e);
  bound_pc=component(player,ctrl_pc);if(!live(bound_pc))return;
  bound_gun=first(read_ref(ctrl_pc,bound_pc,"launchers"));
  bound_turret=read_ref(ctrl_pc,bound_pc,"tMove");
  bound_stats=stats(bound_hud);
  if(pool_offset<16)pool_offset=field(ctrl_launcher,"shellApGos");
  exclusive=idx==23&&find("Hatch F Trigger");
}
static unsigned pool_state(void *pool,int *free_count){
  unsigned mask=0;*free_count=0;int n=pool?AT(pool,24,int):0;
  if(n<1||n>32)return 0;
  for(int i=0;i<n;i++){void *g=AT(pool,32+sizeof(void*)*i,void*);if(!live(g))continue;
    if(flag(goc,g,"get_activeSelf"))mask|=1u<<i;else ++*free_count;}
  return mask;
}
/* out[0]=-1 if not an F; [0..1]=remaining, scaled seconds until the full clip.
   Read only the PLAYER's stats, never the AI's alternating launcher. */
static void update_cannon(float *out){
  out[0]=-1.f;
  if(!owner||!live(bound_st)||!live(bound_gun)||!live(bound_hud)||!live(bound_turret))return;
  float now=scalar(timec,0,"get_time");if(!isfinite(now))return;
  if(now<f_last){magazine=(ClipClock){0};last_count=-1;}f_last=now;gun_tick(&magazine,now);
  if(!bound_stats)bound_stats=stats(bound_hud);
  int count=bound_stats?number(stats_class,bound_stats,"get_FireNumByPlayer",-1):-1;
  float start=scalar(ctrl_tm,bound_turret,"get_LoadingStartTime");
  int free_count=0;void *pool=pool_offset>=16?AT(bound_gun,pool_offset,void*):0;
  unsigned mask=0;
  if(exclusive && magazine.pending){
    mask=pool_state(pool,&free_count);
    if((mask&~magazine.pool)||(count>=0&&count>magazine.before&&start>cycle_before)
       ||(isfinite(start)&&isfinite(cycle_before)&&start>cycle_before && count<0))
       gun_accept(&magazine,magazine.issued);
    else if(now-magazine.issued>1.f&&!flag(ui,bound_hud,"get_IsFireWaiting"))magazine.pending=0;
  }
  if(!exclusive&&am_player_f&&count>last_count&&last_count>=0&&start>cycle_before){gun_accept(&magazine,now);}
  if(!exclusive)cycle_before=start;
  if(!exclusive&&am_player_f){
    if(magazine.spent==10){
      void *btn=first(read_ref(ui,bound_hud,"fireBtnGos"));
      if(live(btn)&&flag(goc,btn,"get_activeSelf")){locked_button=btn;button_locked=1;deactivate(btn);}
    }else if(button_locked)unlock_button();
  }
  last_count=count;
  if(am_player_f){out[0]=(float)(10-magazine.spent);out[1]=magazine.spent==10?fmaxf(0,magazine.next-now):0;}
  if(bound!=23)return;
  if(!exclusive)exclusive=find("Hatch F Trigger")!=0;
  if(!exclusive)return;
  void *down=find("Hatch F Down"),*held=find("Hatch F Held");
  int tap=down!=0;if(down)deactivate(down);
  static int menu_off=-1;if(menu_off<16)menu_off=field(ui,"isMenuPopUp");
  int e=0;
  if(scalar(timec,0,"get_timeScale")<=0 || (menu_off>=16&&AT(bound_hud,menu_off,uint8_t))){
    if(held)deactivate(held);
    return;
  }
  if(!am_player_f){
    if(tap){int gun=0;void *a[]={&gun};call(ui,bound_hud,"ButtonFire",1,a,&e);}return;
  }
  if(!tap && !held)return;
  if(!gun_can(&magazine,now)||flag(ctrl_tm,bound_turret,"get_IsNowLoading")||flag(ui,bound_hud,"get_IsFireWaiting"))return;
  mask=pool_state(pool,&free_count);if(!free_count)return;
  magazine.pool=mask;magazine.before=count;magazine.issued=now;cycle_before=start;
  int main_gun=0;void *a[]={&main_gun};call(ui,bound_hud,"ButtonFire",1,a,&e);
  if(!e)magazine.pending=1;
}
#include "green_point.h"
JNIEXPORT jboolean JNICALL Java_com_luna17_campaign_CampaignLoop_sample(JNIEnv *env,jclass cls,jfloatArray dst,jint profiles,jboolean aim){
  (void)cls;
  if(!dst||(*env)->GetArrayLength(env,dst)!=7)return JNI_FALSE;
  float out[7]={-1,0,-1,0,0,0,0};
  if(ready && !terminal){update_cannon(out);update_green(out,profiles,aim);}
  (*env)->SetFloatArrayRegion(env,dst,0,7,out);
  return !terminal&&owner&&(am_player_f||bound==22||bound==23);
}
