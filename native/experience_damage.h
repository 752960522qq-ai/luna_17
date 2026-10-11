#pragma once
#include "experience_math.h"
static void *(*original_cal_damage)(void *,void *,void *,bool,const void *);
// SetDamage consumes byte-sized damage values; cap rather than wrap at 256.
static int bte_damage_byte(float value){return value<=0?0:value>=255?255:(int)lroundf(value);}
static void *experience_compute_damage(void *damage,void *info,void *part,bool bomb,const void *mi){
    int flags=__atomic_load_n(&experience_flags,__ATOMIC_ACQUIRE);
    const FillingProfile *filling=info?filling_profile(info):0;
    int enabled=(flags&2) && state==3 && offline_mode() && filling && filling->known;
    // Stock treats HE as a bomb and skips impact-normal calculation. Reuse
    // its cannon collision path for HE, then replace only the damage result.
    bool classify_bomb=bomb && !(enabled && info && I(info,0x4c)==BTE_HE);
    void *result=original_cal_damage(damage,info,part,classify_bomb,mi);
    if(!enabled || !result || I(result,0x18)!=4 || !info || !damage || classify_bomb)return result;
    int shell=I(info,0x4c),hit_part=I(info,0x44),area=I(damage,0x70),section=I(damage,0x74);
    // Only main cannon AP/HE/APCR/HEAT; mines/bombs/MG/smoke keep their path.
    if(shell<0 || shell>4 || shell==3 || (hit_part!=0 && hit_part!=1) || area<0 || area>3 || section<0)return result;
    void *status=P(damage,0x38);if(!unity_exists(status))return result;
    void *armor=P(status,hit_part?0x1c0:0x1b8);int count=armor?I(armor,0x18):0;
    if(count<4 || count>64 || count%4 || section>=count/4)return result;
    int thickness=I(armor,0x20+(area*(count/4)+section)*4);if(thickness<0)return result;
    // CalDamage returns grazing angle (90-theta), derived from its collider
    // raycast normal, not the gun's angle or the vehicle's forward direction.
    int grazing=I(result,0x28);if(grazing<0 || grazing>90)return result;
    float cosine=sinf(grazing*.017453292519943295f);
    // Unknown ammunition keeps the game's damage, rather than receiving a
    // fabricated global explosive charge. Zero filling is a valid config.
    if(!filling || !filling->known)return result;
    BteDamage value=bte_damage(shell,I(info,0x1c),I(info,0x50),cosine,thickness,experience_k,experience_khe,filling->grams);
    I(result,0x20)=bte_damage_byte(value.damage);
    // Penetration is a pass/fail gate. Do not turn damage into armor erosion.
    I(result,0x24)=0;
    if(!value.penetrated)I(result,0x2c)=0;
    return result;
}

static void *experience_cal_damage(void *damage,void *info,void *part,bool bomb,const void *mi){
 void *result=experience_compute_damage(damage,info,part,bomb,mi);
 crew_damage_result(damage,info,result);return result;
}
