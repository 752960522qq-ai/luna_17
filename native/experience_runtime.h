#pragma once
// All Unity calls run in CameraControl.LateUpdate. Android exchanges only
// numeric snapshots/commands; it never dereferences Unity objects.
enum { BTE_SNAPSHOT_SIZE=28 };
static float bte_snapshot[BTE_SNAPSHOT_SIZE];
static volatile int bte_snapshot_lock, bte_command_lock;
static float bte_pan_x,bte_pan_y,bte_zoom,bte_tilt;
static int bte_next_mode,bte_target_pending;
static float bte_target_x,bte_target_y;
static Vec3 bte_target_world;
static int bte_target_valid,bte_target_reachable;
static int bte_mode,bte_fov_owned;
static void *bte_owner,*bte_camera;
static float bte_original_fov,bte_height=180.f,bte_pitch=65.f;
static Vec3 bte_center,bte_requested_aim,bte_requested_direction;
static Vec3 (*original_turret_target_dir)(void *,const void *);
static int bte_requested_aim_valid;
static unsigned long bte_last_prediction;
static float bte_cached_speed,bte_cached_gravity;
static int bte_cached_shell_ok;
static void bte_lock(volatile int *lock){while(__atomic_exchange_n(lock,1,__ATOMIC_ACQUIRE)){} }
static void bte_unlock(volatile int *lock){__atomic_store_n(lock,0,__ATOMIC_RELEASE);}
static void bte_publish(float *values){bte_lock(&bte_snapshot_lock);memcpy(bte_snapshot,values,sizeof(bte_snapshot));bte_unlock(&bte_snapshot_lock);}
static BteVec bv(Vec3 v){return (BteVec){v.x,v.y,v.z};}
static Vec3 uv(BteVec v){return (Vec3){v.x,v.y,v.z};}
static float bte_limit(float x,float lo,float hi){return fmaxf(lo,fminf(x,hi));}
static int bte_field_offset(void *object,const char *name){
    if(!object)return -1;void *iter=0,*field;
    while((field=class_fields(P(object,0),&iter)))if(!strcmp(P(field,0),name)){
        int offset=I(field,0x18);return offset>=0x10 && offset<0x1800?offset:-1;
    }
    return -1;
}
static float bte_float(void *object,const char *name){
    void *m=method(object,name,0);return m?((float (*)(void *,const void *))P(m,0))(object,m):0;
}
static void bte_set_float(void *object,const char *name,float value){
    void *m=method(object,name,1);if(m)((void (*)(void *,float,const void *))P(m,0))(object,value,m);
}
static int bte_project(void *camera,Vec3 world,float *out){
    int error=0;void *args[]={&world};
    void *value=enemy_invoke(method(camera,"WorldToScreenPoint",1),camera,args,&error);
    if(error || !value)return 0;
    Vec3 p;memcpy(&p,(uint8_t *)value+0x10,sizeof(p));
    if(!isfinite(p.x)||!isfinite(p.y)||!isfinite(p.z)||p.z<=0)return 0;
    void *screen=hatch_class("UnityEngine","Screen");
    void *w=screen?enemy_invoke(class_method(screen,"get_width",0),0,0,&error):0;
    void *h=screen?enemy_invoke(class_method(screen,"get_height",0),0,0,&error):0;
    if(error||!w||!h||I(w,0x10)<=0||I(h,0x10)<=0)return 0;
    out[0]=p.x/I(w,0x10);out[1]=1-p.y/I(h,0x10);return 1;
}
// Segment casts use the same default-layer mask as the base game, ignore
// trigger volumes, and advance past the player's own colliders.
static int bte_cast(Vec3 from,Vec3 to,EnemyHit *hit){
    BteVec delta=bte_sub(bv(to),bv(from));float remaining=sqrtf(bte_dot(delta,delta));
    if(!isfinite(remaining)||remaining<.001f)return 0;
    Vec3 direction=uv(bte_scale(delta,1/remaining));int error=0,mask=-5,triggers=1;
    static void *cast,*get;
    if(!cast){void *physics=hatch_class("UnityEngine","Physics");cast=physics?class_method(physics,"Raycast",6):0;}
    if(!get){void *klass=hatch_class("UnityEngine","RaycastHit");get=klass?class_method(klass,"get_collider",0):0;}
    if(!cast||!get)return 0;
    for(int i=0;i<12 && remaining>.001f;i++){
        void *args[]={&from,&direction,hit,&remaining,&mask,&triggers};
        void *answer=enemy_invoke(cast,0,args,&error);
        if(error||!answer||!B(answer,0x10))return 0;
        if(!isfinite(hit->distance)||hit->distance<0||hit->distance>remaining)return 0;
        void *collider=((void *(*)(EnemyHit *,const void *))P(get,0))(hit,get);
        if(!unity_exists(collider))return 0;
        if(!enemy_own_collider(collider,&error))return error?0:1;
        if(error)return 0;float step=hit->distance+.02f;
        from=uv(bte_add(bv(from),bte_scale(bv(direction),step)));remaining-=step;
    }return 0;
}
#include "target_geometry.h"
#include "artillery_aim.h"
static int bte_impact(Vec3 origin,Vec3 velocity,float gravity,Vec3 *point,float *time){
    Vec3 previous=origin;
    for(int i=1;i<=300;i++){
        float t=i*.4f;Vec3 next=uv(bte_position(bv(origin),bv(velocity),gravity,t));
        EnemyHit hit={0};if(bte_cast(previous,next,&hit)){
            *point=hit.point;*time=t-.4f+hit.distance/fmaxf(.001f,sqrtf(bte_dot(bte_sub(bv(next),bv(previous)),bte_sub(bv(next),bv(previous)))))*.4f;
            return 1;
        }
        if(bte_dot(bte_sub(bv(next),bv(origin)),bte_sub(bv(next),bv(origin)))>3000.f*3000.f || next.y<origin.y-1000.f)break;
        previous=next;
    }return 0;
}
static int bte_shell(void *pc,const CustomTank *config,float *speed,float *gravity){
    void *array=P(pc,0x58);int n=array?I(array,0x18):0;
    if(n<1||n>8)return 0;void *launcher=P(array,0x20);
    if(!unity_exists(launcher))return 0;
    int shell_offset=bte_field_offset(player_status,"usingShell");
    if(shell_offset<0)return 0;int shell=I(player_status,shell_offset);if(shell<0||shell>4)return 0;
    // Preview objects must not enter shell_profiles: 10 Hz previews would
    // evict still-flying artillery shots from the live projectile ring.
    void *info=original_attack_info(launcher,shell,0,0);if(!info)return 0;
    float physical=F(info,0x18),launcher_speed=F(launcher,0x54);
    if(config && launcher_speed>0)physical*=config->speed/launcher_speed;
    if(config && config->ballistics_profile==HATCH_BALLISTICS_PHYSICAL){*speed=physical;*gravity=9.81f;}
    else {
        *speed=physical*STOCK_SHELL_SPEED_SCALE;
        // Read the actual pooled cannon's gravity rather than guessing from
        // nominal muzzle speed. HE and AP use separate pools.
        int offset=bte_field_offset(launcher,shell==BTE_HE?"shellHeGos":"shellApGos");
        void *pool=offset>=0?P(launcher,offset):0;
        if(!pool||I(pool,0x18)<1||I(pool,0x18)>256)return 0;
        void *go=P(pool,0x20);if(!unity_exists(go))return 0;
        void *type=hatch_type_object(hatch_class("","ShellMove"));
        int error=0;void *args[]={type};
        void *component=type?enemy_invoke(hatch_method(P(go,0),"GetComponent",1,hatch_class("System","Type")),go,args,&error):0;
        if(error||!unity_exists(component))return 0;*gravity=F(component,0x7c);
    }
    return isfinite(*speed)&&*speed>0&&isfinite(*gravity)&&*gravity>0;
}
typedef struct {void *air,*transform;BteMotion motion;} BteAirMotion;
static BteAirMotion bte_air_motion[128];
static unsigned bte_air_motion_cursor;
static int bte_measured_velocity(void *air,void *transform,Vec3 position,float now,Vec3 *velocity){
    BteAirMotion *sample=0;
    for(int i=0;i<128;i++)if(bte_air_motion[i].air==air && bte_air_motion[i].transform==transform){sample=&bte_air_motion[i];break;}
    if(!sample){sample=&bte_air_motion[bte_air_motion_cursor++%128];*sample=(BteAirMotion){air,transform,{0}};}
    BteVec measured;
    if(!bte_motion_velocity(&sample->motion,bv(position),now,&measured))return 0;
    *velocity=uv(measured);return 1;
}
static void bte_restore(void){
    if(bte_fov_owned&&unity_exists(bte_camera)&&bte_original_fov>0)bte_set_float(bte_camera,"set_fieldOfView",bte_original_fov);
    memset(bte_air_motion,0,sizeof(bte_air_motion));bte_air_motion_cursor=0;
    bte_camera=0;bte_owner=0;bte_original_fov=0;bte_mode=0;bte_fov_owned=0;bte_requested_aim_valid=0;bte_target_valid=0;
}
static void bte_air_lead(void *camera,Vec3 origin,Vec3 forward,float speed,float gravity,float *values){
    // Aiming near a live enemy aircraft selects the closest angular target.
    // Measure Transform motion for scripted flight; Rigidbody is only a
    // first-sample fallback. Sample all live enemies, even outside the cone.
    void *klass=hatch_class("","AircraftControl"),*type=hatch_type_object(klass);
    void *object=hatch_class("UnityEngine","Object");int error=0;
    bool inactive=false;void *args[]={type,&inactive};
    void *all=type?enemy_invoke(hatch_method(object,"FindObjectsOfType",2,hatch_class("System","Type")),0,args,&error):0;
    int n=all?I(all,0x18):0;if(error||n<0||n>128)return;
    float now=FN(RVA_GAME_TIME,float (*)(const void *))(0);
    float best=.985f;BteVec aim={0};float flight=0;int found=0;
    for(int i=0;i<n;i++){
        void *air=P(all,0x20+i*8);if(!unity_exists(air))continue;
        void *status=0;int off=bte_field_offset(air,"airStatus");if(off>=0)status=P(air,off);
        if(!unity_exists(status))continue;
        // IsMyFriend is defined by the game's IFF rules, not by country alone.
        void *m=method(status,"get_IsMyFriend",0);if(!m||((bool (*)(void *,const void *))P(m,0))(status,m))continue;
        void *tr=enemy_invoke(method(air,"get_transform",0),air,0,&error);if(error||!unity_exists(tr))continue;
        Vec3 p=call_vec(tr,"get_position");
        Vec3 measured={0};int measured_ok=bte_measured_velocity(air,tr,p,now,&measured);
        BteVec delta=bte_sub(bv(p),bv(origin));float length=sqrtf(bte_dot(delta,delta));if(length<1||length>3000)continue;
        float cosine=bte_dot(bte_scale(delta,1/length),bv(forward));if(cosine<best)continue;
        off=bte_field_offset(air,"isShotDown");if(off>=0 && B(air,off))continue;
        off=bte_field_offset(air,"<IsErasing>k__BackingField");if(off>=0 && B(air,off))continue;
        off=bte_field_offset(air,"rgdbody");void *body=off>=0?P(air,off):0;
        Vec3 velocity=measured_ok?measured:unity_exists(body)?call_vec(body,"get_linearVelocity"):(Vec3){0};
        if(!measured_ok && !unity_exists(body))continue;
        if(!isfinite(velocity.x)||!isfinite(velocity.y)||!isfinite(velocity.z))continue;
        BteVec candidate;float t;
        if(bte_intercept(delta,bv(velocity),speed,gravity,120,&candidate,&t)){
            aim=candidate;flight=t;best=cosine;found=1;
        }
    }
    if(found && bte_project(camera,uv(bte_add(bv(origin),aim)),values+5)){values[4]=1;values[7]=flight;}
}
#include "artillery_scope.h"
static void experience_camera_prepare(void *control){
    void *ui=unity_exists(control)?P(control,0xe8):0;
    if(bte_camera && (!unity_exists(ui)||!bte_ground_sight(I(control,0x38),I(ui,0x2c))||state!=3||bte_owner!=player_status))bte_restore();
}
static void experience_turret_target(void *turret){
    if(bte_mode==2 && bte_requested_aim_valid && bte_owner==player_status && P(turret,0x40)==player_status && state==3 && offline_mode())
        set_vec(turret,"set_TargetPos",bte_requested_aim);
}
static Vec3 experience_turret_target_dir(void *turret,const void *mi){
    // The stock player path ignores TargetPos and returns Camera.TargetDir.
    // Override that direction at its source, keeping the stock gun motion,
    // traverse/elevation clamps and loading state machine intact.
    if(bte_mode==2 && bte_requested_aim_valid && bte_owner==player_status && P(turret,0x40)==player_status && state==3 && offline_mode())
        return bte_requested_direction;
    return original_turret_target_dir(turret,mi);
}
static void experience_camera_update(void *control){
    int flags=__atomic_load_n(&experience_flags,__ATOMIC_ACQUIRE);
    void *pc=player_control,*ui=unity_exists(control)?P(control,0xe8):0;
    void *camera=unity_exists(control)?P(control,0x28):0;
    int valid=flags && state==3 && offline_mode() && unity_exists(pc)&&unity_exists(player_status)&&unity_exists(ui)&&unity_exists(camera)&&bte_ground_sight(I(control,0x38),I(ui,0x2c));
    if(!valid){bte_restore();float empty[BTE_SNAPSHOT_SIZE]={0};bte_publish(empty);return;}
    const CustomTank *config=tank_config(player_status);
    int spg=(flags&4) && config && config->vehicle_kind==HATCH_VEHICLE_SPG;
    if(bte_owner!=player_status||bte_camera!=camera){bte_restore();bte_owner=player_status;bte_camera=camera;bte_original_fov=bte_float(camera,"get_fieldOfView");bte_last_prediction=0;}
    bte_lock(&bte_command_lock);
    bte_next_mode=0; // Original scope button owns mode selection.
    float dx=bte_pan_x,dy=bte_pan_y,zoom=bte_zoom;
    int tap=bte_target_pending;float tx=bte_target_x,ty=bte_target_y;bte_target_pending=0;
    bte_pan_x=bte_pan_y=bte_zoom=bte_tilt=0;bte_unlock(&bte_command_lock);
    int next=bte_scope_mode(control,ui,spg);
    if(next!=bte_mode){
        if(bte_fov_owned){
            // Stock ChangeCameraZoom may already have applied the next scope.
            void *change=method(control,"ChangeCameraZoom",1);bool scoped=B(control,0x78);
            void *args[]={&scoped};int error=0;
            if(change)enemy_invoke(change,control,args,&error);
            else bte_set_float(camera,"set_fieldOfView",bte_original_fov);
            bte_fov_owned=0;
        }
        bte_mode=next;bte_requested_aim_valid=0;bte_target_valid=0;bte_last_prediction=0;
        if(next==2){
            bte_original_fov=bte_float(camera,"get_fieldOfView");
            Vec3 root=call_vec(P(pc,0x20),"get_position"),forward=call_vec(P(pc,0x20),"get_forward");
            bte_center=uv(bte_add(bv(root),bte_scale(bv(forward),200)));
            bte_height=180;bte_pitch=65;
        }
    }
    if(next==2){bte_set_float(camera,"set_fieldOfView",60.f);bte_fov_owned=1;}
    void *launchers=P(pc,0x58);void *mount=P(pc,0x30);
    if(launchers && I(launchers,0x18)>=1 && I(launchers,0x18)<=8){
        void *launcher=P(launchers,0x20);int error=0;
        void *tr=enemy_invoke(method(launcher,"get_transform",0),launcher,0,&error);
        if(!error&&unity_exists(tr))mount=tr;
    }
    Vec3 origin=call_vec(mount,"get_position"),forward=call_vec(mount,"get_forward");
    unsigned long now=now_ms();int predict=now-bte_last_prediction>=100;
    if(predict)bte_cached_shell_ok=bte_shell(pc,config,&bte_cached_speed,&bte_cached_gravity);
    float speed=bte_cached_speed,gravity=bte_cached_gravity;int shell_ok=bte_cached_shell_ok;
    if(spg && bte_mode==2){
        bte_height=bte_limit(bte_height*expf(zoom),30,800);
        int error=0;void *screen=hatch_class("UnityEngine","Screen");
        void *w=enemy_invoke(class_method(screen,"get_width",0),0,0,&error),*h=enemy_invoke(class_method(screen,"get_height",0),0,0,&error);
        float aspect=w&&h&&I(h,0x10)>0?(float)I(w,0x10)/I(h,0x10):1;
        float span=2*bte_height*tanf(30.f*.01745329252f);
        bte_center.x-=dx*span*aspect;bte_center.z+=dy*span/sinf(bte_pitch*.01745329252f);
        Vec3 root=call_vec(P(pc,0x20),"get_position");BteVec delta=bte_sub(bv(bte_center),bv(root));delta.y=0;
        float dist=sqrtf(bte_dot(delta,delta));if(dist>3000){BteVec d=bte_scale(delta,3000/dist);bte_center.x=root.x+d.x;bte_center.z=root.z+d.z;}
        EnemyHit ground={0};Vec3 high=bte_center,low=bte_center;high.y=root.y+1000;low.y=root.y-1000;
        if(bte_cast(high,low,&ground))bte_center.y=ground.point.y;
        void *transform=P(control,0x20);float pitch=bte_pitch*.01745329252f;
        Vec3 position=bte_center;position.y+=bte_height;position.z-=bte_height/tanf(pitch);
        set_vec(transform,"set_position",position);
        void *m=method(transform,"set_rotation",1);Quat rotation={sinf(pitch*.5f),0,0,cosf(pitch*.5f)};
        if(m)((void (*)(void *,Quat,const void *))P(m,0))(transform,rotation,m);
        if(tap){Vec3 target;if(bte_screen_target(camera,tx,ty,&target)){bte_target_world=target;bte_target_valid=1;}}
        BteVec aim;float time;bte_requested_aim_valid=0;bte_target_reachable=0;
        if(bte_target_valid&&shell_ok&&bte_intercept(bte_sub(bv(bte_target_world),bv(origin)),(BteVec){0},speed,gravity,120,&aim,&time)){
            bte_requested_aim=uv(bte_add(bv(origin),aim));bte_requested_direction=uv(bte_scale(aim,1/sqrtf(bte_dot(aim,aim))));bte_requested_aim_valid=1;
            bte_target_reachable=bte_artillery_reachable(bv(bte_requested_direction),bv(call_vec(P(pc,0x20),"get_forward")),bv(call_vec(P(pc,0x20),"get_right")),config->traverse_half_angle,config->elevation,config->depression);
            set_vec(P(pc,0x50),"set_TargetPos",bte_requested_aim);
        }else if(!bte_target_valid){bte_requested_direction=forward;bte_requested_aim=uv(bte_add(bv(origin),bte_scale(bv(forward),1000)));bte_requested_aim_valid=1;}

    }else if(spg&&bte_mode==1){
        bte_requested_aim_valid=0;
        // First sight follows the current barrel in world space, including
        // suspension pitch/roll. No snapshot of spawn rotation is retained.
        void *transform=P(control,0x20);set_vec(transform,"set_position",origin);
        void *m=method(transform,"set_rotation",1);Quat q=FN(RVA_343DE40,Quat (*)(void *,const void *))(P(pc,0x30),0);
        if(m)((void (*)(void *,Quat,const void *))P(m,0))(transform,q,m);
    }
    if(!predict)return;bte_last_prediction=now;
    float values[BTE_SNAPSHOT_SIZE]={0};values[0]=1;values[8]=spg;values[9]=bte_mode;values[18]=bte_pitch;
    if(shell_ok){
        Vec3 point;float flight;
        if((flags&1) && bte_impact(origin,uv(bte_scale(bv(forward),speed)),gravity,&point,&flight)&&bte_project(camera,point,values+2)){
            values[1]=1;values[10]=sqrtf(bte_dot(bte_sub(bv(point),bv(origin)),bte_sub(bv(point),bv(origin))));values[11]=flight;
            float error=bte_float(P(pc,0x50),"get_GunErrorAngle");
            float radius=values[10]*tanf(bte_limit(error,0,15)*.01745329252f);values[12]=radius;
            Vec3 edge=point;edge.x+=radius;float projected[2];if(bte_project(camera,edge,projected))values[13]=fabsf(projected[0]-values[2]);
            edge=point;edge.z+=radius;if(bte_project(camera,edge,projected))values[14]=fabsf(projected[1]-values[3]);
        }
        if(flags&1)bte_air_lead(camera,origin,forward,speed,gravity,values);
        float elevation=config?fminf(45,config->elevation):45;
        values[15]=fminf(3000,speed*speed*sinf(elevation*.03490658504f)/gravity);
        Vec3 root=call_vec(P(pc,0x20),"get_position");bte_project(camera,root,values+16);
        Vec3 edge=root;edge.x+=values[15];float projected[2];if(bte_project(camera,edge,projected))values[19]=fabsf(projected[0]-values[16]);
        edge=root;edge.z+=values[15];if(bte_project(camera,edge,projected))values[20]=fabsf(projected[1]-values[17]);
    }
    values[21]=shell_ok;
    if(bte_target_valid&&bte_project(camera,bte_target_world,values+22)){values[24]=1;values[25]=bte_target_reachable;}
    bte_publish(values);
}
