#pragma once
// 5.1.0 embedding API bindings identified from this game's ARM64 instructions.
static void *(*ha_domain)(void);
static const void **(*ha_assemblies)(void *,size_t *);
static void *(*ha_image)(const void *);
static void *(*ha_class)(void *,const char *,const char *);
static void *(*ha_new)(void *);
static void *(*ha_array)(void *,uintptr_t);
static void *(*ha_string)(const char *);
static void *(*ha_invoke)(void *,void *,void **,void **);
static void *(*ha_methods)(void *,void **);
static void *(*ha_type)(void *);
static void *(*ha_param_class)(void *);
static void *(*ha_reflect_type)(void *);
static int hatch_engine_ok,hatch_engine_error;
static int hatch_bind(void *lib){
#define HB(var,symbol) do{*(void **)(&(var))=dlsym(lib,symbol);if(!(var))return 0;}while(0)
 HB(ha_domain,"UfzMkOtv_Gn");HB(ha_assemblies,"rVAuNLFRLxv");HB(ha_image,"x_LrKbbfHVP");HB(ha_class,"DUNcvDcUAAe");
 HB(ha_new,"TgBaGbDucCp");HB(ha_array,"GUsixcHyL_y");HB(ha_string,"bmILtizhYMG");HB(ha_invoke,"kLtgigZNfGj");
 HB(ha_methods,"OSUIuUEDvmO");HB(ha_type,"oJVzeZIBbVs");HB(ha_param_class,"ugvIuXSfdRU");HB(ha_reflect_type,"Ehq_kQowKHa");
#undef HB
 hatch_engine_ok=1;return 1;
}
static void *hatch_class(const char *ns,const char *name){
 if(!hatch_engine_ok)return 0;size_t count=0;const void **assemblies=ha_assemblies(ha_domain(),&count);if(!assemblies||count>2048)return 0;
 for(size_t i=0;i<count;i++){void *c=ha_class(ha_image(assemblies[i]),ns,name);if(c)return c;}return 0;
}
static void *hatch_type_object(void *klass){return klass?ha_reflect_type(ha_type(klass)):0;}
static void *hatch_method(void *klass,const char *name,int count,void *first_class){
 if(!klass)return 0;if(!first_class)return class_method(klass,name,count);void *iter=0,*m;
 while((m=ha_methods(klass,&iter))){
  if(!strcmp((const char *)P(m,0x18),name) && B(m,0x52)==count){const void **params=P(m,0x30);if(params && ha_param_class((void *)params[0])==first_class)return m;}
 }return 0;
}
static void *hatch_call_class(void *klass,void *object,const char *name,int count,void **args,void *first_class){
 if(hatch_engine_error)return 0;void *m=hatch_method(klass,name,count,first_class);
 if(!m){hatch_engine_error=1;snprintf(hatch_error,sizeof(hatch_error),"Unity method unavailable: %s",name);return 0;}
 void *exception=0;void *result=ha_invoke(m,object,args,&exception);
 if(exception){hatch_engine_error=1;snprintf(hatch_error,sizeof(hatch_error),"Unity exception calling %s",name);}return result;
}
static void *hatch_call(void *o,const char *name,int n,void **a){if(!o){hatch_engine_error=1;hatch_fail("Unity object missing");return 0;}return hatch_call_class(P(o,0),o,name,n,a,0);}
static void hatch_set(void *o,const char *name,void *v){void *a[]={v};hatch_call(o,name,1,a);}
static void *hatch_component(void *go,void *klass){void *type=hatch_type_object(klass);void *a[]={type};return type?hatch_call_class(P(go,0),go,"AddComponent",1,a,hatch_class("System","Type")):0;}
static void *hatch_get_child_component(void *go,const char *ns,const char *name){void *type=hatch_type_object(hatch_class(ns,name));bool inactive=true;void *a[]={type,&inactive};return type?hatch_call(go,"GetComponentInChildren",2,a):0;}
static void *hatch_all(void *go,void *klass){void *type=hatch_type_object(klass);bool inactive=true;void *a[]={type,&inactive};return type?hatch_call(go,"GetComponentsInChildren",2,a):0;}
static void hatch_field(void *o,const char *name,void *value){
 if(!o){hatch_engine_error=1;return;}void *iter=0,*f;while((f=class_fields(P(o,0),&iter)))if(!strcmp((const char *)P(f,0),name)){int offset=I(f,0x18);if(offset>=0x10 && offset<0x1800){managed_store(o,offset,value);return;}}
 hatch_engine_error=1;snprintf(hatch_error,sizeof(hatch_error),"Game field unavailable: %s",name);
}
static void *hatch_new(void *klass,int count,void **args,void *first_class){if(!klass){hatch_engine_error=1;hatch_fail("Unity class missing");return 0;}void *o=ha_new(klass);if(!o){hatch_engine_error=1;return 0;}hatch_call_class(klass,o,".ctor",count,args,first_class);return o;}
static void *hatch_array_copy(void *klass,const void *data,uint32_t count,size_t size){void *a=ha_array(klass,count);if(!a){hatch_engine_error=1;return 0;}if(data && count)memcpy((unsigned char *)a+0x20,data,(size_t)count*size);return a;}
static void hatch_parent(void *tr,void *parent,const float *pos,const float *rot,const float *scale){hatch_set(tr,"set_parent",parent);hatch_set(tr,"set_localPosition",(void *)pos);hatch_set(tr,"set_localRotation",(void *)rot);hatch_set(tr,"set_localScale",(void *)scale);}
static void hatch_model_point(void *root,void *tr,const float *model,float *local){
 float p[3]={model[0],model[1],-model[2]};void *a[]={p};void *world=hatch_call(root,"TransformPoint",1,a);
 if(!world)return;void *b[]={(unsigned char *)world+0x10};void *result=hatch_call(tr,"InverseTransformPoint",1,b);
 if(result)memcpy(local,(unsigned char *)result+0x10,12);
}
static void *hatch_objects[2048],*hatch_transforms[2048];
static void *hatch_texture_objects[128];
static int hatch_apply_tank(HatchTank *t,void *go,void *pc,void *status){
 if(!hatch_engine_ok)return hatch_fail("Hatch embedding API not ready");hatch_engine_error=0;
 void *gameobject=hatch_class("UnityEngine","GameObject"),*meshklass=hatch_class("UnityEngine","Mesh"),*textureklass=hatch_class("UnityEngine","Texture2D"),*materialklass=hatch_class("UnityEngine","Material"),*rendererklass=hatch_class("UnityEngine","Renderer"),*meshfilterklass=hatch_class("UnityEngine","MeshFilter"),*meshrendererklass=hatch_class("UnityEngine","MeshRenderer"),*imageklass=hatch_class("UnityEngine","ImageConversion"),*vector3=hatch_class("UnityEngine","Vector3"),*vector2=hatch_class("UnityEngine","Vector2"),*intklass=hatch_class("System","Int32"),*byteklass=hatch_class("System","Byte"),*stringklass=hatch_class("System","String"),*transformklass=hatch_class("UnityEngine","Transform");
 if(!gameobject||!meshklass||!textureklass||!materialklass||!rendererklass||!meshfilterklass||!meshrendererklass||!imageklass||!vector3||!vector2||!intklass||!byteklass||!stringklass||!transformklass)return hatch_fail("Required runtime class was stripped");
 void *root=hatch_call(go,"get_transform",0,0),*old_renderers=hatch_all(go,rendererklass),*source_material=0;
 if(!old_renderers || I(old_renderers,0x18)<=0 || I(old_renderers,0x18)>1024)return hatch_fail("T34 renderer template missing");
 for(int i=0;i<I(old_renderers,0x18);i++){void *renderer=P(old_renderers,0x20+i*8);if(!source_material)source_material=hatch_call(renderer,"get_sharedMaterial",0,0);bool no=false;hatch_set(renderer,"set_enabled",&no);}
 if(!source_material || hatch_engine_error)return 0;
 // Strong managed arrays keep all temporary Unity wrappers rooted during allocations.
 void *volatile texture_roots=ha_array(textureklass,t->image_count),*volatile object_roots=ha_array(gameobject,t->node_count);if(!texture_roots||!object_roots)return hatch_fail("Cannot allocate model roots");
 for(uint32_t i=0;i<t->image_count && !hatch_engine_error;i++){
  int size=2;void *a[]={&size,&size};void *texture=hatch_new(textureklass,2,a,intklass),*data=hatch_array_copy(byteklass,t->images[i].bytes,t->images[i].size,1);bool no=false;void *load[]={texture,data,&no};void *ok=hatch_call_class(imageklass,0,"LoadImage",3,load,textureklass);
  if(!ok || !B(ok,0x10)){hatch_engine_error=1;hatch_fail("Texture decode failed");}hatch_texture_objects[i]=texture;managed_store(texture_roots,0x20+i*8,texture);
 }
 for(uint32_t i=0;i<t->node_count && !hatch_engine_error;i++){
  void *s=ha_string(t->nodes[i].disk->name);void *a[]={s};void *obj=hatch_new(gameobject,1,a,stringklass);hatch_objects[i]=obj;managed_store(object_roots,0x20+i*8,obj);hatch_transforms[i]=hatch_call(obj,"get_transform",0,0);
 }
 void *turret=0,*gun=0,*recoil=0;int gun_index=-1,recoil_index=-1;
 for(uint32_t i=0;i<t->node_count && !hatch_engine_error;i++){
  const HatchDiskNode *n=t->nodes[i].disk;hatch_parent(hatch_transforms[i],n->parent<0?root:hatch_transforms[n->parent],n->pos,n->rot,n->scale);
  if(n->flags&2)turret=hatch_transforms[i];if(n->flags&4){gun=hatch_transforms[i];gun_index=(int)i;}if(n->flags&8){recoil=hatch_transforms[i];recoil_index=(int)i;}
  if(!n->vertices)continue;const float *v=t->nodes[i].vertices;float *positions=malloc(n->vertices*12),*normals=malloc(n->vertices*12),*uv=malloc(n->vertices*8);
  if(!positions||!normals||!uv){free(positions);free(normals);free(uv);return hatch_fail("Insufficient mesh memory");}
  for(uint32_t j=0;j<n->vertices;j++){memcpy(positions+j*3,v+j*8,12);memcpy(normals+j*3,v+j*8+3,12);memcpy(uv+j*2,v+j*8+6,8);}
  void *mesh=hatch_new(meshklass,0,0,0);int index_format=1;hatch_set(mesh,"set_indexFormat",&index_format);
  void *posarr=hatch_array_copy(vector3,positions,n->vertices,12),*normarr=hatch_array_copy(vector3,normals,n->vertices,12),*uvarr=hatch_array_copy(vector2,uv,n->vertices,8),*idxarr=hatch_array_copy(intklass,t->nodes[i].indices,n->indices,4);
  free(positions);free(normals);free(uv);hatch_set(mesh,"set_vertices",posarr);hatch_set(mesh,"set_normals",normarr);hatch_set(mesh,"set_uv",uvarr);hatch_set(mesh,"set_triangles",idxarr);hatch_call(mesh,"RecalculateBounds",0,0);
  void *filter=hatch_component(hatch_objects[i],meshfilterklass);hatch_set(filter,"set_sharedMesh",mesh);
  void *renderer=hatch_component(hatch_objects[i],meshrendererklass);void *ma[]={source_material};void *mat=hatch_new(materialklass,1,ma,materialklass);hatch_set(mat,"set_color",(void *)n->factor);
  if(n->color>=0)hatch_set(mat,"set_mainTexture",hatch_texture_objects[n->color]);
  if(n->normal>=0){void *ta[]={ha_string("_BumpMap"),hatch_texture_objects[n->normal]};hatch_call_class(materialklass,mat,"SetTexture",2,ta,stringklass);}
  hatch_set(renderer,"set_sharedMaterial",mat);
 }
 if(hatch_engine_error||!turret||!gun||!recoil)return 0;
 void *old_turret=P(pc,0x28),*old_gun=P(pc,0x30);float zero[3]={0},identity[4]={0,0,0,1},one[3]={1,1,1};
 if(old_turret)hatch_parent(old_turret,turret,zero,identity,one);
 if(old_gun)hatch_parent(old_gun,gun,zero,identity,one);
 managed_store(pc,0x28,turret);managed_store(pc,0x30,gun);
 void *tm=hatch_get_child_component(go,"","TurretMove"),*body=hatch_get_child_component(go,"","BodyMove");
 if(!tm||!body||hatch_engine_error)return hatch_fail("T34 control components missing");
 hatch_field(tm,"thisTrf",turret);void *guns=ha_array(transformklass,1);managed_store(guns,0x20,gun);hatch_field(tm,"gunTrfs",guns);
 void *wheels=ha_array(transformklass,t->config.wheel_count),*susp=ha_array(transformklass,t->config.wheel_count);int wi=0;
 for(int side=0;side<2;side++)for(uint32_t i=0;i<t->node_count;i++)if((t->nodes[i].disk->flags&16) && (t->nodes[i].disk->flags&(side?256:128))){
  managed_store(wheels,0x20+wi*8,hatch_transforms[i]);int parent=t->nodes[i].disk->parent;managed_store(susp,0x20+wi*8,parent>=0&&(t->nodes[parent].disk->flags&32)?hatch_transforms[parent]:hatch_transforms[i]);wi++;
 }
 hatch_field(body,"largeWheelLodTrfs",wheels);hatch_field(body,"susWheelTrfs",susp);void *empty=ha_array(transformklass,0);hatch_field(body,"partsTransforms",empty);hatch_field(body,"smallWheelLodTrfs",empty);
 I(body,0x68)=1;F(body,0x88)=t->config.rest;F(body,0xa8)=1;I(body,0xac)=1;I(body,0xb0)=t->config.wheel_count/2;
 void *small=ha_array(transformklass,64);int small_count=0;
 for(int side=0;side<2;side++)for(uint32_t i=0;i<t->node_count;i++)if((t->nodes[i].disk->flags&512)&&(t->nodes[i].disk->flags&(side?256:128))&&small_count<64)managed_store(small,0x20+small_count++*8,hatch_transforms[i]);
 void *smalls=ha_array(transformklass,small_count);for(int i=0;i<small_count;i++)managed_store(smalls,0x20+i*8,P(small,0x20+i*8));hatch_field(body,"smallWheelLodTrfs",smalls);
 void *tracks=ha_array(rendererklass,2);int track_count=0;
 for(uint32_t i=0;i<t->node_count && track_count<2;i++)if(t->nodes[i].disk->flags&64){void *a=hatch_all(hatch_objects[i],rendererklass);if(a && I(a,0x18)>0)managed_store(tracks,0x20+track_count++*8,P(a,0x20));}
 if(track_count==2)hatch_field(body,"scrollLodRends",tracks);
 void *rb=hatch_get_child_component(go,"UnityEngine","Rigidbody");if(rb){float mass=t->config.weight*1000;hatch_set(rb,"set_mass",&mass);}
 void *boxes=hatch_all(go,hatch_class("UnityEngine","BoxCollider"));unsigned box_mask=0;
 if(boxes && I(boxes,0x18)<64)for(int i=0;i<I(boxes,0x18);i++){
  void *box=P(boxes,0x20+i*8),*owner=hatch_call(box,"get_gameObject",0,0);char name[128];utf8_name(hatch_call(owner,"get_name",0,0),name,sizeof(name));
  int k=owner==go?0:!strcmp(name,"Turret")?1:!strcmp(name,"Unit Info")?2:-1;
  if(k>=0){hatch_set(box,"set_size",t->disk.boxes+k*6);hatch_set(box,"set_center",t->disk.boxes+k*6+3);box_mask|=1u<<k;}
 }
 if(box_mask!=7)return hatch_fail("Required collision regions missing");
 const char *track_classes[]={"RealTrackMove","Mesh","MeshFilter"};const char *track_fields[]={"rTrackMoves","sTrackMeshes","sTrackMeshFilters"};
 for(int k=0;k<3;k++){void *c=hatch_class(k?"UnityEngine":"",track_classes[k]);if(c)hatch_field(status,track_fields[k],ha_array(c,0));}


 // Move inherited weapon mounts with the new pivots, keeping the original effects/audio.
 void *launchers=P(pc,0x58);if(launchers && I(launchers,0x18)>0 && I(launchers,0x18)<16){
  float muzzle[3]={0},identity[4]={0,0,0,1},one[3]={1,1,1};hatch_model_point(root,recoil,t->disk.pivots+3,muzzle);
  for(int i=0;i<I(launchers,0x18);i++){void *l=P(launchers,0x20+i*8);void *tr=hatch_call(l,"get_transform",0,0);hatch_parent(tr,recoil,muzzle,identity,one);hatch_field(l,"barrelTrf",recoil);}
 }
 void *mg=P(pc,0x60);if(mg){float p[3]={0},q[4]={0,0,0,1},s[3]={1,1,1};hatch_model_point(root,gun,t->disk.pivots+6,p);hatch_parent(hatch_call(mg,"get_transform",0,0),gun,p,q,s);}
 managed_store(status,0x68,ha_string(t->disk.id));managed_store(status,0x70,ha_string(t->disk.gun));hatch_set(go,"set_name",ha_string(t->disk.id));
 (void)gun_index;(void)object_roots;(void)texture_roots;return !hatch_engine_error;
}
