#pragma once
static int bte_scope_mode(void *control,void *ui,int spg){
    if(!spg||!unity_exists(control)||!unity_exists(ui)||I(ui,0x30)!=2||!B(control,0x78))return 0;
    void *scales=P(control,0x40);int index=I(control,0x88),count=scales?I(scales,0x18):0;
    if(index<0||index>=count||count>32)return 0;
    float scale=F(scales,0x20+index*4);
    return fabsf(scale-5.f)<.01f?2:fabsf(scale-2.5f)<.01f?1:0;
}
