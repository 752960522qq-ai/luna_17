#include <assert.h>
#include "../storm_clock.h"
int main(void){
  for(int side=24;side<=25;side++){
    StormClock s={0};storm_tick(&s,side,3,120);
    for(int i=0;i<540;i++)storm_tick(&s,side,3,120); /* a long real pause */
    assert(storm_verdict(&s,0,0,2)==RUNNING);
    storm_tick(&s,side,3,899.99f);assert(storm_verdict(&s,0,0,6)==RUNNING);
    storm_tick(&s,side,3,900);assert(storm_verdict(&s,0,0,6)==(side==24?WON:LOST));
    assert(storm_verdict(&s,0,0,0)==WON&&storm_verdict(&s,0,1,0)==RUNNING&&storm_verdict(&s,1,0,2)==RUNNING);
    assert(storm_verdict(&s,0,0,-1)==RUNNING);
    s.requested=LOST;assert(storm_verdict(&s,0,0,6)==RUNNING);
    storm_tick(&s,side,4,901);assert(!s.requested&&s.start==901&&storm_verdict(&s,0,0,1)==RUNNING);
    storm_tick(&s,side,4,15);assert(s.start==15);storm_tick(&s,side,4,NAN);assert(s.last==15);
  }
}
