#pragma once
static int live(void *o){return o&&AT(o,16,void*);}
static int number(void *c,void *o,const char *name,int bad){
  int e=0;void *v=call(c,o,name,0,0,&e);return v&&!e?AT(v,16,int):bad;
}
static int flag(void *c,void *o,const char *name){
  int e=0;void *v=call(c,o,name,0,0,&e);return v&&!e&&AT(v,16,uint8_t);
}
static float scalar(void *c,void *o,const char *name){
  int e=0;void *v=call(c,o,name,0,0,&e);return v&&!e?AT(v,16,float):NAN;
}
static int named(void *s,const char *name){
  size_t n=strlen(name);if(!s||AT(s,16,int)!=(int)n)return 0;
  for(size_t i=0;i<n;i++)if(AT(s,20+2*i,uint16_t)!=(unsigned char)name[i])return 0;
  return 1;
}
static void *read_ref(void *c,void *o,const char *name){
  if(!o||!c)return 0;
  int offset=field(c,name);return offset>=16?AT(o,offset,void*):0;
}
static void *first(void *arr){
  return arr && AT(arr,24,uintptr_t)>0 && AT(arr,24,uintptr_t)<=256 ? AT(arr,32,void*):0;
}
static void *stats_class,*ctrl_ui,*ctrl_pc,*ctrl_launcher,*ctrl_tm;
static int ui_stats=-1;
static void *stats(void *hud){
  if(!live(hud))return 0;
  if(ui_stats>=16){void *br=AT(hud,ui_stats,void*);if(live(br))return br;}
  int e=0;void *go=call(ctrl_ui,hud,"get_gameObject",0,0,&e);
  return e?0:component(go,stats_class);
}
