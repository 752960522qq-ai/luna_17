#pragma once
typedef struct {void *info,*root;} ProjectileOwner;
static ProjectileOwner projectile_owners[512];static unsigned projectile_owner_cursor;
static void record_projectile_owner(void *info,void *root){
 if(!info)return;ProjectileOwner *slot=0;
 for(int i=0;i<512;i++)if(projectile_owners[i].info==info){slot=projectile_owners+i;break;}
 if(!slot)slot=projectile_owners+projectile_owner_cursor++%512;
 *slot=(ProjectileOwner){info,root};
}
static void *projectile_owner(void *info){if(!info)return 0;for(int i=0;i<512;i++)if(projectile_owners[i].info==info)return projectile_owners[i].root;return 0;}
static int projectile_hits_owner(void *info,void *collider){
 if(!offline_mode()||!unity_exists(collider))return 0;
 void *root=projectile_owner(info);if(!unity_exists(root))return 0;
 void *hit=hatch_weapon_mount(collider);return unity_exists(hit)&&(root==hit||hatch_belongs_to(hit,root));
}
