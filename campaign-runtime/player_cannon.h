/* Offline Panzer II F: use the same UGUI Button for both taps and holds. This
 * script runs on Unity's frame queue. No platform overlay handles the fire touch. */
#include "clip.h"
#include <stdlib.h>
static void *button_c,*select_c,*resources_c,*str_c,*array_c,*pc_c,*launch_c,*tr_c,*comp_c;
static void *load_relay,*make_obj,*array_get,*array_set;
static int unit_at=-1, guns_at=-1, pool_at=-1, f_scene=-1, f_owner, f_enabled, configured, attempted;
static int pending, issued_held, baseline_ammo, reload_kind=-1, snapshot[2];
static float prior_cycle;
static void *turret_c, *integer_value;
static unsigned baseline_mask;
static float issued, f_clock;
static PlayerClip clip;
static void *method_arg(void *cl,const char *name,int n,int arg,void *type){
  void *it=0,*m;
  while(cl && (m=ha_methods(cl,&it))) {
    if(AT(m,0x52,uint8_t)!=n || strcmp(AT(m,0x18,const char*),name))continue;
    void **params=AT(m,0x30,void**);
    if(params && ha_param_class(params[arg])==type)return m;
  }
  return 0;
}
static int f_init(void){
  button_c=hatch_class("UnityEngine.UI","Button");select_c=hatch_class("UnityEngine.UI","Selectable");
  resources_c=hatch_class("UnityEngine","Resources");str_c=hatch_class("System","String");
  array_c=hatch_class("System","Array");pc_c=hatch_class("","PlayerControl");launch_c=hatch_class("","Launcher");
  tr_c=hatch_class("UnityEngine","Transform");comp_c=hatch_class("UnityEngine","Component");
  if(!button_c||!select_c||!resources_c||!str_c||!array_c||!pc_c||!launch_c||!tr_c||!comp_c)return 0;
  load_relay=method_arg(resources_c,"Load",2,1,hatch_class("System","Type"));make_obj=over(obj,"Instantiate",obj);
  array_get=over(array_c,"GetValue",intc);array_set=method_arg(array_c,"SetValue",2,1,intc);
  unit_at=field(uStatus,"unitName");guns_at=field(pc_c,"launchers");pool_at=field(launch_c,"shellApGos");
  return load_relay&&make_obj&&array_get&&array_set&&unit_at>=16&&guns_at>=16&&pool_at>=16;
}
static int truth(void *cl,void *o,const char *k){
  if(!o)return 0;
  int err=0;void *b=call(cl,o,k,0,0,&err);return b&&!err&&AT(b,16,uint8_t);
}
static int eqascii(void *s,const char *name){
  size_t n=strlen(name);
  if(!s||AT(s,16,int)!=(int)n)return 0;
  for(size_t i=0;i<n;i++)if(AT(s,20+2*i,uint16_t)!=(unsigned char)name[i])return 0;
  return 1;
}
static int ammo_read(void *st,int *slots){
  int e=0,total=0;
  void *arr=call(uStatus,st,"get_ShellNums",0,0,&e);
  if(!arr || e || AT(arr,24,uintptr_t)<3 || AT(arr,24,uintptr_t)>16)return -1;
  for(int i=0;i<3;i+=2){
    void *args[]={&i},*boxed=invoke(array_get,arr,args,&e);
    if(e||!boxed)return -1;
    void *s=call(AT(boxed,0,void*),(char*)boxed+16,"ToString",0,0,&e);
    if(!s||e)return -1;
    int digits=AT(s,16,int),value=0;if(digits<1||digits>7)return -1;
    for(int j=0;j<digits;j++){int d=AT(s,20+2*j,uint16_t)-'0';if(d<0||d>9)return -1;value=10*value+d;}
    if(slots)slots[i/2]=value;
    total+=value;
  }
  return total;
}
static void *stock_int(void *st,int n){
  int e=0;
  if(!integer_value){
    void *v=call(uStatus,st,"get_LoadingTime",0,0,&e);
    if(!v||e)return 0;
    integer_value=over(AT(v,0,void*),"op_Implicit",intc);
  }
  void *args[]={&n};return invoke(integer_value,0,args,&e);
}
static float cycle_start(void *turret){
  int e=0;void *v=turret?call(turret_c,turret,"get_LoadingStartTime",0,0,&e):0;
  return v&&!e?AT(v,16,float):-1.f;
}
static void stock_reload(void *st,void *turret,int full){
  if(!turret||reload_kind==full)return;
  int e=0,offset=field(turret_c,"loadingDelay");void *value=stock_int(st,full?5:1);
  if(offset<16||!value)return;
  void *a[]={(char*)value+16};call(uStatus,st,"set_LoadingTime",1,a,&e);
  if(!e){AT(turret,offset,float)=full?-.15f:-.6f;reload_kind=full;}
}
static void refund_failed(void *st){
  int slots[2],e=0;
  if(baseline_ammo<0 || ammo_read(st,slots)!=baseline_ammo-1)return;
  void *arr=call(uStatus,st,"get_ShellNums",0,0,&e);
  if(!arr||e)return;
  int k=clip_failed_slot(snapshot,slots);if(k>=0){
    int index=2*k;void *val=stock_int(st,snapshot[k]);
    if(val){void *a[]={val,&index};invoke(array_set,arr,a,&e);}
  }
}
static int mask_pool(void *pool,unsigned *mask){
  size_t n=pool?AT(pool,24,uintptr_t):0;unsigned out=0;int free_count=0;
  if(!n||n>32)return 0;
  for(size_t i=0;i<n;i++){
    void *o=AT(pool,32+sizeof(void*)*i,void*);if(!o||!AT(o,16,void*))continue;
    if(truth(goc,o,"get_activeSelf"))out|=(1u<<i);else free_count++;
  }
  *mask=out;return free_count;
}
static void dispose_go(void *o){
  if(!o)return;
  int e=0;void *a[]={o};invoke(over(obj,"Destroy",obj),0,a,&e);
}
static void grow_pool(void *launcher){
  /* Only clone an inactive projectile. Preserve existing shots and their owners.
   * SetValue goes through managed array/field setters with their write barriers. */
  void *pool=AT(launcher,pool_at,void*);size_t n=pool?AT(pool,24,uintptr_t):0;
  if(n==0||n>=12)return;
  void *source=0;for(size_t i=0;i<n;i++){void *s=AT(pool,32+sizeof(void*)*i,void*);if(s&&AT(s,16,void*)&&!truth(goc,s,"get_activeSelf")){source=s;break;}}
  if(!source)return;
  int e=0,flags=4|16|32;
  void *ty=hatch_type_object(launch_c),*fargs[]={ha_string("shellApGos"),&flags};
  void *fieldinfo=ty?call(AT(ty,0,void*),ty,"GetField",2,fargs,&e):0;
  if(!fieldinfo||e)return;
  void *tr=call(goc,source,"get_transform",0,0,&e);
  void *parent=tr?call(tr_c,tr,"get_parent",0,0,&e):0;
  void *newarr=ha_array(goc,12),*clones[12]={0};if(!newarr||e)return;
  for(int i=0;i<12&&!e;i++){
    void *o=i<(int)n?AT(pool,32+sizeof(void*)*(size_t)i,void*):0;
    if(i>=(int)n){void *args[]={source};o=clones[i]=invoke(make_obj,0,args,&e);if(!o||e){e=1;break;}
      if(parent){void *nt=call(goc,o,"get_transform",0,0,&e);bool preserve=false;void *a[]={parent,&preserve};if(nt)call(tr_c,nt,"SetParent",2,a,&e);}
    }
    void *args[]={o,&i};invoke(array_set,newarr,args,&e);
  }
  if(!e){void *args[]={launcher,newarr};call(AT(fieldinfo,0,void*),fieldinfo,"SetValue",2,args,&e);}
  if(e||AT(launcher,pool_at,void*)!=newarr){for(size_t i=n;i<12;i++)dispose_go(clones[i]);}
}
static int swap_events(void *a,void *b){
  int e=0;void *x=call(button_c,a,"get_onClick",0,0,&e),*y=call(button_c,b,"get_onClick",0,0,&e);
  if(!x||!y||e)return 0;
  void *v[]={x};call(button_c,b,"set_onClick",1,v,&e);if(e)return 0;
  v[0]=y;call(button_c,a,"set_onClick",1,v,&e);return !e;
}
#define RELAY "Hatch Autocannon Relay(Clone)"
static void release_input(void){
  void *mirror=find(RELAY);
  if(mirror){
    int e=0;void *b=component(mirror,button_c);
    void *graphic=b?call(select_c,b,"get_targetGraphic",0,0,&e):0;
    void *live=graphic?call(comp_c,graphic,"get_gameObject",0,0,&e):0;
    void *a=component(live,button_c);
    if(a&&b&&f_enabled)swap_events(a,b);
    dispose_go(mirror);
  }
  f_enabled=pending=attempted=0;clip_reset(&clip);
}
static void *install_relay(void *button){
  int e=0;
  void *path[]={ha_string("hatch/controls/autocannonrelay"),hatch_type_object(goc)};
  void *prefab=invoke(load_relay,0,path,&e);if(!prefab||e)return 0;
  void *args[]={prefab};void *go=invoke(make_obj,0,args,&e);if(!go||e)return 0;
  void *mirror=component(go,button_c);
  void *graphic=call(select_c,button,"get_targetGraphic",0,0,&e);
  if(!mirror||!graphic||e){dispose_go(go);return 0;}
  bool enabled=false;void *disable[]={&enabled},*remember[]={graphic};
  call(hatch_class("UnityEngine","Behaviour"),mirror,"set_enabled",1,disable,&e);
  call(select_c,mirror,"set_targetGraphic",1,remember,&e);
  if(e||!swap_events(button,mirror)){dispose_go(go);return 0;}
  f_enabled=1;return go;
}
static void *marker_of(void *relay){
  int e=0,zero=0;void *tr=call(goc,relay,"get_transform",0,0,&e);void *a[]={&zero};
  void *ch=tr?call(tr_c,tr,"GetChild",1,a,&e):0;
  return ch&&!e?call(comp_c,ch,"get_gameObject",0,0,&e):0;
}
static void fire_binding(int idx,int mode,void *gc,void *st){
  /* Scene unload also destroys the nonpersistent helper and the original HUD. */
  if(idx!=f_scene){f_scene=idx;f_enabled=pending=f_owner=attempted=0;clip_reset(&clip);}
  if(!gc || !st || mode<0 || mode==2){if(f_enabled)release_input();f_owner=0;return;}
  if(!configured)configured=f_init();
  if(!configured)return;
  int live=mode>=0&&mode!=2&&gc&&st&&AT(st,16,void*)&&deadoff>=16&&!AT(st,deadoff,uint8_t);
  int id=0,e=0;void *ident=live&&eqascii(AT(st,unit_at,void*),"Panzer_II_Ausf_F")?call(obj,st,"GetInstanceID",0,0,&e):0;
  if(ident&&!e)id=AT(ident,16,int);
  if(id!=f_owner){
    if(f_enabled)release_input();
    f_owner=id;attempted=pending=0;reload_kind=-1;clip_reset(&clip);
  }
}
JNIEXPORT jboolean JNICALL Java_com_luna17_campaign_CampaignLoop_autocannonFrame(JNIEnv *env,jclass cls){
  (void)env;(void)cls;
  if(!f_owner || !ready || !configured)return JNI_FALSE;
  int e=0;
  void *gc=instance(controller);if(!gc||!AT(gc,16,void*)||statoff<16||boardoff<16)return JNI_FALSE;
  void *st=AT(gc,statoff,void*),*hud=AT(gc,boardoff,void*);
  if(!st||!AT(st,16,void*)||!hud||!eqascii(AT(st,unit_at,void*),"Panzer_II_Ausf_F")||AT(st,deadoff,uint8_t))return JNI_FALSE;
  void *player=call(controller,gc,"get_PlayerGo",0,0,&e);void *pc=component(player,pc_c);
  void *guns=pc?AT(pc,guns_at,void*):0;if(!guns||AT(guns,24,uintptr_t)<1)return JNI_FALSE;
  void *gun=AT(guns,32,void*);if(!gun||!AT(gun,16,void*))return JNI_FALSE;
  void *bg=find("Button Fire"),*btn=component(bg,button_c);
  if(!btn || !truth(select_c,btn,"IsInteractable"))return JNI_FALSE;
  void *relay=find(RELAY);
  if(!relay){f_enabled=0;relay=install_relay(btn);if(!relay)return JNI_FALSE;}
  void *mark=marker_of(relay);if(!mark)return JNI_FALSE;
  if(!attempted){grow_pool(gun);attempted=1;}
  void *time=call(timec,0,"get_time",0,0,&e),*scale=call(timec,0,"get_timeScale",0,0,&e);
  int clicked=truth(goc,mark,"get_activeSelf");if(clicked)deactivate(mark);
  if(!time||!scale||e||AT(scale,16,float)<=0)return JNI_TRUE;
  float now=AT(time,16,float);if(!isfinite(now))return JNI_TRUE;
  if(now<f_clock){clip_reset(&clip);pending=0;}f_clock=now;
  if(!turret_c)turret_c=hatch_class("","TurretMove");
  void *turret=call(ui,hud,"get_PlayerTurretMove",0,0,&e);
  stock_reload(st,turret,clip.rounds==0 && clip.available>now);
  int held=truth(select_c,btn,"IsPressed");
  void *pool=AT(gun,pool_at,void*);unsigned mask=0;
  if(!held&&!clicked&&!pending){clip.heldShot=0;return JNI_TRUE;}
  int free_count=mask_pool(pool,&mask);
  if(pending){
    int n=ammo_read(st,0);float cycle=cycle_start(turret);
    if(clip_ack(baseline_mask,mask,baseline_ammo,n,prior_cycle,cycle)){
      clip_launched(&clip,now,issued_held);stock_reload(st,turret,clip.rounds==0);pending=0;
    } else if(now-issued<.6f || (now-issued<2.f && truth(ui,hud,"get_IsFireWaiting")))return JNI_TRUE;
    else {refund_failed(st);pending=0;}
  }
  if(!clip_request(&clip,now,held,clicked,free_count))return JNI_TRUE;
  /* The UI method keeps the stock crew, ownership, ammo and loading checks.
   * Its position in the UI is irrelevant: input is sampled from the Selectable. */
  if((turret && truth(turret_c,turret,"get_IsNowLoading")) || truth(ui,hud,"get_IsFireWaiting"))return JNI_TRUE;
  static int menu_at=-2;if(menu_at==-2)menu_at=field(ui,"isMenuPopUp");
  if(menu_at>=16 && AT(hud,menu_at,uint8_t))return JNI_TRUE;
  int before=ammo_read(st,snapshot);if(before==0)return JNI_TRUE;
  prior_cycle=cycle_start(turret);
  int mainGun=0;void *a[]={&mainGun};call(ui,hud,"ButtonFire",1,a,&e);if(e)return JNI_TRUE;
  unsigned after=0;mask_pool(pool,&after);
  int left=ammo_read(st,0);
  if(clip_ack(mask,after,before,left,prior_cycle,cycle_start(turret))){clip_launched(&clip,now,held);stock_reload(st,turret,clip.rounds==0);}
  else {pending=1;issued=now;issued_held=held;baseline_mask=mask;baseline_ammo=before;}
  return JNI_TRUE;
}
