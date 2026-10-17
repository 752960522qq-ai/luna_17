#pragma once
static int bte_ground_sight(int camera_mode,int sight_kind){return camera_mode==0 && sight_kind>=0 && sight_kind<=2;}
#include <math.h>

// Independent of the Unity adapter. All lengths and speeds use metres/seconds.
enum { BTE_AP, BTE_HE, BTE_APCR, BTE_WP, BTE_HEAT };
typedef struct { float effective_penetration, damage; int penetrated; } BteDamage;
static BteDamage bte_damage(int shell, float penetration, float caliber,
                            float normal_cosine, float armor, float k, float khe, float filling_grams) {
    BteDamage result = {0};
    if (shell < 0 || shell > 4 || shell == BTE_WP ||
        !isfinite(penetration) || penetration < 0 || !isfinite(caliber) || caliber <= 0 ||
        !isfinite(normal_cosine) || !isfinite(armor) || armor < 0 ||
        !isfinite(filling_grams) || filling_grams < 0 || filling_grams > 100000 ||
        !isfinite(k) || k <= 0 || !isfinite(khe) || khe <= 0) return result;
    float cosine = fmaxf(0, fminf(normal_cosine, 1));
    float exponent = shell == BTE_APCR ? 1.4f : shell == BTE_HEAT ? .8f : 1.f;
    result.effective_penetration = penetration * powf(cosine, exponent);
    result.penetrated = result.effective_penetration >= armor;
    if (shell == BTE_HE) {
        result.damage = khe * powf(filling_grams/100.f, .6f) * sqrtf(caliber/100.f) *
                        (result.penetrated ? 1.f : .10f);
    } else if (result.penetrated) {
        float margin = armor > 0 ? fminf(1.5f, fmaxf(1.f, result.effective_penetration/armor)) : 1.5f;
        // Increase only penetration's extra damage contribution by 30%.
        // A 1.20x margin becomes 1.26x; the old 1.50x cap becomes 1.65x.
        margin = 1.f + 1.3f * (margin - 1.f);
        float multiplier = shell == BTE_APCR ? .7f : shell == BTE_HEAT ? .8f : 1.f;
        result.damage = k * (caliber/100.f) * (caliber/100.f) * multiplier * margin;
        // AP filling is optional and belongs to this ammunition.
        if (shell == BTE_AP) result.damage *= 1.f + .25f * sqrtf(filling_grams/100.f);
        if (shell == BTE_HEAT) result.damage = khe * powf(filling_grams/100.f,.6f) * sqrtf(caliber/100.f) * .8f * margin;
    }
    return result;
}
typedef struct { float x,y,z; } BteVec;
static BteVec bte_add(BteVec a,BteVec b){return (BteVec){a.x+b.x,a.y+b.y,a.z+b.z};}
static BteVec bte_sub(BteVec a,BteVec b){return (BteVec){a.x-b.x,a.y-b.y,a.z-b.z};}
static BteVec bte_scale(BteVec a,float f){return (BteVec){a.x*f,a.y*f,a.z*f};}
static float bte_dot(BteVec a,BteVec b){return a.x*b.x+a.y*b.y+a.z*b.z;}
static BteVec bte_position(BteVec origin,BteVec velocity,float gravity,float time){
    BteVec p=bte_add(origin,bte_scale(velocity,time));p.y-=.5f*gravity*time*time;return p;
}
// Solve moving-target interception including gravity. A scanned bracket avoids
// Newton divergence for crossing/receding aircraft and reports unreachable shots.
static int bte_intercept(BteVec delta,BteVec target_velocity,float speed,float gravity,
                          float max_time,BteVec *aim,float *flight_time){
    if(!aim||!flight_time||!isfinite(speed)||speed<=0||!isfinite(gravity)||gravity<0||!isfinite(max_time)||max_time<=0||
       !isfinite(delta.x)||!isfinite(delta.y)||!isfinite(delta.z)||!isfinite(target_velocity.x)||!isfinite(target_velocity.y)||!isfinite(target_velocity.z)||bte_dot(delta,delta)<.0001f)return 0;
    float previous=0,previous_value=bte_dot(delta,delta);
    for(int i=1;i<=512;i++){
        float t=max_time*i/512.f;
        BteVec q=bte_add(delta,bte_scale(target_velocity,t));q.y+=.5f*gravity*t*t;
        float value=bte_dot(q,q)-speed*speed*t*t;
        if(previous_value>=0 && value<=0){
            float lo=previous,hi=t;
            for(int j=0;j<28;j++){
                float mid=(lo+hi)*.5f;BteVec p=bte_add(delta,bte_scale(target_velocity,mid));p.y+=.5f*gravity*mid*mid;
                if(bte_dot(p,p)>speed*speed*mid*mid)lo=mid;else hi=mid;
            }
            *flight_time=(lo+hi)*.5f;
            *aim=bte_add(delta,bte_scale(target_velocity,*flight_time));aim->y+=.5f*gravity*(*flight_time)*(*flight_time);
            return isfinite(aim->x)&&isfinite(aim->y)&&isfinite(aim->z);
        }
        previous=t;previous_value=value;
    }
    return 0;
}

// Scripted aircraft can move their Transform without any Rigidbody velocity.
typedef struct {BteVec position;float time;int valid;} BteMotion;
static int bte_motion_velocity(BteMotion *sample,BteVec position,float now,BteVec *velocity){
    if(!sample||!velocity||!isfinite(now)||!isfinite(position.x)||!isfinite(position.y)||!isfinite(position.z))return 0;
    float dt=now-sample->time;
    BteVec delta=bte_sub(position,sample->position);
    int usable=sample->valid && dt>.001f && dt<=.5f;
    *sample=(BteMotion){position,now,1};
    if(!usable)return 0;
    *velocity=bte_scale(delta,1/dt);
    // Scene changes and teleports must not produce an impossible lead marker.
    return bte_dot(*velocity,*velocity)<=1000.f*1000.f;
}
