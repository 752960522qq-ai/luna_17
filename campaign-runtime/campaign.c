/* In-process companion for the offline mission. Runs via the player's existing
   UnityMain looper and the project's 5.1.0 scripting adapter. The original
   native mod is unchanged. */
#include "../native/hatch_embedding.h"
#include "../native/profile_config.h"
#include "mission_state.h"
#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define AT(ptr, o, t) (*(t *)((char *)(ptr) + (o)))
typedef void *(*Method)(void *, const char *, int);
typedef void *(*Fields)(void *, void **);
static Method lookup;
static Fields fields;
static void *goc, *obj, *scene, *timec, *intc, *paramc, *controller, *uStatus,
    *ui;
static int ready, scene_id = -1, player_id, kills = -1, hits = -1, wave_mask;
static float last_time;
static void fire_binding(int,int,void*,void*);
static AimHold shock, crew;
static void *invoke(void *m, void *self, void **args, int *err) {
  void *ex = 0;
  if (!m) {
    *err = 1;
    return 0;
  }
  void *out = ha_invoke(m, self, args, &ex);
  if (ex)
    *err = 1;
  return out;
}
static void *call(void *cl, void *self, const char *name, int count,
                  void **args, int *err) {
  return invoke(cl ? lookup(cl, name, count) : 0, self, args, err);
}
static void *over(void *cl, const char *n, void *type) {
  void *it = 0, *m;
  while (cl && (m = ha_methods(cl, &it))) {
    if (AT(m, 0x52, uint8_t) != 1 || strcmp(AT(m, 0x18, const char *), n))
      continue;
    void **params = AT(m, 0x30, void **);
    if (params && ha_param_class(params[0]) == type)
      return m;
  }
  return 0;
}
static int initialize(void) {
  void *lib = dlopen("libil2cpp.so", RTLD_NOW | RTLD_NOLOAD);
  if (!lib)
    return 0;
  int ok = hatch_bind(lib);
  lookup = (Method)dlsym(lib, SYMBOL_CLASS_METHOD);
  fields = (Fields)dlsym(lib, SYMBOL_CLASS_FIELDS);
  dlclose(lib);
  if (!ok || !lookup || !fields || !ha_domain())
    return 0;
  goc = hatch_class("UnityEngine", "GameObject");
  obj = hatch_class("UnityEngine", "Object");
  timec = hatch_class("UnityEngine", "Time");
  scene = hatch_class("UnityEngine.SceneManagement", "SceneManager");
  intc = hatch_class("System", "Int32");
  paramc = hatch_class("", "GameParamManager");
  controller = hatch_class("", "GameControl");
  uStatus = hatch_class("", "UnitStatus");
  ui = hatch_class("", "GameUiManager");
  return goc && obj && timec && scene && intc && paramc && controller &&
         uStatus && ui;
}
static void *find(const char *n) {
  int e = 0;
  void *a[] = {ha_string(n)};
  return call(goc, 0, "Find", 1, a, &e);
}
static void *component(void *go, void *cl) {
  if (!go)
    return 0;
  int e = 0;
  void *type = hatch_class("System", "Type"), *t = hatch_type_object(cl);
  void *a[] = {t};
  return invoke(over(goc, "GetComponent", type), go, a, &e);
}
static void *instance(void *cl) {
  int e = 0;
  void *m = lookup(cl, "get_Instance", 0);
  if (m) {
    void *p = invoke(m, 0, 0, &e);
    if (p && !e)
      return p;
  }
  void *candidate =
      component(find(cl == paramc ? "GameParam" : "GameController"), cl);
  if (candidate)
    return candidate;
  void *t = hatch_type_object(cl);
  void *args[] = {t};
  void *type = hatch_class("System", "Type");
  return invoke(over(obj, "FindObjectOfType", type), 0, args, &e);
}
static int field(void *cl, const char *n) {
  void *it = 0, *f;
  while ((f = fields(cl, &it))) {
    if (!strcmp(AT(f, 0, const char *), n))
      return AT(f, 0x18, int);
  }
  return -1;
}
static int property(void *p, const char *n, int value) {
  char k[100];
  int e = 0;
  snprintf(k, sizeof k, "set_%s", n);
  void *a[] = {&value};
  call(paramc, p, k, 1, a, &e);
  snprintf(k, sizeof k, "get_%s", n);
  void *v = call(paramc, p, k, 0, 0, &e);
  if (!e && v && AT(v, 16, int) == value)
    return 1;
  /* Some enum accessors are stripped. Use only the five named mission
   * parameters. */
  snprintf(k, sizeof k, "<%s>k__BackingField", n);
  int off = field(paramc, k);
  if (off < 16)
    return 0;
  AT(p, off, int) = value;
  return AT(p, off, int) == value;
}
static void deactivate(void *g) {
  bool v = false;
  void *a[] = {&v};
  int e = 0;
  call(goc, g, "SetActive", 1, a, &e);
}
static int activescene(void) {
  int e = 0;
  void *s = call(scene, 0, "GetActiveScene", 0, 0, &e);
  if (!s || e)
    return -1;
  void *c = AT(s, 0, void *);
  void *ret = call(c, (char *)s + 16, "get_buildIndex", 0, 0, &e);
  return ret && !e ? AT(ret, 16, int) : -1;
}
static int begin(void *mark, int nation) {
  int e = 0;
  void *p = instance(paramc);
  if (!p) {
    deactivate(mark);
    return -1;
  }
  const char *keys[] = {"GameMode", "PlayerNation", "EnemyNation",
                        "PlayerUnitIndex", "CurrentStageNum"};
  int v[] = {0, nation, 1 - nation, 4, 1};
  for (int i = 0; i < 5; i++)
    if (!property(p, keys[i], v[i])) {
      deactivate(mark);
      return -1;
    }
  float scale = 1;
  void *s[] = {&scale};
  call(timec, 0, "set_timeScale", 1, s, &e);
  int target = 22 + nation;
  void *a[] = {&target};
  deactivate(mark);
  invoke(over(scene, "LoadScene", intc), 0, a, &e);
  return e ? -1 : 0;
}
static int statoff = -1, boardoff = -1, deadoff = -1, towedoff = -1, panic = -1,
           gunner = -1, crewn = -1, ko = -1, hi = -1;
static void resolve(void) {
  statoff = field(controller, "<PlayerStatus>k__BackingField");
  boardoff = field(controller, "uiManager");
  deadoff = field(uStatus, "<IsDestroyed>k__BackingField");
  towedoff = field(uStatus, "<IsTowed>k__BackingField");
  panic = field(uStatus, "_isPanic");
  gunner = field(uStatus, "_crewDmgPosNum");
  crewn = field(uStatus, "_crewNum");
  ko = field(ui, "<KillNum>k__BackingField");
  const char *names[] = {"<HitNum>k__BackingField",
                         "<HitShellNum>k__BackingField",
                         "<MainGunHitNum>k__BackingField",
                         "hitNum",
                         "hitShellNum",
                         0};
  for (int i = 0; names[i] && hi < 0; i++)
    hi = field(ui, names[i]);
}
static int blocked(int off) { return off < 16; }
JNIEXPORT jint JNICALL Java_com_luna17_campaign_CampaignLoop_step(JNIEnv *env,
                                                                  jclass cls) {
  (void)env;
  (void)cls;
  if (!ready) {
    ready = initialize();
    if (!ready)
      return 0;
    resolve();
  }
  int idx = activescene();
  if (idx < 0) {
    if (find("Hatch Battle GE"))
      idx = 23;
    else if (find("Hatch Battle SO"))
      idx = 22;
    else
      idx = find("GameController") ? 8 : 0;
  }
  if (idx != scene_id) {
    scene_id = idx;
    player_id = 0;
    wave_mask = 0;
    kills = hits = -1;
    shock = (AimHold){0};
    crew = (AimHold){0};
  }
  if (idx < 8 || idx > 23) fire_binding(idx,-1,0,0);
  if (idx == 0) {
    void *m = find("Hatch Start GE");
    if (m)
      return begin(m, 1);
    m = find("Hatch Start SO");
    return m ? begin(m, 0) : 0;
  }
  if (idx != 22 && idx != 23 && (idx < 8 || idx > 19)) { fire_binding(idx,-1,0,0);return 0; }
  void *p = instance(paramc);
  int e = 0;
  void *mode = p ? call(paramc, p, "get_GameMode", 0, 0, &e) : 0;
  int modeValue = mode && !e ? AT(mode, 16, int) : -1;
  if (modeValue < 0 && p) {
    int f = field(paramc, "<GameMode>k__BackingField");
    if (f == FIELD_GAMEPARAMMANAGER_GAMEMODE_K__BACKINGFIELD)
      modeValue = AT(p, f, int);
  }
  void *gc = modeValue>=0 && modeValue!=2 ? instance(controller) : 0;
  fire_binding(idx,modeValue,gc,gc && !blocked(statoff) ? AT(gc,statoff,void*) : 0);
  if (modeValue != 0) return 0; /* mission logic: local campaign only */
  if (!gc || blocked(statoff) || blocked(boardoff))
    return 0;
  void *st = AT(gc, statoff, void *), *hud = AT(gc, boardoff, void *);
  if (!st || !AT(st, 16, void *) || blocked(deadoff) ||
      AT(st, deadoff, uint8_t))
    return 0;
  void *t = call(timec, 0, "get_time", 0, 0, &e),
       *id = call(obj, st, "GetInstanceID", 0, 0, &e);
  if (e || !t || !id)
    return 0;
  float now = AT(t, 16, float);
  int who = AT(id, 16, int);
  if (!isfinite(now))
    return 0;
  if (who != player_id || now < last_time) {
    shock = (AimHold){0};
    crew = (AimHold){0};
    wave_mask = 0;
    hits = kills = -1;
    player_id = who;
  }
  last_time = now;
  if (!blocked(crewn) && AT(st, crewn, int) > 0 && !blocked(towedoff) &&
      !AT(st, towedoff, uint8_t)) {
    if (!blocked(panic) &&
        expired_hold(&shock, AT(st, panic, uint8_t), now, 2.5f))
      AT(st, panic, uint8_t) = 0;
    if (!blocked(gunner) &&
        expired_hold(&crew, AT(st, gunner, int) == 1, now, 5.f))
      AT(st, gunner, int) = 0;
  }
  int out = 0;
  if (idx == 22 || idx == 23) {
    const char *markers[] = {"Hatch Phase wave2", "Hatch Phase air",
                             "Hatch Phase relief"};
    for (int i = 0; i < 3; i++)
      if (!(wave_mask & (1 << i)) && find(markers[i])) {
        wave_mask |= 1 << i;
        out = 20 + (idx - 22) * 3 + i;
        break;
      }
  }
  if (hud && AT(hud, 16, void *) && idx >= 22) {
    int h=hi>=16?AT(hud,hi,int):-1,k=ko>=16?AT(hud,ko,int):-1;
    if(hits<0)hits=h;
    if(kills<0)kills=k;
    if(!out){
      if(k>kills)out=6;
      else if(h>hits)out=3;
      hits=h;kills=k;
    }
  }
  return out;
}

JNIEXPORT jint JNICALL Java_com_luna17_campaign_CampaignLoop_extraSide(JNIEnv *env,jclass cls){
  (void)env;(void)cls;
  return (scene_id==22 || scene_id==23) && player_id ? scene_id-21 : 0;
}
JNIEXPORT jboolean JNICALL Java_com_luna17_campaign_CampaignLoop_postMessage(JNIEnv *env,jclass cls,jstring text,jint duration){
  (void)cls;
  if(!text || !ready || (scene_id!=22 && scene_id!=23) || blocked(boardoff))return JNI_FALSE;
  void *gc=instance(controller), *hud=gc?AT(gc,boardoff,void*):0;
  if(!hud || !AT(hud,16,void*))return JNI_FALSE;
  const char *s=(*env)->GetStringUTFChars(env,text,0);
  if(!s)return JNI_FALSE;
  void *managed=ha_string(s);(*env)->ReleaseStringUTFChars(env,text,s);
  if(!managed)return JNI_FALSE;
  bool online=false;int seconds=duration,e=0;
  void *args[]={managed,&seconds,&online};call(ui,hud,"SetMessageBox",3,args,&e);
  return e?JNI_FALSE:JNI_TRUE;
}
#include "player_cannon.h"
