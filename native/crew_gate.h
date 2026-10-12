#pragma once
#include <string.h>
#define CREW_QUEUE_CAPACITY 256
static int crew_event[4],crew_pending[4],crew_queue[CREW_QUEUE_CAPACITY][4];
static unsigned crew_head,crew_count;static int crew_busy;static volatile int crew_queue_lock;
static void crew_gate_lock(void){while(__atomic_exchange_n(&crew_queue_lock,1,__ATOMIC_ACQUIRE)){} }
static void crew_gate_unlock(void){__atomic_store_n(&crew_queue_lock,0,__ATOMIC_RELEASE);}
// Producers run on Unity's main thread; pending storage is never active speech.
static int crew_gate_begin(void){crew_gate_lock();int room=crew_count<CREW_QUEUE_CAPACITY;crew_gate_unlock();return room;}
static void crew_gate_publish(void){crew_gate_lock();if(crew_count<CREW_QUEUE_CAPACITY){memcpy(crew_queue[(crew_head+crew_count)%CREW_QUEUE_CAPACITY],crew_pending,sizeof(crew_pending));crew_count++;}crew_gate_unlock();}
static int crew_gate_take(void){crew_gate_lock();int ok=!crew_busy&&crew_count;if(ok){memcpy(crew_event,crew_queue[crew_head],sizeof(crew_event));crew_head=(crew_head+1)%CREW_QUEUE_CAPACITY;crew_count--;crew_busy=1;}crew_gate_unlock();return ok;}
static void crew_gate_finish(void){crew_gate_lock();crew_busy=0;crew_gate_unlock();}
static void crew_gate_clear(void){crew_gate_lock();crew_busy=0;crew_head=crew_count=0;crew_gate_unlock();}
