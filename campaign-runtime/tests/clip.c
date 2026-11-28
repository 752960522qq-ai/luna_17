#include <assert.h>
#include <math.h>
#include "../clip.h"
int main(void){
 PlayerClip m;clip_reset(&m);
 for(int i=0;i<10;i++){
   float t=i*.4f;
   assert(!clip_request(&m,t,1,0,0)); /* full projectile pool cannot spend ammunition */
   assert(clip_request(&m,t,1,0,1));
   clip_launched(&m,t,1);
   for(int j=1;j<39;j++)assert(!clip_request(&m,t+j*.01f,1,j%2,1));
 }
 assert(fabs(m.available-8.45f)<.0001f);
 for(int j=0;j<484;j++)assert(!clip_request(&m,3.61f+j*.01f,1,1,1));
 assert(clip_request(&m,8.45f,1,0,1));clip_launched(&m,8.45f,1);
 assert(!clip_request(&m,9.f,0,1,1)); /* release of a successful hold is not another shot */
 assert(clip_request(&m,9.01f,0,1,1));int count=m.rounds;
 assert(!clip_request(&m,9.02f,0,1,0)&&m.rounds==count);
 clip_reset(&m);assert(clip_request(&m,0,0,1,1)&&!m.rounds);
 assert(!clip_ack(2u,0u,120,119,12.f,12.f)); /* spending alone is not a launched shot */
 assert(clip_ack(2u,6u,120,120,12.f,12.f)); /* real launch with unchanged reserve */
 assert(clip_ack(2u,0u,120,119,12.f,13.f)); /* immediately resolved shot and native reload */
 int start[]={120,60},lost[]={119,60},other[]={119,61},resupply[]={125,60};
 assert(clip_failed_slot(start,lost)==0 && clip_failed_slot(start,other)<0 && clip_failed_slot(start,resupply)<0);
 return 0;
}
