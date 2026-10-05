"""Exercise production helpers with misleading Unity overloads preceding Type overloads."""
import os, pathlib, subprocess, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
PRELUDE=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define P(o,n) (*(void **)((uint8_t *)(o)+(n)))
#define I(o,n) (*(int32_t *)((uint8_t *)(o)+(n)))
#define B(o,n) (*(uint8_t *)((uint8_t *)(o)+(n)))
static char hatch_error[192];
static int hatch_fail(const char *s){snprintf(hatch_error,sizeof(hatch_error),"%s",s);return 0;}
static void *(*class_method)(void *,const char *,int);
static void *(*class_fields)(void *,void **);
static void managed_store(void *o,int n,void *v){P(o,n)=v;}
static void *dlsym(void *l,const char *s){return 0;}
'''
HARNESS=r'''
static unsigned char wrong[96],right[96],object[32],result[40];
static int type_class, bool_class, go_class, renderer_class, domain, assembly, fail;
static const void *assemblies[]={&assembly};
static const void *bad_params[]={&bool_class},*good_params[]={&type_class};
static void *mock_domain(void){return &domain;}
static const void **mock_assemblies(void *d,size_t *n){*n=1;return assemblies;}
static void *mock_image(const void *a){return (void *)a;}
static void *mock_class(void *i,const char *ns,const char *n){return !strcmp(n,"Type")?&type_class:&renderer_class;}
static void *mock_identity(void *p){return p;}
static void *mock_methods(void *k,void **it){uintptr_t n=(uintptr_t)*it;*it=(void *)(n+1);return n==0?wrong:n==1?right:0;}
static void *mock_untyped(void *k,const char *s,int n){return wrong;}
static void *mock_invoke(void *m,void *o,void **a,void **ex){
 assert(m==right);assert(a[0]==&renderer_class);
 if(!strcmp(P(m,0x18),"GetComponentsInternal")){
  assert(!*(bool *)a[1]);assert(*(bool *)a[2]);assert(*(bool *)a[3]);assert(!*(bool *)a[4]);assert(a[5]==0);
 }else assert(*(bool *)a[1]);
 if(fail){*ex=&domain;return 0;}return result;
}
int main(void){
 hatch_engine_ok=1;ha_domain=mock_domain;ha_assemblies=mock_assemblies;ha_image=mock_image;ha_class=mock_class;
 ha_type=mock_identity;ha_reflect_type=mock_identity;ha_param_class=mock_identity;ha_methods=mock_methods;ha_invoke=mock_invoke;class_method=mock_untyped;
 P(object,0)=&go_class;P(wrong,0x30)=bad_params;P(right,0x30)=good_params;B(wrong,0x52)=B(right,0x52)=6;
 P(wrong,0x18)=P(right,0x18)="GetComponentsInternal";
 assert(hatch_all(object,&renderer_class)==result);assert(!hatch_engine_error);
 P(wrong,0x18)=P(right,0x18)="GetComponentInChildren";B(wrong,0x52)=B(right,0x52)=2;
 assert(hatch_get_child_component(object,"UnityEngine","Renderer")==result);
 fail=1;P(wrong,0x18)=P(right,0x18)="GetComponentsInternal";B(wrong,0x52)=B(right,0x52)=6;
 assert(hatch_all(object,&renderer_class)==0);assert(hatch_engine_error);
 assert(!strcmp(hatch_error,"Unity exception calling GetComponentsInternal"));
 hatch_engine_error=0;B(right,0x52)=1;
 assert(hatch_all(object,&renderer_class)==0);assert(hatch_engine_error);
 assert(!strcmp(hatch_error,"Unity method unavailable: GetComponentsInternal"));
 puts("4 overload/error checks passed");
}
'''
class RendererDispatch(unittest.TestCase):
 def test_actual_helpers(self):
  header=(ROOT/'native/hatch_engine.h').read_text().split('static void *hatch_objects')[0]
  with tempfile.TemporaryDirectory() as tmp:
   c=pathlib.Path(tmp)/'test.c';exe=pathlib.Path(tmp)/'test';c.write_text(PRELUDE+header+HARNESS)
   subprocess.run(['gcc','-std=c11','-fsanitize=address,undefined','-g',str(c),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True,env={**os.environ,"ASAN_OPTIONS":"detect_leaks=0"})
if __name__=='__main__':unittest.main()
