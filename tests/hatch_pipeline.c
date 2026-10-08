// Production loader + actual runtime.bin; simulated Unity objects, no GPU.
#include <assert.h>
#include <dlfcn.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define P(o, n) (*(void **)((uint8_t *)(o) + (n)))
#define I(o, n) (*(int32_t *)((uint8_t *)(o) + (n)))
#define B(o, n) (*(uint8_t *)((uint8_t *)(o) + (n)))
#define F(o, n) (*(float *)((uint8_t *)(o) + (n)))
static void *(*class_method)(void *, const char *, int);
static void *(*class_fields)(void *, void **);
static void managed_store(void *o, int n, void *v) { P(o, n) = v; }
static int unity_exists(void *o) { return o && P(o, 0x10); }
static void utf8_name(void *o, char *out, size_t n) {
  snprintf(out, n, "%s", o ? (char *)o : "");
}
#include "../native/hatch_data.h"
#include "../native/hatch_engine.h"
typedef struct {
  const char *name;
} Cls;
typedef struct Obj {
  unsigned char bytes[3072];
  char name[96];
  struct Obj *owner, *transform;
  struct Obj *components[8];
  int count;
} Obj;
static Cls classes[64];
static int class_count;
static Obj *body, *tm, *root, *material, *boxes[3];
static int textures, meshes, renderers, load_calls, fail_ctor, fail_decode;
static Obj *all_objects[8192];
static int object_count;
static unsigned char methods[128][96];
static const void *params[128][1];
static int method_count;
static void *method_owners[128];
static Cls *cls(const char *name) {
  for (int i = 0; i < class_count; i++)
    if (!strcmp(classes[i].name, name))
      return classes + i;
  classes[class_count].name = name;
  return classes + class_count++;
}
static Obj *obj(Cls *c, const char *name) {
  Obj *o = calloc(1, sizeof(*o));
  P(o, 0) = c;
  P(o, 16) = o;
  assert(object_count < 8192);
  all_objects[object_count++] = o;
  if (name)
    snprintf(o->name, 96, "%s", name);
  return o;
}
static void *array(void *c, uintptr_t n) {
  void *a = calloc(1, 32 + n * 32);
  I(a, 24) = n;
  return a;
}
static void *lookup(void *c, const char *name, int n) {
  for (int i = 0; i < method_count; i++)
    if (method_owners[i] == c && !strcmp(P(methods[i], 24), name) &&
        B(methods[i], 82) == n)
      return methods[i];
  int i = method_count++;
  assert(i < 128);
  method_owners[i] = c;
  P(methods[i], 24) = (void *)name;
  B(methods[i], 82) = n;
  params[i][0] = !strcmp(name, ".ctor")
                     ? cls(n == 2 ? "Int32"
                                  : (!strcmp(((Cls *)c)->name, "GameObject")
                                         ? "String"
                                         : ((Cls *)c)->name))
                 : !strcmp(name, "LoadImage")  ? cls("Texture2D")
                 : !strcmp(name, "SetTexture") ? cls("String")
                                               : cls("Type");
  P(methods[i], 48) = params[i];
  return methods[i];
}
static void *enumerate(void *c, void **iter) {
  uintptr_t i = (uintptr_t)*iter;
  while (i < method_count && method_owners[i] != c)
    i++;
  if (i >= method_count)
    return 0;
  *iter = (void *)(i + 1);
  return methods[i];
}
static void *identity(void *c) { return c; }
static void *new(void *c) { return obj(c, 0); }
static void *getclass(void *i, const char *ns, const char *name) {
  return cls(name);
}
static const void *assembly[] = {"fake"};
static void *domain(void) { return classes; }
static const void **assemblies(void *d, size_t *n) {
  *n = 1;
  return assembly;
}
static void *image(const void *a) { return (void *)a; }
static void *str(const char *s) { return (void *)s; }
static void *invoke(void *m, void *o, void **a, void **ex) {
  const char *name = P(m, 24);
  int count = B(m, 82);
  Obj *v = o;
  if (!strcmp(name, ".ctor")) {
    if (!strcmp(((Cls *)P(o, 0))->name, "Texture2D") && fail_ctor) {
      *ex = classes;
      return 0;
    }
    if (!strcmp(((Cls *)P(o, 0))->name, "GameObject"))
      snprintf(v->name, 96, "%s", (char *)a[0]);
    return 0;
  }
  if (!strcmp(name, "LoadImage")) {
    assert(count == 2);
    assert(I(a[1], 24) > 8);
    assert(!memcmp((char *)a[1] + 32, "\211PNG\r\n\032\n", 8) ||
           (!memcmp((char *)a[1] + 32, "\xff\xd8", 2)));
    textures++;
    load_calls++;
    void *b = calloc(1, 24);
    B(b, 16) = !fail_decode;
    return b;
  }
  if (!strcmp(name, "set_parent")) {
    P(o, 0x70) = a[0];
    return 0;
  }
  if (!strcmp(name, "get_transform")) {
    if (v->owner)
      v = v->owner;
    if (!v->transform) {
      v->transform = obj(cls("Transform"), v->name);
      v->transform->owner = v;
    }
    return v->transform;
  }
  if (!strcmp(name, "GetComponentsInternal")) {
    assert(count == 6 && !*(bool *)a[1] && *(bool *)a[2] && *(bool *)a[3] &&
           !*(bool *)a[4] && !a[5]);
    Obj *list[1024];
    int n = 0;
    const char *type = ((Cls *)a[0])->name;
    if (v == root && !strcmp(type, "BoxCollider")) {
      for (int i = 0; i < 3; i++)
        list[n++] = boxes[i];
    } else
      for (int k = 0; k < object_count; k++) {
        Obj *candidate = all_objects[k];
        if (strcmp(((Cls *)P(candidate, 0))->name, "GameObject"))
          continue;
        Obj *tr = candidate->transform;
        int descendant = (candidate == v);
        for (int depth = 0; tr && !descendant && depth < 2048; depth++) {
          tr = P(tr, 0x70);
          descendant = tr && tr->owner == v;
        }
        if (descendant)
          for (int i = 0; i < candidate->count; i++) {
            Obj *comp = candidate->components[i];
            const char *kind = ((Cls *)P(comp, 0))->name;
            if (!strcmp(type, kind) ||
                (!strcmp(type, "Renderer") &&
                 (!strcmp(kind, "MeshRenderer") ||
                  !strcmp(kind, "ParticleSystemRenderer")))) {
              assert(n < 1024);
              list[n++] = comp;
            }
          }
      }
    void *out = array(a[0], n);
    for (int i = 0; i < n; i++)
      P(out, 32 + i * 8) = list[i];
    return out;
  }
  if (!strcmp(name, "GetComponentInChildren")) {
    const char *type = ((Cls *)a[0])->name;
    return !strcmp(type, "TurretMove") ? tm
           : !strcmp(type, "BodyMove") ? body
                                       : obj(a[0], "component");
  }
  if (!strcmp(name, "get_sharedMaterial"))
    return material;
  if (!strcmp(name, "AddComponent")) {
    Obj *c = obj(a[0], "component");
    assert(v->count < 8);
    v->components[v->count++] = c;
    c->owner = v;
    if (!strcmp(((Cls *)a[0])->name, "MeshRenderer"))
      renderers++;
    return c;
  }
  if (!strcmp(name, "SetLODs")) {
    assert(I(a[0], 24) == 0);
    B(o, 0x181) = 1;
    return 0;
  }
  if (!strcmp(name, "get_parent"))
    return P(o, 0x70);
  if (!strcmp(name, "IsChildOf")) {
    Obj *tr = o;
    int yes = 0;
    for (int i = 0; tr && i < 2048; i++, tr = P(tr, 0x70))
      if (tr == a[0]) {
        yes = 1;
        break;
      }
    void *result = calloc(1, 24);
    B(result, 16) = yes;
    return result;
  }
  if (!strcmp(name, "set_enabled")) {
    B(o, 0x180) = *(bool *)a[0];
    return 0;
  }
  if (!strcmp(name, "get_gameObject"))
    return v->owner;
  if (!strcmp(name, "get_name"))
    return v->name;
  if (!strcmp(name, "TransformPoint") ||
      !strcmp(name, "InverseTransformPoint")) {
    void *out = calloc(1, 32);
    memcpy((char *)out + 16, a[0], 12);
    return out;
  }
  if (!strcmp(name, "set_vertices"))
    meshes++;
  // Setters intentionally have no Unity rendering implementation in this
  // harness.
  return 0;
}
static Obj *hull_renderer, *ap_renderer, *he_renderer, *particle_renderer, *mg,
    *mg_mount, *launcher, *lod;
static unsigned char fields[16][32];
static const char *fieldnames[] = {
    "thisTrf",         "gunTrfs",           "largeWheelLodTrfs", "susWheelTrfs",
    "partsTransforms", "smallWheelLodTrfs", "scrollLodRends",    "rTrackMoves",
    "sTrackMeshes",    "sTrackMeshFilters", "barrelTrf"};
static void *field(void *c, void **iter) {
  uintptr_t i = (uintptr_t)*iter;
  if (i >= sizeof(fieldnames) / sizeof(*fieldnames))
    return 0;
  *iter = (void *)(i + 1);
  P(fields[i], 0) = (void *)fieldnames[i];
  I(fields[i], 24) = 0x400 + i * 8;
  return fields[i];
}
static Obj *fixture_go(const char *name, Obj *parent) {
  Obj *go = obj(cls("GameObject"), name);
  go->transform = obj(cls("Transform"), name);
  go->transform->owner = go;
  if (parent)
    P(go->transform, 0x70) = parent->transform;
  return go;
}
static Obj *fixture_component(Obj *go, const char *kind) {
  Obj *c = obj(cls(kind), kind);
  c->owner = go;
  go->components[go->count++] = c;
  B(c, 0x180) = 1;
  return c;
}
static void fixture_weapons(Obj *pc) {
  root->transform = obj(cls("Transform"), "root");
  root->transform->owner = root;
  Obj *turret = fixture_go("Turret", root), *gun = fixture_go("Gun", turret);
  P(pc, 0x28) = turret->transform;
  P(pc, 0x30) = gun->transform;
  hull_renderer =
      fixture_component(fixture_go("old hull", root), "MeshRenderer");
  lod = fixture_component(root, "LODGroup");
  Obj *fire = fixture_go("Fire Point", gun);
  launcher = fixture_component(fire, "Launcher");
  void *ls = array(cls("Launcher"), 1);
  P(ls, 32) = launcher;
  P(pc, 0x58) = ls;
  ap_renderer = fixture_component(fixture_go("Shell AP", fire), "MeshRenderer");
  he_renderer = fixture_component(fixture_go("Shell HE", fire), "MeshRenderer");
  mg_mount = fixture_go("MG Effects Point", gun);
  fixture_component(mg_mount, "AudioSource");
  Obj *effect = fixture_go("Machine Gun Effect", mg_mount);
  mg = fixture_component(effect, "MachineGun");
  particle_renderer = fixture_component(effect, "ParticleSystemRenderer");
  P(pc, 0x60) = mg;
}
static void setup(void) {
  hatch_engine_ok = 1;
  hatch_engine_error = 0;
  object_count = 0;
  ha_domain = domain;
  ha_assemblies = assemblies;
  ha_image = image;
  ha_class = getclass;
  ha_type = identity;
  ha_reflect_type = identity;
  ha_param_class = identity;
  ha_methods = enumerate;
  ha_new = new;
  ha_array = array;
  ha_string = str;
  ha_invoke = invoke;
  class_method = lookup;
  class_fields = field;
  // Seed the exact overloads the production matching routine needs.
  lookup(cls("Texture2D"), ".ctor", 2);
  lookup(cls("Material"), ".ctor", 1);
  lookup(cls("GameObject"), ".ctor", 1);
  lookup(cls("GameObject"), "GetComponentsInternal", 6);
  lookup(cls("GameObject"), "GetComponentInChildren", 2);
  lookup(cls("GameObject"), "AddComponent", 1);
  lookup(cls("ImageConversion"), "LoadImage", 2);
  lookup(cls("Material"), "SetTexture", 2);
  root = obj(cls("GameObject"), "T34_85_Player");
  body = obj(cls("BodyMove"), "body");
  tm = obj(cls("TurretMove"), "turret");
  material = obj(cls("Material"), "template material");
  for (int i = 0; i < 3; i++) {
    boxes[i] = obj(cls("BoxCollider"), "box");
    boxes[i]->owner =
        i == 0 ? root : obj(cls("GameObject"), i == 1 ? "Turret" : "Unit Info");
  }
}
int main(int argc, char **argv) {
  assert(argc == 2);
  FILE *f = fopen(argv[1], "rb");
  assert(f);
  fseek(f, 0, SEEK_END);
  size_t size = ftell(f);
  rewind(f);
  unsigned char *blob = malloc(size);
  assert(fread(blob, 1, size, f) == size);
  fclose(f);
  HatchTank tank;
  assert(hatch_parse(&tank, blob, size));
  setup();
  Obj *pc = obj(cls("PlayerControl"), "pc"),
      *status = obj(cls("UnitStatus"), "status");
  fixture_weapons(pc);
  if (!hatch_apply_tank(&tank, root, pc, status)) {
    fprintf(stderr, "pipeline error: %s\n", hatch_error);
    return 1;
  }
  assert(textures == tank.image_count && load_calls == tank.image_count);
  assert(meshes > 0 && meshes == renderers);
  assert(P(pc, 0x28) && P(pc, 0x30));
  assert(I(P(body, 0x410), 24) == tank.config.wheel_count &&
         I(P(body, 0x418), 24) == tank.config.wheel_count &&
         I(P(body, 0x430), 24) == (tank.config.vehicle_kind == HATCH_VEHICLE_TOWED ? 0 : 2));
  assert(!B(hull_renderer, 0x180) && B(lod, 0x181));
  assert(B(ap_renderer, 0x180) && B(he_renderer, 0x180) &&
         B(particle_renderer, 0x180));
  assert(P(mg->owner->transform, 0x70) == mg_mount->transform &&
         P(mg_mount->transform, 0x70) == P(pc, 0x30));
  assert(!hatch_machine_gun_ready(pc));
  P(mg, 0x20) = obj(cls("ParticleSystem"), "particle");
  P(mg, 0x28) = obj(cls("AudioSource"), "audio");
  assert(hatch_machine_gun_ready(pc));
  puts("AP/HE mesh renderers and MG particles preserved; old hull/LOD "
       "disabled; MG audio parent retained");
  printf("full production pipeline: %u nodes, %d textures, %d meshes; ammo "
         "enum verified\n",
         tank.node_count, textures, meshes);
  setup();
  fixture_weapons(pc);
  fail_ctor = 1;
  int before = load_calls;
  assert(!hatch_apply_tank(&tank, root, pc, status));
  assert(load_calls == before);
  assert(strstr(hatch_error, "Unity exception calling .ctor"));
  puts("upstream exception retained; decoder was not called after failure");
  fail_ctor = 0;
  setup();
  fixture_weapons(pc);
  fail_decode = 1;
  int mesh_before = meshes;
  assert(!hatch_apply_tank(&tank, root, pc, status));
  assert(meshes == mesh_before);
  assert(strstr(hatch_error, "Texture 0 decode failed"));
  puts("Decoder failure stops before mesh construction");
  hatch_release(&tank);
}
