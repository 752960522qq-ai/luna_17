#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define F(o,n) (*(float *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
typedef struct {int value;} ObscuredInt;
static int plain_int(ObscuredInt value){return value.value;}
static int unity_exists(void *object){return object!=0;}
static void managed_store(void *object,int offset,void *value){P(object,offset)=value;}
static int mg_ready=1;
static int hatch_machine_gun_ready(void *pc){(void)pc;return mg_ready;}
#include "../native/weapon_readiness.h"
int main(void){
    _Alignas(16) uint8_t pc[256]={0},status[1024]={0},pool[128]={0},launcher[256]={0},game[32]={0},muzzle[32]={0},ammo[32]={0};
    P(pc,0x58)=pool;I(pool,0x18)=1;P(pool,0x20)=launcher;P(launcher,0x20)=muzzle;P(status,0xf0)=ammo;
    I(status,0x78)=0;I(status,0xa8)=280;
    assert(weapon_ready(pc,status,game));assert(I(launcher,0x50)==0&&F(launcher,0x54)==280);assert(P(launcher,0x38)==status&&P(launcher,0xb0)==game);
    I(status,0x78)=-1;assert(!weapon_ready(pc,status,game));I(status,0x78)=212;
    I(status,0xa8)=0;assert(!weapon_ready(pc,status,game));I(status,0xa8)=895;
    assert(weapon_ready(pc,status,game));P(launcher,0x20)=0;assert(!weapon_ready(pc,status,game));P(launcher,0x20)=muzzle;
    I(pool,0x18)=9;assert(!weapon_ready(pc,status,game));I(pool,0x18)=1;mg_ready=0;assert(!weapon_ready(pc,status,game));
    puts("Weapon readiness: Grille zero AP accepted; incomplete launchers rejected");
}
