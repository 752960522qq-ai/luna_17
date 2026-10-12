#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "../native/ammunition_identity.h"
int main(void){char names[][64]={"SU_85_Player(Clone)","SU_85_AI (Clone)","SU_85_Enemy","Grille(Clone)"};for(int i=0;i<4;i++){ammunition_normalize(names[i]);assert(!strcmp(names[i],i==3?"Grille":"SU_85"));}puts("Player, AI, Enemy and Clone names normalize without crossing mod IDs");}
