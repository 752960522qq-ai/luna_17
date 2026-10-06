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
    if(!profile){original_shell_fixed_update(shell,mi);return;}
    float speed=F(info,0x18);
    if(!B(shell,0x9c))F(info,0x18)=profile->speed/STOCK_SHELL_SPEED_SCALE;
    F(shell,0x7c)=HATCH_SHELL_GRAVITY;
    original_shell_fixed_update(shell,mi);
    F(info,0x18)=speed;
}
