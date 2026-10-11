// Execute production semantic observers against explicit battle state fixtures.
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <stdio.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
#define FIELD_UNITSTATUS_ISDESTROYED_K__BACKINGFIELD 0x206
#include "../native/experience_math.h"
typedef struct {float x,y,z;} Vec3;
typedef struct {Vec3 point;float distance;} EnemyHit;
typedef void (*UpdateFn)(void *,const void *);
static unsigned char player[1024],enemy[1024],game[1024],pc[1024],ui[1024],damage[512],result[64],shell[512],info[128],info2[128];
static void *player_status=player,*player_control=pc;
static int state=3,offline=1,stock_calls,scanning;
static unsigned char root_tr[512],enemy_tr[512],turret[768],enemy_air[1024],air_tr[512],enemy_list[48],air_list[48];
static unsigned long clock_time=10000;
static unsigned long now_ms(void){return clock_time;}
static int offline_mode(void){return offline;}
static int unity_exists(void *p){return p!=0;}
static bool enemy_friend(void *p,const void *m){(void)p;(void)m;return false;}
static void *fake_method[2],*destroy_method[2];
static bool destroyed(void *p,const void *m){(void)m;return B(p,0x206);}
static unsigned char transform_method[96];
static void *method(void *p,const char *n,int c){(void)p;(void)c;return !strcmp(n,"get_IsMyFriend")?fake_method:!strcmp(n,"get_IsDestroyed")?destroy_method:!strcmp(n,"get_transform")?(void *)transform_method:0;}
static int bte_field_offset(void *p,const char *n){(void)p;return !strcmp(n,"usingShell")?0x1e8:!strcmp(n,"<KillNum>k__BackingField")?0x100:-1;}
static Vec3 call_vec(void *p,const char *n){
 if(!p)return (Vec3){0};if(!strcmp(n,"get_forward"))return (Vec3){0,0,1};
 return *(Vec3 *)((char *)p+(!strcmp(n,"get_TargetPos")?0x200:0x100));
}
static void *hatch_class(const char *a,const char *b){(void)a;return scanning?(void *)b:0;}
static void *hatch_type_object(void *p){return p;}
static void *hatch_method(void *p,const char *n,int c,void *k){(void)p;(void)c;(void)k;return (void *)n;}
static void *enemy_invoke(void *m,void *p,void **args,int *error){
 *error=0;if(m==transform_method)return P(p,0x280);
 if(m&&!strcmp((char *)m,"FindObjectsOfType"))return !strcmp(args[0],"UnitStatus")?enemy_list:air_list;
 return 0;
}
static void utf8_name(void *p,char *s,size_t n){(void)p;if(n)s[0]=0;}
static BteVec bv(Vec3 p){return (BteVec){p.x,p.y,p.z};}
static int bte_cast(Vec3 a,Vec3 b,EnemyHit *h){(void)a;(void)b;(void)h;return 0;}
#include "../native/crew_voice.h"
static void radio(void *p,int event,const void *m){(void)p;(void)event;(void)m;stock_calls++;}
static void reset(void *p,const void *m){(void)m;B(p,0x9c)=0;}
static void event_is(int event){assert(crew_gate_take());assert(crew_event[0]==event);crew_gate_finish();}
int main(void){
 destroy_method[0]=destroyed;fake_method[0]=enemy_friend;crew_enabled=1;crew_event_mask=262143;original_radio_voice=radio;original_crew_shell_reset=reset;
 P(game,0x118)=player;P(pc,0x98)=ui;P(damage,0x38)=enemy;I(result,0x18)=4;
 crew_battle_update(game,2);event_is(0);
 crew_battle_update(game,3);assert(!crew_gate_take());
 crew_radio_voice(0,0,0);crew_radio_voice(0,10,0);crew_radio_voice(0,11,0);assert(!stock_calls&&!crew_gate_take());
 crew_record_shot(info,player,0);I(result,0x20)=10;crew_damage_result(damage,info,result);event_is(3);
 crew_damage_result(damage,info,result);assert(!crew_gate_take());
 crew_record_shot(info2,player,0);I(result,0x20)=9;crew_damage_result(damage,info2,result);event_is(7);
 // Outcomes during speech are discarded permanently, including misses.
 crew_trigger(4);crew_record_shot(info,player,0);crew_damage_result(damage,info,result);event_is(4);crew_damage_result(damage,info,result);assert(!crew_gate_take());
 crew_record_shot(info,player,0);P(shell,0x90)=info;B(shell,0x9c)=1;crew_shell_reset(shell,0);clock_time+=301;crew_player_update(pc);event_is(2);
 P(damage,0x38)=player;crew_damage_result(damage,info,result);event_is(4);
 I(ui,0x100)=1;crew_player_update(pc);event_is(6);crew_player_update(pc);assert(!crew_gate_take());
 I(player,0x1e8)=1;crew_player_update(pc);event_is(13);crew_player_update(pc);assert(!crew_gate_take());
 B(game,0x10c)=1;crew_battle_update(game,3);event_is(5);
 state=2;B(player,0x206)=1;B(game,0x10c)=0;crew_battle_update(game,2);assert(state==2&&!crew_gate_take());
 state=3;B(player,0x206)=0;scanning=1;P(pc,0x20)=root_tr;P(pc,0x50)=turret;
 P(enemy,0x280)=enemy_tr;P(enemy_air,0x280)=air_tr;
 *(Vec3 *)(enemy_tr+0x100)=(Vec3){100,0,0};*(Vec3 *)(turret+0x200)=(Vec3){100,1,0};
 I(enemy_list,0x18)=1;P(enemy_list,0x20)=enemy;I(air_list,0x18)=0;
 crew_contact=0;clock_time+=1000;crew_acquire_target(pc,clock_time);assert(crew_gate_take());assert(crew_event[0]==17&&crew_event[1]==1&&crew_event[2]==3&&crew_event[3]==100);crew_gate_finish();
 clock_time+=300;crew_acquire_target(pc,clock_time);assert(!crew_gate_take());
 I(enemy_list,0x18)=0;I(air_list,0x18)=1;P(air_list,0x20)=enemy_air;
 *(Vec3 *)(air_tr+0x100)=(Vec3){0,1,450};*(Vec3 *)(turret+0x200)=(Vec3){0,1,450};
 clock_time+=300;crew_acquire_target(pc,clock_time);assert(crew_gate_take());assert(crew_event[0]==17&&crew_event[1]==2&&crew_event[2]==12&&crew_event[3]==450);crew_gate_finish();
 // Busy contact is consumed, not delayed until the voice gate releases.
 crew_trigger(4);I(air_list,0x18)=0;I(enemy_list,0x18)=1;*(Vec3 *)(turret+0x200)=(Vec3){100,1,0};
 clock_time+=300;crew_acquire_target(pc,clock_time);event_is(4);clock_time+=300;crew_acquire_target(pc,clock_time);assert(!crew_gate_take());
 // Directional outcomes use the nearest sampled approach to the locked target.
 crew_record_shot(info,player,0);CrewShot *shot=crew_shot(info);assert(shot->has_target);shot->closest=(BteVec){100,4,0};shot->closest_error=0;shot->finished=clock_time+1;
 clock_time+=10;crew_player_update(pc);event_is(8);
 scanning=0;
 offline=0;crew_radio_voice(0,10,0);assert(stock_calls==1);
 puts("Crew events: ready once, stock IDs suppressed, damage threshold 9/10, hit, kill, shell change, victory, delayed miss, busy drop, destroyed guard");
}
