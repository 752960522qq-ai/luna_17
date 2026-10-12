#include <assert.h>
#include <stdio.h>
#include "../native/crew_gate.h"
int main(void){
 assert(!crew_gate_take());assert(crew_gate_begin());crew_pending[0]=17;crew_pending[3]=450;crew_gate_publish();assert(crew_gate_take());
 for(int i=0;i<256;i++){assert(crew_gate_begin());crew_pending[0]=i;crew_gate_publish();}
 assert(!crew_gate_begin());assert(crew_event[0]==17&&crew_event[3]==450);assert(!crew_gate_take());crew_gate_finish();
 for(int i=0;i<256;i++){assert(crew_gate_take());assert(crew_event[0]==i);crew_gate_finish();}
 assert(!crew_gate_take());crew_gate_clear();puts("Crew FIFO preserves events during complete segmented speech; bounded capacity");
}
