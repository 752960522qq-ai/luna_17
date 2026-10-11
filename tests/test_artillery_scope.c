#include <assert.h>
#include <stdint.h>
#include <math.h>
#include <stdio.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define F(o,n) (*(float *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
static int unity_exists(void *p){return p!=0;}
#include "../native/artillery_scope.h"
int main(void){
 unsigned char camera[256]={0},ui[256]={0},scales[64]={0};P(camera,0x40)=scales;I(scales,0x18)=3;F(scales,0x20)=1;F(scales,0x24)=2.5;F(scales,0x28)=5;I(ui,0x30)=2;B(camera,0x78)=1;
 assert(bte_scope_mode(camera,ui,1)==0);I(camera,0x88)=1;assert(bte_scope_mode(camera,ui,1)==1);I(camera,0x88)=2;assert(bte_scope_mode(camera,ui,1)==2);
 assert(bte_scope_mode(camera,ui,0)==0);I(ui,0x30)=0;assert(bte_scope_mode(camera,ui,1)==0);I(ui,0x30)=2;
 B(camera,0x78)=0;assert(bte_scope_mode(camera,ui,1)==0);B(camera,0x78)=1;I(camera,0x88)=3;assert(bte_scope_mode(camera,ui,1)==0);
 // Locate scale, not a hard-coded index; other scopes/arrays must remain normal.
 I(camera,0x88)=0;F(scales,0x20)=5;assert(bte_scope_mode(camera,ui,1)==2);F(scales,0x20)=10;assert(bte_scope_mode(camera,ui,1)==0);
 puts("Original 5x scope enters artillery view; 2.5x stays flat, other tanks/modes unaffected");
}
