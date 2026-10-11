#pragma once

// Hatch geometry is exported in metres; the game's stock shells use a 0.23
// speed scale. Keep physical muzzle speed for metre-sized imported vehicles.
#define STOCK_SHELL_SPEED_SCALE .23f
#define HATCH_SHELL_GRAVITY 9.81f
typedef struct { void *info; float speed; } ShellProfile;
static ShellProfile shell_profiles[128];
static unsigned shell_profile_cursor;
static UpdateFn original_shell_fixed_update;
static void record_shell_profile(void *info,float speed) {
    if(!info)return;
    for(unsigned i=0;i<128;i++)if(shell_profiles[i].info==info)shell_profiles[i]=(ShellProfile){0};
    if(speed<=0)return;
    shell_profiles[shell_profile_cursor++%128]=(ShellProfile){info,speed};
}
static const ShellProfile *shell_profile(void *info) {
    if(!info)return 0;
    for(unsigned i=0;i<128;i++)if(shell_profiles[i].info==info)return &shell_profiles[i];
    return 0;
}
static void shell_fixed_update(void *shell,const void *mi) {
    void *info=P(shell,0x90);
    const ShellProfile *profile=shell_profile(info);
    int initialized=B(shell,0x9c);
    if(!profile){original_shell_fixed_update(shell,mi);crew_observe_shell(shell,initialized);return;}
    float speed=F(info,0x18),gravity=F(shell,0x7c);
    if(!B(shell,0x9c))F(info,0x18)=profile->speed/STOCK_SHELL_SPEED_SCALE;
    F(shell,0x7c)=HATCH_SHELL_GRAVITY;
    original_shell_fixed_update(shell,mi);
    F(info,0x18)=speed;
    // Shell pools may later serve stock-template shots. Do not leave physical
    // gravity on their shared component between updates or vehicle switches.
    F(shell,0x7c)=gravity;
    crew_observe_shell(shell,initialized);
}


// Stock ShellMove skips just one collider. Imported tanks retain several
// body/turret/info regions; ignore any region belonging to the firing tank.
static void (*original_shell_impact)(void *,void *,const void *);
static int shell_hits_owner(void *shell,void *collider) {
    if(!offline_mode()||!unity_exists(shell)||!unity_exists(collider))return 0;
    // AttackInfo.owner (+0x20) is a Transform, not UnitStatus.
    void *info=P(shell,0x90),*root=info?P(info,0x20):0;
    if(!unity_exists(root))return 0;
    void *go=hatch_call(root,"get_gameObject",0,0);
    void *owner=go?hatch_get_child_component(go,"","UnitStatus"):0;
    if(!unity_exists(owner)||!tank_config(owner))return 0;
    void *hit=hatch_weapon_mount(collider);
    return root && hit && (root==hit||hatch_belongs_to(hit,root));
}
static void shell_impact(void *shell,void *collider,const void *mi) {
    if(shell_hits_owner(shell,collider))return;
    original_shell_impact(shell,collider,mi);
}
