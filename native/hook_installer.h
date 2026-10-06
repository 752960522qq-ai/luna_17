#pragma once
static void emit_absolute(uint32_t **out,uintptr_t destination,unsigned reg) {
    *(*out)++=0xd2800000|((destination&0xffff)<<5)|reg;
    for(unsigned i=1;i<4;i++) *(*out)++=0xf2800000|(i<<21)|(((destination>>(i*16))&0xffff)<<5)|reg;
}
int install(uintptr_t rva,void *replacement,void **original) {
    uint32_t *entry=(uint32_t *)(base+rva);
    uint32_t *tramp=mmap(0,(size_t)page_size,3,0x22,-1,0);
    if(tramp==(void *)-1) return 0;
    uint32_t *cursor=tramp;
    for(int i=0;i<4;i++) {
        uint32_t instruction=entry[i];
        if((instruction&0x9f000000)==0x90000000) {
            int64_t imm=((instruction>>29)&3)|(((instruction>>5)&0x7ffff)<<2);
            if(imm&(1<<20)) imm-=1<<21;
            uintptr_t target=((base+rva+i*4)&~(uintptr_t)0xfff)+(imm*4096);
            emit_absolute(&cursor,target,instruction&31);
        } else if((instruction&0x7c000000)==0x14000000) {
            int64_t imm=instruction&0x3ffffff;
            if(imm&(1<<25))imm-=1<<26;
            uintptr_t target=base+rva+i*4+imm*4;
            if(target>=base+rva && target<base+rva+16){munmap(tramp,(size_t)page_size);return 0;}
            emit_absolute(&cursor,target,16);
            *cursor++=(instruction&0x80000000)?0xd63f0200:0xd61f0200;
        } else {
            // All selected prologues contain only ordinary instructions or ADRP.
            if((instruction&0x9f000000)==0x10000000 ||
               (instruction&0x3b000000)==0x18000000 || (instruction&0xff000010)==0x54000000 ||
               (instruction&0x7e000000)==0x34000000 || (instruction&0x7e000000)==0x36000000) {
                munmap(tramp,(size_t)page_size);return 0;
            }
            *cursor++=instruction;
        }
    }
    *cursor++=0x58000050;*cursor++=0xd61f0200;
    uintptr_t resume=base+rva+16;memcpy(cursor,&resume,8);
    clear_cache(tramp,(uint8_t *)cursor+8);
    if(mprotect(tramp,(size_t)page_size,5)) {munmap(tramp,(size_t)page_size);return 0;}
    *original=tramp;
    uintptr_t page=(uintptr_t)entry&~((uintptr_t)page_size-1);
    size_t span=((((uintptr_t)entry+16+page_size-1)&~((uintptr_t)page_size-1))-page);
    if(mprotect((void *)page,span,7)) return 0;
    uint32_t patch[4]={0x58000050,0xd61f0200,0,0};memcpy(patch+2,&replacement,8);
    memcpy(entry,patch,16);clear_cache(entry,(uint8_t *)entry+16);
    return mprotect((void *)page,span,5)==0;
}

