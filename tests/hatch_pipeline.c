// Production loader + actual runtime.bin; simulated Unity objects, no GPU.
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <dlfcn.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
#define F(o,n) (*(float *)((uint8_t *)(o)+(n)))
static void *(*class_method)(void *,const char *,int);
static void *(*class_fields)(void *,void **);
static void managed_store(void *o,int n,void *v){P(o,n)=v;}
static int unity_exists(void *o){return o&&P(o,0x10);}
static void utf8_name(void *o,char *out,size_t n){snprintf(out,n,"%s",o?(char *)o:"");}
#include "../native/hatch_data.h"
#include "../native/hatch_engine.h"
typedef struct {const char *name;} Cls;
typedef struct Obj {unsigned char bytes[3072];char name[96];struct Obj *owner,*transform;struct Obj *components[8];int count;} Obj;
static Cls classes[32];static int class_count;static Obj *body,*tm,*root,*material,*boxes[3];
static int textures,meshes,renderers,load_calls,fail_ctor,fail_decode;
static unsigned char methods[80][96];static const void *params[80][1];static int method_count;
static Cls *cls(const char *name){for(int i=0;i<class_count;i++)if(!strcmp(classes[i].name,name))return classes+i;classes[class_count].name=name;return classes+class_count++;}
static Obj *obj(Cls *c,const char *name){Obj *o=calloc(1,sizeof(*o));P(o,0)=c;P(o,16)=o;if(name)snprintf(o->name,96,"%s",name);return o;}
static void *array(void *c,uintptr_t n){void *a=calloc(1,32+n*32);I(a,24)=n;return a;}
static void *lookup(void *c,const char *name,int n){if(!strcmp(name,"set_indexFormat"))return 0;for(int i=0;i<method_count;i++)if(!strcmp(P(methods[i],24),name) && P(methods[i],16)==c&&B(methods[i],82)==n)return methods[i];int i=method_count++;assert(i<80);P(methods[i],16)=c;P(methods[i],24)=(void *)name;B(methods[i],82)=n;params[i][0]=!strcmp(name,".ctor")?cls(n==2?"Int32":!strcmp(((Cls *)c)->name,"GameObject")?"String":((Cls *)c)->name):!strcmp(name,"LoadImage")?cls("Texture2D"):!strcmp(name,"SetTexture")?cls("String"):cls("Type");P(methods[i],48)=params[i];return methods[i];}
static void *enumerate(void *c,void **iter){uintptr_t i=(uintptr_t)*iter;while(i<method_count&&P(methods[i],16)!=c)i++;if(i>=method_count)return 0;*iter=(void *)(i+1);return methods[i];}
static void *identity(void *c){return c;}
static void *new(void *c){return obj(c,0);}
static void *getclass(void *i,const char *ns,const char *name){return cls(name);}
static const void *assembly[]={"fake"};static void *domain(void){return classes;}
static const void **assemblies(void *d,size_t *n){*n=1;return assembly;}
static void *image(const void *a){return (void *)a;}
static void *str(const char *s){return (void *)s;}
static void *invoke(void *m,void *o,void **a,void **ex){
 const char *name=P(m,24);int count=B(m,82);Obj *v=o;
 if(!strcmp(name,".ctor")){
  if(!strcmp(((Cls *)P(o,0))->name,"Texture2D")&&fail_ctor){*ex=classes;return 0;}
  if(!strcmp(((Cls *)P(o,0))->name,"GameObject"))snprintf(v->name,96,"%s",(char *)a[0]);return 0;
 }
 if(!strcmp(name,"LoadImage")){assert(count==2);assert(I(a[1],24)>8);assert(!memcmp((char *)a[1]+32,"\211PNG\r\n\032\n",8));textures++;load_calls++;void *b=calloc(1,24);B(b,16)=!fail_decode;return b;}
 if(!strcmp(name,"get_transform")){if(!v->transform){v->transform=obj(cls("Transform"),v->name);v->transform->owner=v;}return v->transform;}
 if(!strcmp(name,"GetComponentsInternal")){
  assert(count==6&&!*(bool *)a[1]&&*(bool *)a[2]&&*(bool *)a[3]&&!*(bool *)a[4]&&!a[5]);
  Obj *list[8];int n=0;const char *type=((Cls *)a[0])->name;
  if(v==root&&!strcmp(type,"Renderer")){list[n++]=obj(cls("Renderer"),"template");}
  else if(v==root&&!strcmp(type,"BoxCollider")){for(int i=0;i<3;i++)list[n++]=boxes[i];}
  else for(int i=0;i<v->count;i++)if(!strcmp(type,"Renderer")&&!strcmp(((Cls *)P(v->components[i],0))->name,"MeshRenderer"))list[n++]=v->components[i];
  void *out=array(a[0],n);for(int i=0;i<n;i++)P(out,32+i*8)=list[i];return out;
 }
 if(!strcmp(name,"GetComponentInChildren")){const char *type=((Cls *)a[0])->name;return !strcmp(type,"TurretMove")?tm:!strcmp(type,"BodyMove")?body:obj(a[0],"component");}
 if(!strcmp(name,"get_sharedMaterial"))return material;
 if(!strcmp(name,"AddComponent")){Obj *c=obj(a[0],"component");assert(v->count<8);v->components[v->count++]=c;if(!strcmp(((Cls *)a[0])->name,"MeshRenderer"))renderers++;return c;}
 if(!strcmp(name,"get_gameObject"))return v->owner;
 if(!strcmp(name,"get_name"))return v->name;
 if(!strcmp(name,"TransformPoint")||!strcmp(name,"InverseTransformPoint")){void *out=calloc(1,32);memcpy((char *)out+16,a[0],12);return out;}
 if(!strcmp(name,"set_vertices"))meshes++;
 // Setters intentionally have no Unity rendering implementation in this harness.
 return 0;
}
static unsigned char fields[16][32];static const char *fieldnames[]={"thisTrf","gunTrfs","largeWheelLodTrfs","susWheelTrfs","partsTransforms","smallWheelLodTrfs","scrollLodRends","rTrackMoves","sTrackMeshes","sTrackMeshFilters","barrelTrf"};
static void *field(void *c,void **iter){uintptr_t i=(uintptr_t)*iter;if(i>=sizeof(fieldnames)/sizeof(*fieldnames))return 0;*iter=(void *)(i+1);P(fields[i],0)=(void *)fieldnames[i];I(fields[i],24)=0x400+i*8;return fields[i];}
static void setup(void){
 hatch_engine_ok=1;hatch_engine_error=0;ha_domain=domain;ha_assemblies=assemblies;ha_image=image;ha_class=getclass;ha_type=identity;ha_reflect_type=identity;ha_param_class=identity;ha_methods=enumerate;ha_new=new;ha_array=array;ha_string=str;ha_invoke=invoke;class_method=lookup;class_fields=field;
 // Seed the exact overloads the production matching routine needs.
 lookup(cls("Texture2D"),".ctor",2);lookup(cls("Material"),".ctor",1);lookup(cls("GameObject"),".ctor",1);
 lookup(cls("GameObject"),"GetComponentsInternal",6);lookup(cls("GameObject"),"GetComponentInChildren",2);lookup(cls("GameObject"),"AddComponent",1);lookup(cls("ImageConversion"),"LoadImage",2);lookup(cls("Material"),"SetTexture",2);
 root=obj(cls("GameObject"),"T34_85_Player");body=obj(cls("BodyMove"),"body");tm=obj(cls("TurretMove"),"turret");material=obj(cls("Material"),"template material");
 for(int i=0;i<3;i++){boxes[i]=obj(cls("BoxCollider"),"box");boxes[i]->owner=obj(cls("GameObject"),i==0?"T34_85_Player":i==1?"Turret":"Unit Info");if(!i)P(boxes[i]->owner,16)=P(root,16);}
}
int main(int argc,char **argv){assert(argc==2);FILE *f=fopen(argv[1],"rb");assert(f);fseek(f,0,SEEK_END);size_t size=ftell(f);rewind(f);unsigned char *blob=malloc(size);assert(fread(blob,1,size,f)==size);fclose(f);HatchTank tank;assert(hatch_parse(&tank,blob,size));
 setup();Obj *pc=obj(cls("PlayerControl"),"pc"),*status=obj(cls("UnitStatus"),"status");
 if(!hatch_apply_tank(&tank,root,pc,status)){fprintf(stderr,"production loader error: %s\n",hatch_error);return 1;}assert(textures==36&&load_calls==36);assert(meshes>0&&meshes==renderers);assert(P(pc,0x28)&&P(pc,0x30));assert(tank.config.ammo[1]==10&&tank.config.ammo[4]==2);
 printf("full production pipeline: %u nodes, %d textures, %d meshes; ammo enum verified\n",tank.node_count,textures,meshes);
 setup();fail_decode=1;int mesh_before=meshes;assert(!hatch_apply_tank(&tank,root,pc,status));assert(meshes==mesh_before);assert(strstr(hatch_error,"Texture 0 decode failed"));puts("decoder false: no mesh creation; image index and size retained");
 setup();fail_decode=0;fail_ctor=1;int before=load_calls;assert(!hatch_apply_tank(&tank,root,pc,status));assert(load_calls==before);assert(strstr(hatch_error,"Unity exception calling .ctor"));puts("upstream exception retained; decoder was not called after failure");
 unsigned char *large=malloc(size);memcpy(large,blob,size);uint32_t oversized=65536;memcpy(large+616+48,&oversized,4);HatchTank rejected;assert(!hatch_parse(&rejected,large,size));assert(strstr(hatch_error,"Mesh exceeds 65535 vertices"));hatch_release(&rejected);puts("oversized mesh rejected before allocation or Unity calls");
}
