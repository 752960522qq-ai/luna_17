#pragma once
static int crew_notice[5];static volatile int crew_notice_lock;
static void crew_notice_publish(int type,int clock,int metres){bte_lock(&crew_notice_lock);crew_notice[0]++;crew_notice[1]=type;crew_notice[2]=clock;crew_notice[3]=metres;crew_notice[4]=1;bte_unlock(&crew_notice_lock);}
static void crew_notice_clear(void){bte_lock(&crew_notice_lock);crew_notice[4]=0;bte_unlock(&crew_notice_lock);}
