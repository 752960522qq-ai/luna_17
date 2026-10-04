// Preserve stored anomaly flags and economy values. Only offline launch
// decisions use a different result; network mode always calls the original.
static int offline_title_scope;
static bool (*original_product_check)(void *,const void *);
static int (*original_load_flag)(void *,const void *);
static bool (*original_hnz_check)(const void *);
static bool (*original_iap_sanity)(void *,const void *);
static int offline_mode(void) {
    void *p=FN(RVA_1931CFC,void *(*)(const void *))(0);
    return p && I(p,FIELD_GAMEPARAMMANAGER_GAMEMODE_K__BACKINGFIELD)!=2;
}
static int same_string(void *a,void *b) {
    if(!a || !b)return 0;if(a==b)return 1;
    int n=I(a,0x10);if(n<0 || n>128 || n!=I(b,0x10))return 0;
    uint16_t *x=(uint16_t *)((uint8_t *)a+0x14),*y=(uint16_t *)((uint8_t *)b+0x14);
    for(int i=0;i<n;i++)if(x[i]!=y[i])return 0;
    return 1;
}
static void title_start(void *self,const void *mi) {
    offline_title_scope=offline_mode();original_title_start(self,mi);offline_title_scope=0;
}
static bool product_check(void *self,const void *mi) {
    return offline_title_scope && offline_mode() ? false : original_product_check(self,mi);
}
static int load_flag(void *key,const void *mi) {
    if(offline_mode()){
        void **cell=(void **)P((void *)base,RVA_ACT_CLASS);
        if(cell){FN(RVA_17CAA40,void (*)(void **))(cell);void *klass=*cell;
            if(klass && P(klass,0xb8) && same_string(key,P(P(klass,0xb8),0)))return 0;}
    }
    return original_load_flag(key,mi);
}
static bool hnz_check(const void *mi) { return offline_mode() ? false : original_hnz_check(mi); }
static bool iap_sanity(void *self,const void *mi) {
    bool result=original_iap_sanity(self,mi); // Original inventory and purchase checks still execute.
    return offline_title_scope && offline_mode() ? false : result;
}
