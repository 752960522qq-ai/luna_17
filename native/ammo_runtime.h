#pragma once
typedef struct { void *owner,*arrays[2]; int counts[2]; ObscuredInt slots[2][32]; } AmmoSnapshot;
static AmmoSnapshot ammo_snapshot;
static int plain_int(ObscuredInt v) { return (int)(((unsigned)v.hidden-(unsigned)v.key)^(unsigned)v.key); }
void write_ammo_slot(void *array,int index,int count) {
    if(!array || index<0 || index>=I(array,0x18) || I(array,0x18)>32 || count<0)return;
    ObscuredInt v=FN(RVA_18F26B0,ObscuredInt (*)(int,const void *))(count,0);
    memcpy((uint8_t *)array+0x20+index*sizeof(v),&v,sizeof(v));
}
void refill(void *status) {
    if(!status)return;
    if(ammo_snapshot.owner!=status){memset(&ammo_snapshot,0,sizeof(ammo_snapshot));ammo_snapshot.owner=status;}
    const int offsets[]={FIELD_UNITSTATUS_SHELLNUMS_K__BACKINGFIELD,FIELD_UNITSTATUS_SUBARMSNUMS_K__BACKINGFIELD};
    for(int a=0;a<2;a++){
        void *array=P(status,offsets[a]);if(!array)continue;
        int n=I(array,0x18);if(n<1 || n>32)continue;
        ObscuredInt *values=(ObscuredInt *)((uint8_t *)array+0x20);
        if(ammo_snapshot.arrays[a]!=array || ammo_snapshot.counts[a]!=n){
            ammo_snapshot.arrays[a]=array;ammo_snapshot.counts[a]=n;
            memcpy(ammo_snapshot.slots[a],values,n*sizeof(*values));
        }
        for(int i=0;i<n;i++)if(plain_int(ammo_snapshot.slots[a][i])>0 && plain_int(values[i])<plain_int(ammo_snapshot.slots[a][i]))
            memcpy(values+i,&ammo_snapshot.slots[a][i],sizeof(*values));
    }
}

// Return early only for the local player's current UnitStatus in an offline match.
int mod_ignore_damage(void *self) {
    return ready==1 && state==3 && god && self && player_status && P(self,0x38)==player_status;
}
int mod_ignore_engine(void *self) {
    return ready==1 && state==3 && god && self && player_status && P(self,0x40)==player_status;
}

