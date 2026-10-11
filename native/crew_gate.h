#pragma once
static volatile int crew_voice_state;
static int crew_event[4];
static int crew_gate_begin(void){
    int expected=0;
    return __atomic_compare_exchange_n(&crew_voice_state,&expected,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
}
static void crew_gate_publish(void){__atomic_store_n(&crew_voice_state,2,__ATOMIC_RELEASE);}
static int crew_gate_take(void){
    int expected=2;
    return __atomic_compare_exchange_n(&crew_voice_state,&expected,3,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
}
static void crew_gate_finish(void){__atomic_store_n(&crew_voice_state,0,__ATOMIC_RELEASE);}
