#include "../native/hatch_data.h"
_Static_assert(sizeof(HatchDiskConfig)==592,"config layout");
_Static_assert(sizeof(HatchDiskNode)==176,"node layout");
int main(int count,char **args){
 for(int i=1;i<count;i++)if(!hatch_load_file(args[i])){fprintf(stderr,"%s\n",hatch_error);return 1;}
 printf("%u\n",hatch_count);return 0;
}
