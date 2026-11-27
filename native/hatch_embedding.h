#pragma once
#include <dlfcn.h>
#include <stddef.h>
#include <stdint.h>
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
