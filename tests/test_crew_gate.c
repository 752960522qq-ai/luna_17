#include <assert.h>
#include <pthread.h>
#include <stdio.h>
#include "../native/crew_gate.h"
static void *trigger(void *unused){(void)unused;for(int i=0;i<10000;i++)assert(!crew_gate_begin());return 0;}
int main(void){
    assert(!crew_gate_take());assert(crew_gate_begin());
    crew_event[0]=1;crew_event[1]=2;crew_event[2]=3;crew_event[3]=450;
    assert(!crew_gate_begin());assert(!crew_gate_take());
    crew_gate_publish();assert(!crew_gate_begin());assert(crew_gate_take());assert(!crew_gate_take());
    pthread_t threads[4];for(int i=0;i<4;i++)assert(!pthread_create(&threads[i],0,trigger,0));
    for(int i=0;i<4;i++)pthread_join(threads[i],0);
    assert(crew_event[0]==1&&crew_event[3]==450);
    // Finishing an intermediate clip must not call finish. Gate stays held
    // until the Android player's whole utterance completion callback.
    assert(!crew_gate_begin());crew_gate_finish();assert(!crew_gate_take());
    assert(crew_gate_begin());crew_gate_publish();assert(crew_gate_take());crew_gate_finish();
    puts("Crew gate: dropped concurrent/intermediate triggers; no deferred event");
}
