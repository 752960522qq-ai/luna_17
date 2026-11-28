/* Run with cc -std=c11 tests/t28_pose.c -lm. Exercises independent front mount visual limits. */
#include "../t28_pose.h"
#include <assert.h>
#include <stdio.h>
static void near(float got,float want){assert(fabsf(got-want)<.001f);}
static float settle(float bearing,int left){
  float v=0.f;
  for(int j=0;j<80;j++)v=t28_yaw(bearing,v,left,.1f);
  return v;
}
int main(void){
  near(settle(-70,1),-55); near(settle(-70,0),-13);
  near(settle(70,1),13); near(settle(70,0),55);
  near(settle(110,0),27.5f); near(settle(179,1),0); near(settle(-179,0),0);
  near(settle(356,0),-4); near(t28_yaw(50,0,0,.1f),3.6f);
  near(t28_yaw(50,0,0,5),9.f); near(t28_yaw(50,0,0,0),0);
  near(t28_pitch(350),-8); near(t28_pitch(2),2); near(t28_pitch(15),5);
  puts("T28: limited front arcs, wraparound, time steps and pitch OK");
  return 0;
}
