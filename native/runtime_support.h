#pragma once
static void *method(void *object,const char *name,int parameters) {
    return object && P(object,0) ? class_method(P(object,0),name,parameters) : 0;
}
static void *get_type(void *object) {
    void *m=method(object,"GetType",0);
    return m ? ((void *(*)(void *,const void *))P(m,0))(object,m) : 0;
}
static void *get_component(void *go,void *type) {
    void *m=method(go,"GetComponent",1);
    return m && type ? ((void *(*)(void *,void *,const void *))P(m,0))(go,type,m) : 0;
}
static int unity_exists(void *object) {
    return object && P(object,0x10)!=0;
}
static void managed_store(void *object,int offset,void *value) {
    P(object,offset)=value;
    FN(RVA_17CA9E4,void (*)(void **,void *))((void **)((uint8_t *)object+offset),value);
}

