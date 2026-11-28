/* Only the German extra field contains this press marker. The ordinary Unity
   ButtonZoomInOut callback still runs synchronously, with all stock guards. */
static void *aim_press,*fire_selectable,*selectable_class;
static void clear_optics_refs(void){aim_press=fire_selectable=0;}
static void *resolve_press(void){
  int e=0;void *aim=find("Button Aim");if(!live(aim))return 0;
  void *tr=call(goc,aim,"get_transform",0,0,&e);
  if(e||!live(tr))return 0;
  void *a[]={ha_string("Hatch F Aim Press")};
  void *marker=call(AT(tr,0,void*),tr,"Find",1,a,&e);
  return !e&&live(marker)?call(ctrl_ui,marker,"get_gameObject",0,0,&e):0;
}
static int fire_interactable(void){
  if(!selectable_class)selectable_class=hatch_class("UnityEngine.UI","Selectable");
  if(!live(fire_selectable)){
    void *go=first(read_ref(ui,bound_hud,"fireBtnGos"));
    void *button=hatch_class("UnityEngine.UI","Button");
    fire_selectable=live(go)&&button?component(go,button):0;
  }
  return selectable_class&&live(fire_selectable)&&flag(selectable_class,fire_selectable,"get_interactable");
}
static void update_optics(void){
  if(bound!=23||!am_player_f||!owner||!live(bound_hud)||!live(bound_gc)||!live(bound_pc)||!live(bound_st))return;
  if(!live(aim_press))aim_press=resolve_press();
  if(!live(aim_press)||!flag(goc,aim_press,"get_activeSelf"))return;
  deactivate(aim_press); /* one press; never fight an intentional free-camera/air/ship selection */
  if(deadoff<16||AT(bound_st,deadoff,uint8_t)||scalar(timec,0,"get_timeScale")<=0)return;
  int display=number(ui,bound_hud,"get_CurrentDisplayMode",-1);
  if(display!=1&&display!=2)return; /* includes normal exit to third person */
  void *camera=read_ref(controller,bound_gc,"mCamCtrl");
  if(!live(camera))return;
  void *cc=AT(camera,0,void*);int mode=field(cc,"viewMode");
  if(mode<16||AT(camera,mode,int)!=0)return;
  void *turret=read_ref(ctrl_pc,bound_pc,"turretTrf");
  int e=0;
  if(!live(turret))return;
  if(read_ref(cc,camera,"_playerTurretTrf")!=turret || read_ref(cc,camera,"_targetTrf")!=turret){
    void *p[]={turret};call(cc,camera,"set_PlayerTurretTrf",1,p,&e);if(e)return;
  }
  /* At the initial 1x setting the stock aim button enters display 1 (commander);
     mode 2 is the first actual gunner optic. Use the stock zoom switch, which
     updates the zoom text, reticle, FOV and input together. Preserve selected
     higher magnifications and never cycle the binocular button a second time. */
  if(display!=1||number(cc,camera,"get_CurrentZoomIndex",-1)!=0)return;
  void *scales=read_ref(cc,camera,"zoomScaleFactor");
  if(!scales)return;
  uintptr_t n=AT(scales,24,uintptr_t);if(n<2||n>32)return;
  float initial=AT(scales,32,float),next=AT(scales,36,float);
  if(!isfinite(initial)||!isfinite(next)||initial<=0||next<=initial)return;
  int limit=field(uStatus,"maxZoomScaleNum");
  if(limit<16)return;
  /* Older baked player templates initialize the per-tank limit to zero.
     Only unlock a detent that actually exists on this stock camera. */
  if(AT(bound_st,limit,int)<1)AT(bound_st,limit,int)=1;
  call(ui,bound_hud,"SwitchZoomScale",0,0,&e);
}
