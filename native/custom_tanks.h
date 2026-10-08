#pragma once
// Generated from validated project parameters. Never reuse with other resources.
typedef struct { const char *id; int penetration,caliber,speed,reload; float reload_offset; int power,max_speed; float reverse_speed; int turret_speed; float weight; int elevation,depression,crew,tier; int body_armor[4],turret_armor[4],ammo[5],mg_ammo,shell_penetration[5],wheel_count; float travel,rest,spring,damper,radius,track_length; int magazine_capacity; float shot_interval,magazine_reload; int ballistics_profile; float turret_speed_exact; int vehicle_kind, traverse_half_angle; } CustomTank;
static const CustomTank custom_tanks[]={{"T54_1949",212,100,895,10,-0.3000000000000007,520,56,2.2222222222222223,7,35.5,17,4,4,4,{120,80,80,45},{240,125,125,50},{16,10,6,0,2},30,{212,0,216,0,330},10,0.24,0.12,290213.0,18000.0,0.41200868785381317,5.58}};
#define CUSTOM_TANK_COUNT 1


