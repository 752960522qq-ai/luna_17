#pragma once
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "custom_tanks.h"
#define HATCH_MAX_TANKS 16
#define HATCH_MAX_BYTES (256u*1024u*1024u)
typedef struct {char id[64],name[128],gun[128];uint32_t nation;int32_t values[31];float numbers[9],boxes[18],pivots[9];} HatchDiskConfig;
typedef struct {int32_t parent;uint32_t flags;float pos[3],rot[4],scale[3];uint32_t vertices,indices;int32_t color,normal;float factor[4];char name[96];} HatchDiskNode;
typedef struct {const HatchDiskNode *disk;const float *vertices;const uint32_t *indices;} HatchNode;
typedef struct {const unsigned char *bytes;uint32_t size;} HatchImage;
typedef struct {HatchDiskConfig disk;CustomTank config;uint32_t node_count,image_count;HatchNode *nodes;HatchImage *images;unsigned char *bytes;} HatchTank;
static HatchTank hatch_tanks[HATCH_MAX_TANKS];
static unsigned hatch_count;
static size_t hatch_bytes;
static char hatch_error[192];
static struct {char id[64];int capacity;float interval,reload;} staged_magazine;
static uint32_t hatch_u32(const unsigned char *p){uint32_t v;memcpy(&v,p,4);return v;}
static int hatch_fail(const char *message){snprintf(hatch_error,sizeof(hatch_error),"%s",message);return 0;}
#include "hatch_options.h"
static int hatch_finite(const float *a,size_t n){for(size_t i=0;i<n;i++)if(!isfinite(a[i]) || fabsf(a[i])>1000000000)return 0;return 1;}
static void hatch_release(HatchTank *t){free(t->nodes);free(t->images);free(t->bytes);memset(t,0,sizeof(*t));}
static int hatch_image_dimensions(const unsigned char *p,uint32_t n){
 unsigned w=0,h=0;
 if(n>=24 && !memcmp(p,"\x89PNG\r\n\x1a\n",8)){
  if(memcmp(p+12,"IHDR",4))return 0;
  w=((unsigned)p[16]<<24)|((unsigned)p[17]<<16)|((unsigned)p[18]<<8)|p[19];
  h=((unsigned)p[20]<<24)|((unsigned)p[21]<<16)|((unsigned)p[22]<<8)|p[23];
 }else if(n>=4 && p[0]==0xff && p[1]==0xd8){
  uint32_t at=2;while(at<n){if(p[at++]!=0xff)return 0;while(at<n&&p[at]==0xff)at++;if(at>=n)return 0;unsigned marker=p[at++];
   if(marker==0xd9||marker==0xda)break;if(marker==0x01||(marker>=0xd0&&marker<=0xd7))continue;
   if(n-at<2)return 0;unsigned len=((unsigned)p[at]<<8)|p[at+1];if(len<2||len>n-at)return 0;
   if((marker>=0xc0&&marker<=0xcf)&&marker!=0xc4&&marker!=0xc8&&marker!=0xcc){if(len<8)return 0;h=((unsigned)p[at+3]<<8)|p[at+4];w=((unsigned)p[at+5]<<8)|p[at+6];break;}at+=len;
  }
 }
 return w>0&&h>0&&w<=4096&&h<=4096;
}
static int hatch_parse(HatchTank *tank,unsigned char *bytes,size_t size){
 memset(tank,0,sizeof(*tank));tank->bytes=bytes;
 if(size<24+sizeof(HatchDiskConfig) || size>HATCH_MAX_BYTES || memcmp(bytes,"HATCH01\0",8) || hatch_u32(bytes+8)!=1 || hatch_u32(bytes+12)!=size)return hatch_fail("Invalid Hatch 0.1 runtime header");
 uint32_t nodes=hatch_u32(bytes+16),images=hatch_u32(bytes+20);
 if(nodes<4 || nodes>2048 || images>128)return hatch_fail("Node/texture count exceeds loader limits");
 memcpy(&tank->disk,bytes+24,sizeof(tank->disk));HatchDiskConfig *d=&tank->disk;
 if(!memchr(d->id,0,64) || !memchr(d->name,0,128) || !memchr(d->gun,0,128) || d->nation>5 || !d->name[0] || !d->gun[0])return hatch_fail("Invalid tank identity");
 size_t length=strlen(d->id);if(!length || length>48)return hatch_fail("Invalid tank ID");
 for(size_t i=0;i<length;i++)if(!((d->id[i]>='A'&&d->id[i]<='Z')||(d->id[i]>='a'&&d->id[i]<='z')||(d->id[i]>='0'&&d->id[i]<='9')||d->id[i]=='_'||d->id[i]=='-'))return hatch_fail("Invalid tank ID characters");
 for(int i=0;i<31;i++)if(d->values[i]<0 || d->values[i]>3000)return hatch_fail("Tank parameter outside supported range");
 if(!hatch_finite(d->numbers,9)||!hatch_finite(d->boxes,18)||!hatch_finite(d->pivots,9)||d->numbers[2]<1 || d->numbers[7]<=0 || d->numbers[8]<=0 || d->values[30]<4 || d->values[30]>24 || d->values[30]%2)return hatch_fail("Invalid physics parameters");
 if(d->numbers[0]>0||d->numbers[0]<=-1||d->numbers[1]<0||d->numbers[1]>80.f/3.6f||d->numbers[2]>200||d->numbers[3]<=0||d->numbers[4]<=0||d->numbers[7]>2||d->values[1]<1||d->values[1]>300||d->values[2]<1||d->values[2]>2500||d->values[3]<1||d->values[3]>120||d->values[4]<1||d->values[5]<1||d->values[5]>150||d->values[9]<1||d->values[9]>20||d->values[10]<1||d->values[10]>255)return hatch_fail("Invalid tank/weapon ranges");
 for(int i=0;i<18;i++)if((i%6)<3 && d->boxes[i]<=0)return hatch_fail("Invalid collider dimensions");
 tank->nodes=calloc(nodes,sizeof(HatchNode));tank->images=calloc(images?images:1,sizeof(HatchImage));if(!tank->nodes||!tank->images)return hatch_fail("Insufficient memory");
 const unsigned char *at=bytes+24+sizeof(*d),*end=bytes+size;unsigned controls[4]={0},road=0,left=0,right=0;
 for(uint32_t i=0;i<nodes;i++){
  if((size_t)(end-at)<sizeof(HatchDiskNode))return hatch_fail("Truncated node");
  const HatchDiskNode *n=(const HatchDiskNode *)at;at+=sizeof(*n);
  if(n->vertices>65535)return hatch_fail("Mesh exceeds 65535 vertices; split the mesh");
  if(n->flags>1023 || n->parent < -1 || n->parent >= (int)nodes || n->parent==(int)i || n->vertices>200000 || n->indices>600000 || n->indices%3 || (!n->vertices && n->indices) || (n->vertices && !n->indices) || n->color < -1 || n->normal < -1 || n->color >= (int)images || n->normal >= (int)images || !memchr(n->name,0,96) || !hatch_finite(n->pos,10) || !hatch_finite(n->factor,4))return hatch_fail("Invalid node or material");
  if(n->scale[0]==0||n->scale[1]==0||n->scale[2]==0)return hatch_fail("Zero scale");
  size_t len=(size_t)n->vertices*32+(size_t)n->indices*4;if(len>(size_t)(end-at))return hatch_fail("Truncated mesh");
  tank->nodes[i]=(HatchNode){n,(const float *)at,(const uint32_t *)(at+(size_t)n->vertices*32)};
  if(!hatch_finite(tank->nodes[i].vertices,(size_t)n->vertices*8))return hatch_fail("Non-finite geometry");
  for(uint32_t j=0;j<n->indices;j++)if(tank->nodes[i].indices[j]>=n->vertices)return hatch_fail("Mesh index outside vertices");
  for(int k=0;k<4;k++)if(n->flags&(1u<<k))controls[k]++;
  if((n->flags&16) && (!(n->flags&384) || (n->flags&384)==384))return hatch_fail("Invalid wheel side");
  if(n->flags&16){road++;if(n->flags&128)left++;if(n->flags&256)right++;}
  at+=len;
 }
 for(int k=0;k<4;k++)if(controls[k]!=1)return hatch_fail("Requires unique Hull/Turret/Gun/Barrel_Recoil nodes");
 if(road!=(unsigned)d->values[30] || left!=road/2 || right!=road/2)return hatch_fail("Wheel count/side mismatch");
 for(uint32_t i=0;i<nodes;i++){
  int p=(int)i;unsigned count=0;while(p>=0){if(++count>nodes)return hatch_fail("Cyclic model hierarchy");p=tank->nodes[p].disk->parent;}
 }
 int control[4]={-1,-1,-1,-1};
 for(uint32_t i=0;i<nodes;i++)for(int k=0;k<4;k++)if(tank->nodes[i].disk->flags&(1u<<k))control[k]=(int)i;
 for(int k=1;k<4;k++){int p=tank->nodes[control[k]].disk->parent;while(p>=0 && p!=control[k-1])p=tank->nodes[p].disk->parent;if(p<0)return hatch_fail("Invalid control hierarchy");}
 for(uint32_t i=0;i<images;i++){
  if((size_t)(end-at)<4)return hatch_fail("Truncated texture length");uint32_t n=hatch_u32(at);at+=4;
  if(n<8 || n>16u*1024u*1024u || n>(size_t)(end-at))return hatch_fail("Truncated/oversized texture");
  if(memcmp(at,"\x89PNG\r\n\x1a\n",8) && !(at[0]==0xff&&at[1]==0xd8))return hatch_fail("Texture must be PNG or JPEG");
  if(!hatch_image_dimensions(at,n))return hatch_fail("Texture dimensions invalid or above 4096");
  tank->images[i]=(HatchImage){at,n};at+=n;
 }
 tank->node_count=nodes;tank->image_count=images;CustomTank *c=&tank->config;int32_t *v=d->values;float *f=d->numbers;
 *c=(CustomTank){.id=d->id,.penetration=v[0],.caliber=v[1],.speed=v[2],.reload=v[3],.reload_offset=f[0],.power=v[4],.max_speed=v[5],.reverse_speed=f[1],.turret_speed=v[6],.weight=f[2],.elevation=v[7],.depression=v[8],.crew=v[9],.tier=v[10],.mg_ammo=v[24],.wheel_count=v[30],.travel=f[3],.rest=f[4],.spring=f[5],.damper=f[6],.radius=f[7],.track_length=f[8]};
 // Hatch 0.1 files store AP/HEAT/APCR/WP/HE; game enum is AP/HE/APCR/WP/HEAT.
 memcpy(c->body_armor,v+11,16);memcpy(c->turret_armor,v+15,16);memcpy(c->ammo,v+19,20);memcpy(c->shell_penetration,v+25,20);
 int swap=c->ammo[1];c->ammo[1]=c->ammo[4];c->ammo[4]=swap;
 swap=c->shell_penetration[1];c->shell_penetration[1]=c->shell_penetration[4];c->shell_penetration[4]=swap;return hatch_read_options(c,at,(size_t)(end-at));
}
static int hatch_load_file(const char *path){
 if(hatch_count>=HATCH_MAX_TANKS)return hatch_fail("Maximum 16 tank packages");FILE *f=fopen(path,"rb");if(!f)return hatch_fail("Cannot open runtime.bin");
 if(fseek(f,0,SEEK_END)){fclose(f);return hatch_fail("Cannot read runtime.bin");}long n=ftell(f);rewind(f);
 if(n<=0 || (unsigned long)n>HATCH_MAX_BYTES || hatch_bytes+(size_t)n>512u*1024u*1024u){fclose(f);return hatch_fail("Runtime package memory limit");}
 unsigned char *b=malloc((size_t)n);if(!b){fclose(f);return hatch_fail("Insufficient memory");}size_t got=fread(b,1,(size_t)n,f);fclose(f);HatchTank t;
 if(got!=(size_t)n){free(b);return hatch_fail("Incomplete file read");}
 if(!hatch_parse(&t,b,(size_t)n)){hatch_release(&t);return 0;}
 for(unsigned i=0;i<hatch_count;i++)if(!strcmp(hatch_tanks[i].disk.id,t.disk.id)){hatch_release(&t);return hatch_fail("Duplicate tank ID");}
 if(staged_magazine.capacity>=2 && !strcmp(staged_magazine.id,t.disk.id)){
  t.config.magazine_capacity=staged_magazine.capacity;t.config.shot_interval=staged_magazine.interval;t.config.magazine_reload=staged_magazine.reload;
  memset(&staged_magazine,0,sizeof(staged_magazine));
 }
 unsigned index=hatch_count;hatch_tanks[index]=t;hatch_tanks[index].config.id=hatch_tanks[index].disk.id;hatch_bytes+=(size_t)n;__atomic_store_n(&hatch_count,index+1,__ATOMIC_RELEASE);hatch_error[0]=0;return 1;
}
static const CustomTank *hatch_find_config(const char *name){for(unsigned i=0;i<__atomic_load_n(&hatch_count,__ATOMIC_ACQUIRE);i++)if(!strcmp(name,hatch_tanks[i].disk.id))return &hatch_tanks[i].config;return 0;}



