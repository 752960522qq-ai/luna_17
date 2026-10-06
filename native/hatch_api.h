#pragma once
// 5.1.0 embedding API bindings identified from this game's ARM64 instructions.
static void *(*ha_domain)(void);
static const void **(*ha_assemblies)(void *, size_t *);
static void *(*ha_image)(const void *);
static void *(*ha_class)(void *, const char *, const char *);
static void *(*ha_new)(void *);
static void *(*ha_array)(void *, uintptr_t);
static void *(*ha_string)(const char *);
static void *(*ha_invoke)(void *, void *, void **, void **);
static void *(*ha_methods)(void *, void **);
static void *(*ha_type)(void *);
static void *(*ha_param_class)(void *);
static void *(*ha_reflect_type)(void *);
static int hatch_engine_ok, hatch_engine_error;
static const char *hatch_bind_error;
static int hatch_bind(void *lib) {
  hatch_bind_error=0;
#define HB(var, symbol)                                                        \
  do {                                                                         \
    *(void **)(&(var)) = dlsym(lib, symbol);                                   \
    if (!(var)) {                                                              \
      hatch_bind_error=symbol;                                                  \
      return 0;                                                                \
    }                                                                \
  } while (0)
  HB(ha_domain, "UfzMkOtv_Gn");
  HB(ha_assemblies, "rVAuNLFRLxv");
  HB(ha_image, "x_LrKbbfHVP");
  HB(ha_class, "DUNcvDcUAAe");
  HB(ha_new, "TgBaGbDucCp");
  HB(ha_array, "GUsixcHyL_y");
  HB(ha_string, "bmILtizhYMG");
  HB(ha_invoke, "kLtgigZNfGj");
  HB(ha_methods, "OSUIuUEDvmO");
  HB(ha_type, "oJVzeZIBbVs");
  HB(ha_param_class, "ugvIuXSfdRU");
  HB(ha_reflect_type, "Ehq_kQowKHa");
#undef HB
  hatch_engine_ok = 1;
  return 1;
}
static void *hatch_class(const char *ns, const char *name) {
  if (!hatch_engine_ok)
    return 0;
  size_t count = 0;
  const void **assemblies = ha_assemblies(ha_domain(), &count);
  if (!assemblies || count > 2048)
    return 0;
  for (size_t i = 0; i < count; i++) {
    void *c = ha_class(ha_image(assemblies[i]), ns, name);
    if (c)
      return c;
  }
  return 0;
}
static void *hatch_type_object(void *klass) {
  return klass ? ha_reflect_type(ha_type(klass)) : 0;
}
static void *hatch_method(void *klass, const char *name, int count,
                          void *first_class) {
  if (!klass)
    return 0;
  if (!first_class)
    return class_method(klass, name, count);
  void *iter = 0, *m;
  while ((m = ha_methods(klass, &iter))) {
    if (!strcmp((const char *)P(m, 0x18), name) && B(m, 0x52) == count) {
      const void **params = P(m, 0x30);
      if (params && ha_param_class((void *)params[0]) == first_class)
        return m;
    }
  }
  return 0;
}
static void *hatch_call_class(void *klass, void *object, const char *name,
                              int count, void **args, void *first_class) {
  if (hatch_engine_error)
    return 0;
  void *m = hatch_method(klass, name, count, first_class);
  if (!m) {
    hatch_engine_error = 1;
    snprintf(hatch_error, sizeof(hatch_error), "Unity method unavailable: %s",
             name);
    return 0;
  }
  void *exception = 0;
  void *result = ha_invoke(m, object, args, &exception);
  if (exception) {
    hatch_engine_error = 1;
    snprintf(hatch_error, sizeof(hatch_error), "Unity exception calling %s",
             name);
  }
  return result;
}
static void *hatch_call(void *o, const char *name, int n, void **a) {
  if (!o) {
    hatch_engine_error = 1;
    hatch_fail("Unity object missing");
    return 0;
  }
  return hatch_call_class(P(o, 0), o, name, n, a, 0);
}
static void hatch_set(void *o, const char *name, void *v) {
  void *a[] = {v};
  hatch_call(o, name, 1, a);
}
static void *hatch_component(void *go, void *klass) {
  void *type = hatch_type_object(klass);
  void *a[] = {type};
  return type ? hatch_call_class(P(go, 0), go, "AddComponent", 1, a,
                                 hatch_class("System", "Type"))
              : 0;
}
static void *hatch_get_child_component(void *go, const char *ns,
                                       const char *name) {
  void *type = hatch_type_object(hatch_class(ns, name));
  bool inactive = true;
  void *a[] = {type, &inactive};
  return type ? hatch_call_class(P(go, 0), go, "GetComponentInChildren", 2, a,
                                 hatch_class("System", "Type"))
              : 0;
}
// 5.1.0 strips the non-generic public child-array overload. Its private
// six-argument implementation remains in the shipped metadata and native code.
static void *hatch_all(void *go, void *klass) {
  void *type = hatch_type_object(klass);
  bool typed_array = false, recursive = true, inactive = true, reverse = false;
  void *a[] = {type, &typed_array, &recursive, &inactive, &reverse, 0};
  return type ? hatch_call_class(P(go, 0), go, "GetComponentsInternal", 6, a,
                                 hatch_class("System", "Type"))
              : 0;
}
static void hatch_field(void *o, const char *name, void *value) {
  if (!o) {
    hatch_engine_error = 1;
    return;
  }
  void *iter = 0, *f;
  while ((f = class_fields(P(o, 0), &iter)))
    if (!strcmp((const char *)P(f, 0), name)) {
      int offset = I(f, 0x18);
      if (offset >= 0x10 && offset < 0x1800) {
        managed_store(o, offset, value);
        return;
      }
    }
  hatch_engine_error = 1;
  snprintf(hatch_error, sizeof(hatch_error), "Game field unavailable: %s",
           name);
}
static void *hatch_new(void *klass, int count, void **args, void *first_class) {
  if (!klass) {
    hatch_engine_error = 1;
    hatch_fail("Unity class missing");
    return 0;
  }
  void *o = ha_new(klass);
  if (!o) {
    hatch_engine_error = 1;
    return 0;
  }
  hatch_call_class(klass, o, ".ctor", count, args, first_class);
  return o;
}
static void *hatch_array_copy(void *klass, const void *data, uint32_t count,
                              size_t size) {
  void *a = ha_array(klass, count);
  if (!a) {
    hatch_engine_error = 1;
    return 0;
  }
  if (data && count)
    memcpy((unsigned char *)a + 0x20, data, (size_t)count * size);
  return a;
}
static void hatch_parent(void *tr, void *parent, const float *pos,
                         const float *rot, const float *scale) {
  hatch_set(tr, "set_parent", parent);
  hatch_set(tr, "set_localPosition", (void *)pos);
  hatch_set(tr, "set_localRotation", (void *)rot);
  hatch_set(tr, "set_localScale", (void *)scale);
}
static void hatch_model_point(void *root, void *tr, const float *model,
                              float *local) {
  float p[3] = {model[0], model[1], -model[2]};
  void *a[] = {p};
  void *world = hatch_call(root, "TransformPoint", 1, a);
  if (!world)
    return;
  void *b[] = {(unsigned char *)world + 0x10};
  void *result = hatch_call(tr, "InverseTransformPoint", 1, b);
  if (result)
    memcpy(local, (unsigned char *)result + 0x10, 12);
}

