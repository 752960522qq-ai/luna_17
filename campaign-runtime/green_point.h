#include "preview_steps.h"
typedef struct {SceneVec point,normal;unsigned face;float distance,uv[2];int collider;} SceneHit;
static void *line_method,*hit_transform,*tr_class,*shot_class,*cam_class,*physics,*screen_class;
static float cached_speed[5],observed_speed[5],green_screen[4],draw_at;
static int cached_profile=-1,loaded_at=-1,gun_muzzle=-1;
static int last_ammo=-1,green_valid;
static void reset_instruments(void){
  memset(cached_speed,0,sizeof(cached_speed));memset(observed_speed,0,sizeof(observed_speed));draw_at=-1;last_ammo=-1;green_valid=0;cached_profile=-1;
}
static int vec_call(void *c,void *o,const char *name,int n,void **args,SceneVec *v){
  int e=0;void *b=call(c,o,name,n,args,&e);if(!b||e)return 0;
  memcpy(v,(char*)b+16,sizeof(*v));return isfinite(v->x)&&isfinite(v->y)&&isfinite(v->z);
}
typedef struct {void *player;int layers;} RayWorld;
static int line(void *w,SceneVec src,SceneVec to,SceneVec *out){
  RayWorld *world=w;SceneVec delta=dv(to,src);float distance=length(delta);if(distance<.0001f)return 0;
  SceneVec direction=plus((SceneVec){0},delta,1.f/distance);
  for(int n=0;n<12;n++){
    int ignoreTriggers=1,e=0;SceneHit h={0};void *args[]={&src,&to,&h,&world->layers,&ignoreTriggers};
    void *b=invoke(line_method,0,args,&e);if(!b||e)return -1;if(!AT(b,16,uint8_t))return 0;
    void *transform=invoke(hit_transform,&h,0,&e);if(!live(transform)||e)return -1;
    void *p[]={world->player};void *own=call(tr_class,transform,"IsChildOf",1,p,&e);if(!own||e)return -1;
    if(!AT(own,16,uint8_t)){*out=h.point;return 1;}
    if(h.distance+.02f>=length(dv(to,src)))return 0;
    src=plus(h.point,direction,.02f);
  }return -1;
}
static float live_speed(void *gun,int shell){
  int e=0,normal=0;void *args[]={&shell,&normal};void *info=call(ctrl_launcher,gun,"GetShellAttackInfo",2,args,&e);
  if(e||!info)return NAN;
  void *type=AT(info,0,void*);
  int off=field(type,"initSpeed"); /* 5.1.0 AttackInfo shared with the projectile, not a weapon card speed. */
  return off>=16?AT(info,off,float):NAN;
}
/* A fired pool object carries the simulator's initialized speed. Prefer that
   value once a shot of this type has actually flown. Never use a ricochet or
   another tank's shell, and never mutate a live projectile. */
static void observe_pool(void *pool,SceneVec muzzle,void *seedshot){
  if(!pool||!seedshot)return;
  static int initialized=-2,ricochet,hit,velocity,nominal,infoptr,shelltype,tip;
  if(initialized==-2){
    initialized=field(shot_class,"isSetInitV");ricochet=field(shot_class,"isRicochet");
    hit=field(shot_class,"isHitUnit");velocity=field(shot_class,"currentVelocity");
    nominal=field(shot_class,"nrmInitV");infoptr=field(shot_class,"<ShellAttackInfo>k__BackingField");
    tip=field(shot_class,"thisTrf");shelltype=-1;
  }
  if(initialized<16||ricochet<16||hit<16||velocity<16||nominal<16||infoptr<16||tip<16)return;
  int n=AT(pool,24,int);if(n<1||n>32)return;
  for(int i=0;i<n;i++){
    void *go=AT(pool,32+i*sizeof(void*),void*);if(!live(go)||!flag(goc,go,"get_activeSelf"))continue;
    void *shot=i==0?seedshot:component(go,shot_class);
    if(!live(shot)||!AT(shot,initialized,uint8_t)||AT(shot,hit,uint8_t)||AT(shot,ricochet,uint8_t))continue;
    void *info=AT(shot,infoptr,void*);if(!info)continue;
    if(shelltype<16)shelltype=field(AT(info,0,void*),"shellType");
    if(shelltype<16)continue;
    int code=AT(info,shelltype,int);if(code<0||code>4)continue;
    SceneVec p;void *tr=AT(shot,tip,void*);if(!live(tr)||!vec_call(tr_class,tr,"get_position",0,0,&p))continue;
    float v=length(AT(shot,velocity,SceneVec)),origin=AT(shot,nominal,float);
    if(!isfinite(v)||v<=1||v>8000||length(dv(p,muzzle))>fminf(120,v*.12f))continue;
    /* Stock ShellMove writes the launch magnitude before applying direction or
       gravity. A later falling/rising velocity must not become the next shot's initial speed. */
    if(isfinite(origin)&&origin>0&&origin<=8000)observed_speed[code]=origin;
  }
}
static void update_green(float *out,int profiles,int aim){
  if(!owner||(bound!=22&&bound!=23)||(!am_t26&&!am_player_f))return;
  out[2]=0; /* own the marker while playing this mission; invalid paths clear old dots */
  if(!aim || !live(bound_pc)||!live(bound_gun)||!live(bound_st)||!live(bound_hud))return;
  if(!tr_class){
    tr_class=hatch_class("UnityEngine","Transform");shot_class=hatch_class("","ShellMove");
    cam_class=hatch_class("UnityEngine","Camera");physics=hatch_class("UnityEngine","Physics");screen_class=hatch_class("UnityEngine","Screen");
    line_method=physics?lookup(physics,"Linecast",5):0;
    void *rh=hatch_class("UnityEngine","RaycastHit");hit_transform=rh?lookup(rh,"get_transform",0):0;
    gun_muzzle=field(ctrl_launcher,"thisTrf");loaded_at=field(uStatus,"loadedShell");
  }
  if(!line_method||!hit_transform||!tr_class||!cam_class||!shot_class||!screen_class||gun_muzzle<16||loaded_at<16)return;
  void *control=read_ref(controller,bound_gc,"mCamCtrl");
  if(!live(control))return;
  void *cc=AT(control,0,void*);int mode=field(cc,"viewMode");
  if(mode<16||AT(control,mode,int)!=0)return;
  int sight=number(ui,bound_hud,"get_CurrentSightType",-1);if(sight<0||sight>2)return;
  void *camera=read_ref(cc,control,"myCamera"),*mount=AT(bound_gun,gun_muzzle,void*);
  void *player=read_ref(ctrl_pc,bound_pc,"thisTrf");if(!live(camera)||!live(mount)||!live(player))return;
  int shell=AT(bound_st,loaded_at,int);if(shell<0||shell>4)return;
  int physical=(profiles&(am_t26?1:2))!=0;
  if(cached_profile!=physical){memset(cached_speed,0,sizeof(cached_speed));cached_profile=physical;draw_at=-1;}
  float now=scalar(timec,0,"get_unscaledTime");
  if(now<draw_at||now-draw_at>=.035f||shell!=last_ammo){
    draw_at=now;last_ammo=shell;green_valid=0;
    SceneVec pos,dir,world,screen;
    void *pool=read_ref(ctrl_launcher,bound_gun,shell==1?"shellHeGos":"shellApGos"),*seed=first(pool);
    void *shot=component(seed,shot_class);if(!live(shot))return;
    /* The pool's fpTrf is the reference ShellMove itself uses at launch. */
    void *fp=read_ref(shot_class,shot,"fpTrf");if(!live(fp))return;
    if(!vec_call(tr_class,fp,"get_position",0,0,&pos)||!vec_call(tr_class,fp,"get_forward",0,0,&dir))return;
    float g=9.81f;
    if(!physical){int grav=field(shot_class,"gravityAccel");if(grav<16)return;g=AT(shot,grav,float);}
    observe_pool(pool,pos,shot);
    if(!cached_speed[shell]&&!observed_speed[shell]){float measured=live_speed(bound_gun,shell);if(isfinite(measured)&&measured>0)cached_speed[shell]=measured;}
    float speed=observed_speed[shell]>0?observed_speed[shell]:cached_speed[shell]*(physical?1.f:.23f);
    int layer=field(shot_class,"hitLayerMask");
    /* Missing/empty masks on older donor pools mean Unity's default ray layers. */
    int mask=layer>=16?AT(shot,layer,int):0;
    /* The cumulative projectile module records the live launcher's root as
       its owner. In a grouped mission this need not equal PlayerControl.thisTrf.
       Use the same collision exclusion as that actual shot, including on retry. */
    void *skip=player;
    if(physical){
      int e=0;void *root=call(tr_class,fp,"get_root",0,0,&e);
      if(!e&&live(root))skip=root;
    }
    RayWorld rw={skip,mask?mask:-5};float dt=scalar(timec,0,"get_fixedDeltaTime");
    if(!preview_ticks(pos,dir,speed,g,dt,&rw,line,&world))return;
    void *project[]={&world};if(!vec_call(cam_class,camera,"WorldToScreenPoint",1,project,&screen)||screen.z<=0)return;
    int w=number(screen_class,0,"get_width",0),h=number(screen_class,0,"get_height",0);if(w<=0||h<=0)return;
    green_screen[0]=screen.x/w;green_screen[1]=1.f-screen.y/h;
    green_screen[2]=length(dv(world,pos));green_screen[3]=(float)shell;
    green_valid=green_screen[0]>=0&&green_screen[0]<=1&&green_screen[1]>=0&&green_screen[1]<=1;
  }
  if(green_valid){out[2]=1;memcpy(out+3,green_screen,sizeof green_screen);}
}
