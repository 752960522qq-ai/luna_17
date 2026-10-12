#include <assert.h>
#include <stdio.h>
#include "../native/experience_math.h"
#include "../native/artillery_aim.h"
int main(void){BteVec f={0,0,1},r={1,0,0};assert(bte_artillery_reachable((BteVec){0,.1f,1},f,r,5,75,5));assert(!bte_artillery_reachable((BteVec){1,0,1},f,r,5,75,5));assert(!bte_artillery_reachable((BteVec){0,-1,1},f,r,5,75,5));BteVec aim;float t;assert(bte_intercept((BteVec){0,0,300},(BteVec){0},240,9.81f,120,&aim,&t));BteVec end=bte_position((BteVec){0},bte_scale(aim,1/t),9.81f,t);assert(fabsf(end.z-300)<.01f&&fabsf(end.y)<.01f);puts("Artillery target solution and hull-relative traverse/elevation reachability passed");}
