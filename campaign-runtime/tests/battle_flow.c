/* Host replay of the shipped Unity adapter. Managed objects and scene queries
   are substituted here; trigger, magazine, result and marker code are production. */
#include <stdint.h>
#include <assert.h>
#include <math.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include "../preview_steps.h"
#define AT(p,o,t) (*(t*)((char*)(p)+(o)))
typedef struct { void *slots[80]; } Obj;
static Obj G,H,S,BR,PC,T,LA,MNT,SH,SEED,POOL,SHOT[12],HELD,DOWN,UIROOT,CAM,CC,STR,INFO,ROOT,terrain,BOX,ANSWER,ENUMM,PARAMS,ID;
static void *obj=&BOX,*controller=&G,*ui=&H,*timec=&ID,*goc=&ROOT,*uStatus=&S,*lookup_m=&PARAMS,*intc=&ID;
static void *ctrl_pc=&PC,*ctrl_tm=&T,*ctrl_launcher=&LA,*stats_class=&BR;
static int ready=1,terminal=0,deadoff=37,boardoff=56,paused,held,down,accepted,requests,failed_shot;
static int win,lost,result_calls,gameover_calls,show,panels,origin_owner=7,shots[12],last_type=-1,simulatedAI,mg_calls;
static float clockval,unscaled,stock_next,start_cycle,yfloor=0;static int idword;
static void *expected_skip;
static int live(void *p){return p!=0;}
static void *find(const char *n){if(!strcmp(n,"Hatch F Trigger"))return &G;if(!strcmp(n,"Hatch F Held"))return held?&HELD:0;if(!strcmp(n,"Hatch F Down"))return down?&DOWN:0;return 0;}
static void deactivate(void *p){if(p==&DOWN)down=0;else if(p==&HELD)held=0;}
static int flag(void*c,void*p,const char*k){(void)c;
 if(!strcmp(k,"get_activeInHierarchy"))return p==&UIROOT&&show;
 if(!strcmp(k,"get_activeSelf")){for(int i=0;i<12;i++)if(p==&SHOT[i])return shots[i];return 0;}
 if(!strcmp(k,"get_IsGameClear"))return win;
 if(!strcmp(k,"get_IsGameOver"))return lost;
 if(!strcmp(k,"get_IsNowLoading"))return clockval+.00001f<stock_next;
 return 0;}
static int number(void*c,void*p,const char*k,int bad){(void)c;(void)p;
 if(!strcmp(k,"GetInstanceID"))return origin_owner;if(!strcmp(k,"get_FireNumByPlayer"))return accepted;
 if(!strcmp(k,"get_CurrentFndNum"))return 5;if(!strcmp(k,"get_CurrentSightType"))return 0;
 if(!strcmp(k,"get_width"))return 1000;if(!strcmp(k,"get_height"))return 500;return bad;}
static float scalar(void*c,void*p,const char*n){(void)c;(void)p;
 if(!strcmp(n,"get_timeScale"))return !paused;if(!strcmp(n,"get_LoadingStartTime"))return start_cycle;
 if(!strcmp(n,"get_unscaledTime"))return unscaled;if(!strcmp(n,"get_fixedDeltaTime"))return .02f;return clockval;}
static int field(void*c,const char*n){(void)c;
 if(!strcmp(n,"shellApGos"))return 48;if(!strcmp(n,"loadedShell"))return 128;
 if(!strcmp(n,"unitName"))return 40;
 if(!strcmp(n,"viewMode"))return 40;if(!strcmp(n,"thisTrf"))return 64;
 if(!strcmp(n,"initSpeed"))return 24;if(!strcmp(n,"hitLayerMask"))return 76;
 return -1;}
static int named(void*p,const char*n){return p==&STR&&!strcmp(n,"Panzer_II_Ausf_F");}
static void *first(void *p){return p?AT(p,32,void*):0;}
static void *read_ref(void*c,void*p,const char*n){(void)c;(void)p;
 if(!strcmp(n,"mResultGo"))return &UIROOT;if(!strcmp(n,"launchers"))return &G;
 if(!strcmp(n,"tMove"))return &T;if(!strcmp(n,"mCamCtrl"))return &CC;
 if(!strcmp(n,"myCamera"))return &CAM;if(!strcmp(n,"thisTrf"))return &ROOT;
 if(!strcmp(n,"fpTrf"))return &MNT;if(!strcmp(n,"shellApGos"))return &POOL;return 0;}
static void *component(void*g,void*c){(void)c;return g==&PC?&PC:&SH;}
static void *stats(void*h){(void)h;return &BR;}
static void *ha_string(const char*s){return (void*)s;}
static void *hatch_class(const char *ns,const char*n){(void)ns;return (void*)n;}
static void *hatch_type_object(void*c){return c;}
static void *ha_param_class(void*p){return p;}
static void *lookup(void*c,const char*n,int sz){(void)c;(void)sz;return !strcmp(n,"SetMissionResulet")?lookup_m:(void*)n;}
static void *call(void*c,void*self,const char*n,int k,void **a,int*e){(void)c;(void)self;(void)k;(void)e;
 if(!strcmp(n,"get_PlayerGo"))return &PC;
 if(!strcmp(n,"ButtonFire")){requests++;if(!failed_shot&&clockval>=stock_next){accepted++;start_cycle=clockval;stock_next=clockval+.395f;shots[accepted%12]=1;}return 0;}
 if(!strcmp(n,"GameOver")){gameover_calls++;lost=1;return 0;}
 if(!strcmp(n,"Parse")){assert(!strcmp(a[1],"Destroyed"));AT(&ANSWER,16,int)=2;return &ANSWER;}
 if(!strcmp(n,"GetShellAttackInfo")){last_type=*(int*)a[0];AT(&INFO,24,float)=last_type==2?75:40;return &INFO;}
 if(!strcmp(n,"get_position")){AT(&ANSWER,16,SceneVec)=(SceneVec){0,2,0};return &ANSWER;}
 if(!strcmp(n,"get_forward")){AT(&ANSWER,16,SceneVec)=(SceneVec){0,0,1};return &ANSWER;}
 if(!strcmp(n,"get_root"))return &UIROOT;
 if(!strcmp(n,"IsChildOf")){if(expected_skip)assert(a[0]==expected_skip);AT(&ANSWER,16,uint8_t)=self==&ROOT;return &ANSWER;}
 if(!strcmp(n,"WorldToScreenPoint")){SceneVec v=*(SceneVec*)a[0];AT(&ANSWER,16,SceneVec)=(SceneVec){400+v.z,275,1};return &ANSWER;}
 return 0;
}
static void *invoke(void*m,void*self,void**a,int*e){(void)self;(void)e;
 if(m==lookup_m){assert(*(int*)a[1]==5);result_calls++;show=1;return 0;}
 if(!strcmp((char*)m,"get_transform"))return &terrain;
 if(!strcmp((char*)m,"Linecast")){SceneVec p=*(SceneVec*)a[0],q=*(SceneVec*)a[1];bool hit=p.y>=yfloor&&q.y<yfloor;
   if(hit){float t=(p.y-yfloor)/(p.y-q.y);*(SceneVec*)a[2]=plus(p,dv(q,p),t);}
   AT(&ANSWER,16,uint8_t)=hit;return &ANSWER;}return 0;
}
#define JNIEXPORT
#define JNICALL
#define JNI_FALSE 0
#define JNI_TRUE 1
typedef void *jclass,*jfloatArray;
typedef int jboolean,jint;
typedef const struct J{int (*GetArrayLength)(void*,void*);void (*SetFloatArrayRegion)(void*,void*,int,int,float*);}*JNIEnv;
#include "../results.h"
#include "../player_cannon.h"
static void init(void){
 AT(&G,32,void*)=&LA;AT(&G,56,void*)=&H;AT(&S,40,void*)=&STR;AT(&LA,48,void*)=&POOL;AT(&LA,64,void*)=&MNT;
 AT(&POOL,24,uintptr_t)=12;for(int i=0;i<12;i++)AT(&POOL,32+sizeof(void*)*i,void*)=&SHOT[i];
 AT(&CC,0,void*)=&CC;AT(&INFO,0,void*)=&INFO;AT(&PARAMS,0x30,void*)=&ENUMM;AT(&ENUMM,0,void*)=&BOX;AT(&ENUMM,8,void*)=intc;
 fire_binding(23,0,&G,&S);assert(owner&&exclusive&&bound_gun==&LA);
}
static void frame(int cs,float *out){
 clockval=cs*.01f;unscaled=clockval;simulatedAI+=4;
 if(cs%11==0)memset(shots,0,sizeof(shots));
 update_cannon(out);
}
int main(void){
 (void)ready;(void)terminal;(void)idword;(void)panels;(void)mg_calls;(void)SEED;
 init();float o[7]={0};held=down=1;frame(0,o);frame(1,o);assert(accepted==1&&o[0]==9);
 for(int cs=2;cs<=365;cs++){down=cs%3==0;frame(cs,o);}
 assert(accepted==10&&o[0]==0&&o[1]>4.7f);
 int r=requests;
 for(int cs=366;cs<845;cs++){down=cs%2==0;frame(cs,o);}assert(requests==r&&accepted==10);
 frame(846,o);frame(847,o);assert(accepted==11&&o[0]==9);
 held=0;for(int cs=848;cs<1000;cs++)frame(cs,o);assert(accepted==11);
 failed_shot=1;down=1;frame(1000,o);frame(1001,o);assert(magazine.pending&&o[0]==9);
 for(int cs=1002;cs<=1110;cs++)frame(cs,o);assert(!magazine.pending&&o[0]==9);
 paused=1;held=down=1;frame(1111,o);assert(!held&&accepted==11);paused=0;failed_shot=0;
 printf("actual trigger adapter: hold across 10+1, rapid taps, denied shot, pause and active AI passed\n");
 assert(!result_step(22,&G,&H,0));assert(result_step(22,&G,&H,1)&&gameover_calls==1);for(int i=0;i<3;i++)result_step(22,&G,&H,1);assert(!result_calls);
 unscaled+=4;result_step(22,&G,&H,1);assert(result_calls==1&&show);unscaled+=10;result_step(22,&G,&H,1);assert(result_calls==1);
 origin_owner++;lost=show=0;assert(!result_step(23,&G,&H,0));win=1;assert(result_step(23,&G,&H,1));assert(finish.outcome==WON);
 show=1;unscaled+=5;result_step(23,&G,&H,0);assert(result_calls==1&&gameover_calls==1);
 printf("stock result handoff: death, win priority, UI grace, single presentation and retry passed\n");
 /* Where the new shell is selected but the old one is in the chamber, the
    production preview must keep using the old shell until loading completes. */
 expected_skip=&UIROOT;AT(&S,124,int)=2;AT(&S,128,int)=0;update_green(o,2,1);assert(o[2]==1&&last_type==0);float old=o[5];
 AT(&S,128,int)=2;update_green(o,2,1);assert(o[2]==1&&last_type==2&&o[5]>old*1.7f);
 float y=2,vy=0,z=0,prev=0;while(y>0){float yp=y;vy-=9.81f*.02f;y+=vy*.02f;prev=z;z+=75*.02f;if(y<=0)z=prev+(z-prev)*yp/(yp-y);}
 assert(fabsf(o[3]-(400+z)/1000)<.00001f);
 AT(&CC,40,int)=1;update_green(o,2,1);assert(!o[2]);
 printf("green dot: chambered AP/APCR, independent fixed-tick scene replay and camera exit passed\n");return 0;
}
