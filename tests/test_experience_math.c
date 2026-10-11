#include <assert.h>
#include <stdio.h>
#include "../native/experience_math.h"
static int near(float a,float b){return fabsf(a-b)<.0002f;}
int main(void){
    BteDamage ap=bte_damage(BTE_AP,96,100,.5f,45,20,10);
    assert(ap.penetrated && near(ap.effective_penetration,48));
    assert(near(ap.damage,20*(48.f/45)*(1+.25f*sqrtf(1.55f))));
    assert(!bte_damage(BTE_AP,96,100,.5f,49,20,10).penetrated);
    assert(bte_damage(BTE_AP,96,100,.5f,49,20,10).damage==0);
    BteDamage apcr=bte_damage(BTE_APCR,96,100,.5f,45,20,10);
    assert(!apcr.penetrated && near(apcr.effective_penetration,96*powf(.5f,1.4f)));
    BteDamage cap=bte_damage(BTE_APCR,1000,100,1,1,20,10);
    assert(near(cap.damage,21)); // No filling boost, 1.5x penetration cap.
    BteDamage he=bte_damage(BTE_HE,27,152,1,20,20,10);
    BteDamage blocked=bte_damage(BTE_HE,27,152,.5f,20,20,10);
    assert(he.penetrated && !blocked.penetrated && near(blocked.damage,he.damage*.15f));
    assert(near(he.damage,10*powf(7.1f,.6f)*sqrtf(1.52f)));
    assert(bte_damage(BTE_AP,96,100,-1,45,20,10).damage==0);
    assert(bte_damage(BTE_AP,NAN,100,1,45,20,10).damage==0);
    assert(bte_damage(BTE_WP,96,100,1,45,20,10).damage==0);
    // Reconstruct both trajectories at the solution time, including drop.
    BteVec target={1000,100,0},velocity={0,0,90},aim;float time;
    assert(bte_intercept(target,velocity,850,9.81f,120,&aim,&time));
    BteVec launch=bte_scale(aim,850/sqrtf(bte_dot(aim,aim)));
    BteVec impact=bte_position((BteVec){0},launch,9.81f,time);
    BteVec expected=bte_add(target,bte_scale(velocity,time));
    assert(sqrtf(bte_dot(bte_sub(impact,expected),bte_sub(impact,expected)))<.001f);
    assert(!bte_intercept((BteVec){1000,0,0},(BteVec){1000,0,0},800,9.81f,120,&aim,&time));
    assert(!bte_intercept(target,velocity,0,9.81f,120,&aim,&time));
    assert(!bte_intercept(target,velocity,850,9.81f,INFINITY,&aim,&time));
    puts("Damage, obliquity, filling, HE shielding, interception and invalid-input checks passed");
}
