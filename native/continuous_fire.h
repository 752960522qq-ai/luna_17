#pragma once

// Read Unity's own touch/button geometry on the game thread. The Android HUD
// stays transparent and does not intercept either joystick or fire fingers.
static void continuous_fire_update(void *pc){
    const CustomTank *config=tank_config(player_status);
    void *ui=P(pc,0x98),*camera=unity_exists(ui)?P(ui,0x2f8):0;
    if(!config || !config->continuous_fire || state!=3 || !offline_mode() ||
       !unity_exists(ui) || !unity_exists(camera) || I(camera,0x38)!=0 ||
       I(ui,0x2c)>1 || B(player_status,0x206))return;
    int menu=bte_field_offset(ui,"isMenuPopUp");
    if(menu<0 || B(ui,menu))return;
    int offset=bte_field_offset(ui,"fireBtnGos");
    void *buttons=offset>=0?P(ui,offset):0;
    if(!buttons || I(buttons,0x18)<1 || I(buttons,0x18)>16)return;
    void *button=P(buttons,0x20);
    if(!unity_exists(button))return;
    int error=0;
    void *active=enemy_invoke(method(button,"get_activeInHierarchy",0),button,0,&error);
    if(error || !active || !B(active,0x10))return;
    void *rect_type=hatch_type_object(hatch_class("UnityEngine","RectTransform"));
    void *component_args[]={rect_type};
    void *rect=rect_type?enemy_invoke(hatch_method(P(button,0),"GetComponent",1,hatch_class("System","Type")),button,component_args,&error):0;
    if(error || !unity_exists(rect))return;
    void *input=hatch_class("UnityEngine","Input");
    void *count=input?enemy_invoke(class_method(input,"get_touchCount",0),0,0,&error):0;
    if(error || !count)return;
    int n=I(count,0x10);if(n<1 || n>10)return;
    void *utility=hatch_class("UnityEngine","RectTransformUtility");
    void *contains=utility?class_method(utility,"RectangleContainsScreenPoint",3):0;
    if(!contains)return;
    for(int i=0;i<n;i++){
        void *touch_args[]={&i};
        void *touch=enemy_invoke(class_method(input,"GetTouch",1),0,touch_args,&error);
        if(error || !touch)return;
        // Touch: fingerId, position, rawPosition, deltaPosition, deltaTime,
        // tapCount, phase. Unity screen coordinates use a bottom-left origin.
        int phase=I(touch,0x10+36);
        if(phase<0 || phase>2)continue; // ended/cancelled fingers never fire.
        float position[2];memcpy(position,(uint8_t *)touch+0x14,sizeof(position));
        if(!isfinite(position[0]) || !isfinite(position[1]))continue;
        void *args[]={rect,position,0};
        void *inside=enemy_invoke(contains,0,args,&error);
        if(error)return;
        if(inside && B(inside,0x10)){
            // ButtonFire(0) is the audited main-cannon path. It retains loaded
            // shell, crew, ammo, turret readiness and loading-state checks.
            FN(0x198a98c,void (*)(void *,int,const void *))(ui,0,0);
            return;
        }
    }
}
