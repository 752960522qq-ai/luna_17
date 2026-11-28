/* A normal spawn is already a scene root. In an authored field the selected
   player may instead remain inside "Campaign Units". The cumulative projectile
   system uses Transform.root as its collision owner; preserve the tank's exact
   world pose and make only the selected live tank an independent root. */
static int owner_root_done;
static void update_owner_root(void){
  if(owner_root_done||(((bound!=22&&bound!=23)||(!am_player_f&&!am_t26))&&!storm_profile)||!owner||!live(bound_pc)||!live(bound_gc)||!live(bound_st))return;
  if(deadoff<16||AT(bound_st,deadoff,uint8_t))return;
  void *tr=read_ref(ctrl_pc,bound_pc,"thisTrf");int e=0;if(!live(tr))return;
  void *tc=AT(tr,0,void*),*root=call(tc,tr,"get_root",0,0,&e);if(e||!live(root))return;
  if(root==tr){owner_root_done=1;return;}
  void *name=call(obj,root,"get_name",0,0,&e);if(e||!name)return;
  if(!named(name,"Campaign Units")){owner_root_done=1;return;}
  void *go=call(controller,bound_gc,"get_PlayerGo",0,0,&e);
  if(e||!live(go)||!flag(goc,go,"get_activeInHierarchy")||read_ref(ctrl_pc,bound_pc,"uStatus")!=bound_st)return;
  if(call(goc,go,"get_transform",0,0,&e)!=tr||e)return;
  bool keep=true;void *p[]={0,&keep};
  call(tc,tr,"SetParent",2,p,&e);
  if(!e&&call(tc,tr,"get_root",0,0,&e)==tr&&!e)owner_root_done=1;
}
