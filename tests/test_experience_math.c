#include <assert.h>
#include <stdio.h>
#include "../native/experience_math.h"
static int near(float a,float b){return fabsf(a-b)<.0002f;}
int main(void){
    assert(bte_ground_sight(0,0)&&bte_ground_sight(0,1)&&bte_ground_sight(0,2));
    assert(!bte_ground_sight(0,3)&&!bte_ground_sight(0,-1)&&!bte_ground_sight(3,2));
    BteDamage ap=bte_damage(BTE_AP,96,100,.5f,45,20,10,155);
    assert(ap.penetrated && near(ap.effective_penetration,48));
    assert(near(ap.damage,20*(1+1.3f*(48.f/45-1))*(1+.25f*sqrtf(1.55f))));
    assert(!bte_damage(BTE_AP,96,100,.5f,49,20,10,155).penetrated);
    assert(bte_damage(BTE_AP,96,100,.5f,49,20,10,155).damage==0);
    BteDamage apcr=bte_damage(BTE_APCR,96,100,.5f,45,20,10,155);
    assert(!apcr.penetrated && near(apcr.effective_penetration,96*powf(.5f,1.4f)));
    BteDamage cap=bte_damage(BTE_APCR,1000,100,1,1,20,10,155);
    assert(near(cap.damage,23.1f)); // No filling boost, revised 1.65x cap.
    // AP/APCR/HEAT all scale only the surplus; threshold and over-cap
    // penetration are distinct cases. Compare against each shell's own base.
    const int weighted_shells[]={BTE_AP,BTE_APCR,BTE_HEAT};
    const float ratios[]={1.f,1.1f,1.2f,1.4f,1.5f,2.f};
    for(unsigned s=0;s<3;s++){
        BteDamage base=bte_damage(weighted_shells[s],100,100,1,100,20,10,100);
        for(unsigned r=0;r<6;r++){
            BteDamage revised=bte_damage(weighted_shells[s],100*ratios[r],100,1,100,20,10,100);
            float old_margin=fminf(1.5f,ratios[r]);
            assert(near(revised.damage/base.damage,1.f+1.3f*(old_margin-1.f)));
        }
        assert(bte_damage(weighted_shells[s],99,100,1,100,20,10,100).damage==0);
    }
    BteDamage he=bte_damage(BTE_HE,27,152,1,20,20,10,710);
    BteDamage blocked=bte_damage(BTE_HE,27,152,.5f,20,20,10,710);
    assert(he.penetrated && !blocked.penetrated && near(blocked.damage,he.damage*.10f));
    assert(near(he.damage,10*powf(7.1f,.6f)*sqrtf(1.52f)));
    assert(bte_damage(BTE_AP,96,100,-1,45,20,10,155).damage==0);
    assert(bte_damage(BTE_AP,NAN,100,1,45,20,10,155).damage==0);
    assert(bte_damage(BTE_WP,96,100,1,45,20,10,155).damage==0);
    assert(bte_damage(BTE_AP,96,100,.5f,45,20,10,0).damage < ap.damage);
    assert(bte_damage(BTE_HE,27,152,1,20,20,10,8300).damage > he.damage);
    assert(bte_damage(BTE_HE,27,152,1,20,20,10,0).damage==0);
    assert(bte_damage(BTE_HE,27,152,1,20,20,10,NAN).damage==0);
    assert(bte_damage(BTE_HEAT,200,150,1,100,20,10,2400).damage>bte_damage(BTE_HEAT,200,150,1,100,20,10,1200).damage);
    assert(bte_damage(BTE_HEAT,200,150,1,100,20,10,0).damage==0);
    assert(bte_damage(BTE_HEAT,200,150,1,201,20,10,2400).damage==0);
    BteMotion motion={0};BteVec measured;
    assert(!bte_motion_velocity(&motion,(BteVec){0},1,&measured));
    assert(bte_motion_velocity(&motion,(BteVec){0,0,9},1.1f,&measured));
    assert(fabsf(measured.z-90)<.001f);
    assert(!bte_motion_velocity(&motion,(BteVec){10000,0,0},1.2f,&measured));
    assert(!bte_motion_velocity(&motion,(BteVec){0},.5f,&measured));
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
