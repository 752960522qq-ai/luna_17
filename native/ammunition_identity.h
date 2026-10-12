#pragma once
static void ammunition_normalize(char *name){
 char *clone=strstr(name,"(Clone)");if(clone)*clone=0;
 size_t n=strlen(name);while(n&&name[n-1]==' ')name[--n]=0;
 const char *suffix[]={"_Player","_AI","_Enemy"};
 for(int i=0;i<3;i++){size_t k=strlen(suffix[i]);if(n>=k&&!strcmp(name+n-k,suffix[i])){name[n-k]=0;break;}}
}
