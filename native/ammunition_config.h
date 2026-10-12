#pragma once
 #include "ammunition_identity.h"
// Explicit per-vehicle/per-shell overrides. Unset entries retain game damage.
typedef struct {char id[112];float grams[5];unsigned mask;} AmmunitionConfig;
static AmmunitionConfig ammunition_configs[512];
static unsigned ammunition_count;
static const AmmunitionConfig *ammunition_config(void *launcher,void *status){
    char id[112]={0},root_name[112]={0};
    if(status)utf8_name(P(status,0x68),id,sizeof(id));
    void *m=method(launcher,"get_transform",0);
    void *tr=m?((void *(*)(void *,const void *))P(m,0))(launcher,m):0;
    m=tr?method(tr,"get_root",0):0;void *root=m?((void *(*)(void *,const void *))P(m,0))(tr,m):0;
    m=root?method(root,"get_name",0):0;
    if(m)utf8_name(((void *(*)(void *,const void *))P(m,0))(root,m),root_name,sizeof(root_name));
    ammunition_normalize(id);ammunition_normalize(root_name);
    for(unsigned i=0;i<ammunition_count;i++){char key[112];snprintf(key,sizeof(key),"%s",ammunition_configs[i].id);ammunition_normalize(key);if(!strcmp(key,id))return &ammunition_configs[i];}
    // Mod vehicles inherit stock prefab names: preserve their own charge.
    if(tank_config(status))return 0;
    for(unsigned i=0;i<ammunition_count;i++){char key[112];snprintf(key,sizeof(key),"%s",ammunition_configs[i].id);ammunition_normalize(key);if(!strcmp(key,root_name))return &ammunition_configs[i];}
    return 0;
}
