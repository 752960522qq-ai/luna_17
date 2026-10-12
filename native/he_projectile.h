#pragma once
// HE BombMove uses a separate AttackInfo (+0x88) and direct callbacks.
static void (*original_he_collision)(void *,void *,const void *);
static void (*original_he_trigger)(void *,void *,const void *);
static void he_collision(void *bomb,void *collision,const void *mi){
 void *collider=hatch_call(collision,"get_collider",0,0);
 if(projectile_hits_owner(P(bomb,0x88),collider))return;
 crew_projectile_impact_observed(P(bomb,0x88));original_he_collision(bomb,collision,mi);
}
static void he_trigger(void *bomb,void *collider,const void *mi){
 if(projectile_hits_owner(P(bomb,0x88),collider))return;
 crew_projectile_impact_observed(P(bomb,0x88));original_he_trigger(bomb,collider,mi);
}
