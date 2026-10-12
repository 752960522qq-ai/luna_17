#pragma once
static int bte_hit_belongs_to(EnemyHit *hit,void *root){
 void *klass=hatch_class("UnityEngine","RaycastHit"),*get=klass?class_method(klass,"get_collider",0):0;
 void *collider=get?((void *(*)(EnemyHit *,const void *))P(get,0))(hit,get):0;
 void *tr=unity_exists(collider)?hatch_weapon_mount(collider):0;
 return unity_exists(tr)&&(tr==root||hatch_belongs_to(tr,root));
}
// Screen coordinates refer to the rendered overhead camera, after pose restore.
static int bte_screen_target(void *camera,float x,float y,Vec3 *target){
 int error=0;void *screen=hatch_class("UnityEngine","Screen");
 void *w=enemy_invoke(class_method(screen,"get_width",0),0,0,&error),*h=enemy_invoke(class_method(screen,"get_height",0),0,0,&error);
 if(error||!w||!h)return 0;
 Vec3 pixel={x*I(w,0x10),(1-y)*I(h,0x10),0};void *args[]={&pixel};
 void *boxed=enemy_invoke(method(camera,"ScreenPointToRay",1),camera,args,&error);
 if(error||!boxed)return 0;
 struct {Vec3 origin,direction;} ray;memcpy(&ray,(uint8_t *)boxed+0x10,sizeof(ray));
 EnemyHit hit={0};Vec3 end=uv(bte_add(bv(ray.origin),bte_scale(bv(ray.direction),5000)));
 if(!bte_cast(ray.origin,end,&hit))return 0;*target=hit.point;return 1;
}
