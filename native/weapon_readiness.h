#pragma once
// AP penetration may be zero on HE/HEAT-only vehicles such as Grille.
static int weapon_ready(void *pc,void *status,void *game) {
    void *array=P(pc,0x58);if(!array)return 0;
    int n=I(array,0x18);if(n<1 || n>8)return 0;
    int power=plain_int(*(ObscuredInt *)((uint8_t *)status+0x78));
    int speed=plain_int(*(ObscuredInt *)((uint8_t *)status+0xa8));
    if(power<0 || speed<=0 || !P(status,0xf0))return 0;
    for(int i=0;i<n;i++){
        void *launcher=P(array,0x20+i*8);
        if(!unity_exists(launcher) || !unity_exists(P(launcher,0x20)))return 0;
        managed_store(launcher,0x38,status);managed_store(launcher,0xb0,game);
        if(!B(launcher,0xa0)){I(launcher,0x50)=power;F(launcher,0x54)=(float)speed;}
        if(I(launcher,0x50)<0 || F(launcher,0x54)<=0)return 0;
    }
    return hatch_machine_gun_ready(pc);
}
