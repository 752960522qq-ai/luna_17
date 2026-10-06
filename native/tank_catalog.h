#pragma once
static void build_catalog(void *gen) {
    static const int offsets[]={0x28,0x30,0x40,0x48,0x50,0x58};
    for(int nation=0;nation<6;nation++) {
        void *a=P(gen,offsets[nation]);
        if(!a) continue;
        int n=I(a,0x18);
        if(n<0 || n>MAX_TANKS) continue;
        unsigned generation=__atomic_load_n(&hatch_count,__ATOMIC_ACQUIRE);
        if(catalog_source[nation]==a && catalog_stock[nation]==n && catalog_generation[nation]==generation) continue;
        catalog_count[nation]=0;
        for(int i=0;i<n;i++) {
            catalog_hatch[nation][i]=-1;
            void *go=P(a,0x20+i*8);
            void *m=method(go,"get_name",0);
            void *str=m ? ((void *(*)(void *,const void *))P(m,0))(go,m) : 0;
            utf8_name(str,catalog[nation][i],sizeof(catalog[nation][i]));
            if(!catalog[nation][i][0]) {
                char *q=catalog[nation][i];
                q[0]='#'; int v=i+1;
                q[1]=(char)('0'+v/100);q[2]=(char)('0'+v/10%10);q[3]=(char)('0'+v%10);q[4]=0;
            }
        }
        catalog_stock[nation]=n;
        for(unsigned h=0;h<generation && n<MAX_TANKS;h++)if(hatch_tanks[h].disk.nation==(unsigned)nation){
            snprintf(catalog[nation][n],sizeof(catalog[nation][n]),"Hatch · %s",hatch_tanks[h].disk.id);
            catalog_hatch[nation][n++]=(int)h;
        }
        catalog_source[nation]=a;catalog_generation[nation]=generation;
        __atomic_store_n(&catalog_count[nation],n,__ATOMIC_RELEASE);
    }
}

