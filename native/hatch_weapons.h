#pragma once

enum {
  HATCH_PC_LAUNCHERS = 0x58,
  HATCH_PC_MACHINE_GUN = 0x60,
  HATCH_MG_PARTICLES = 0x20,
  HATCH_MG_AUDIO = 0x28
};

static void *hatch_weapon_mount(void *component) {
  return component ? hatch_call(component, "get_transform", 0, 0) : 0;
}

static int hatch_belongs_to(void *transform, void *parent) {
  if (!transform || !parent)
    return 0;
  void *args[] = {parent};
  void *result = hatch_call(transform, "IsChildOf", 1, args);
  return result && B(result, 0x10);
}

static void *hatch_hide_template_geometry(void *go, void *pc,
                                          void *mesh_renderer) {
  void *mounts[16];
  int mount_count = 0;
  void *launchers = P(pc, HATCH_PC_LAUNCHERS);
  int count = launchers ? I(launchers, 0x18) : 0;
  if (count < 1 || count > 8) {
    hatch_engine_error = 1;
    hatch_fail("Launcher template missing");
    return 0;
  }
  for (int i = 0; i < count; ++i)
    mounts[mount_count++] = hatch_weapon_mount(P(launchers, 0x20 + i * 8));
  void *mg = P(pc, HATCH_PC_MACHINE_GUN);
  if (mg) {
    void *transform = hatch_weapon_mount(mg);
    mounts[mount_count++] = hatch_call(transform, "get_parent", 0, 0);
  }

  // Particle renderers are not body geometry. Shell meshes stay with their
  // launchers.
  void *renderers = hatch_all(go, mesh_renderer);
  count = renderers ? I(renderers, 0x18) : 0;
  if (count < 1 || count > 1024) {
    hatch_engine_error = 1;
    hatch_fail("T34 mesh renderer template missing");
    return 0;
  }
  void *lods = hatch_all(go, hatch_class("UnityEngine", "LODGroup"));
  if (lods && I(lods, 0x18) >= 0 && I(lods, 0x18) < 64) {
    for (int i = 0; i < I(lods, 0x18); ++i) {
      void *lod = P(lods, 0x20 + i * 8);
      void *transform = hatch_call(lod, "get_transform", 0, 0);
      int weapon = 0;
      for (int j = 0; j < mount_count && !weapon; ++j)
        weapon = hatch_belongs_to(transform, mounts[j]);
      if (!weapon) {
        void *empty = ha_array(hatch_class("UnityEngine", "LOD"), 0);
        hatch_set(lod, "SetLODs", empty);
      }
    }
  }
  void *material = 0;
  for (int i = 0; i < count && !hatch_engine_error; ++i) {
    void *renderer = P(renderers, 0x20 + i * 8);
    void *transform = hatch_call(renderer, "get_transform", 0, 0);
    int weapon = 0;
    for (int j = 0; j < mount_count && !weapon; ++j)
      weapon = hatch_belongs_to(transform, mounts[j]);
    if (weapon)
      continue;
    if (!material)
      material = hatch_call(renderer, "get_sharedMaterial", 0, 0);
    bool visible = false;
    hatch_set(renderer, "set_enabled", &visible);
  }
  if (!material && !hatch_engine_error) {
    hatch_engine_error = 1;
    hatch_fail("T34 material template missing");
  }
  return material;
}

static int hatch_bind_weapons(HatchTank *tank, void *pc, void *root, void *gun,
                              void *recoil) {
  const float identity[4] = {0, 0, 0, 1}, one[3] = {1, 1, 1}, zero[3] = {0};
  void *launchers = P(pc, HATCH_PC_LAUNCHERS);
  int count = launchers ? I(launchers, 0x18) : 0;
  if (count < 1 || count > 8)
    return hatch_fail("Launcher template missing");
  float muzzle[3] = {0};
  hatch_model_point(root, recoil, tank->disk.pivots + 3, muzzle);
  for (int i = 0; i < count; ++i) {
    void *launcher = P(launchers, 0x20 + i * 8);
    hatch_parent(hatch_weapon_mount(launcher), recoil, muzzle, identity, one);
    hatch_field(launcher, "barrelTrf", recoil);
  }

  void *mg = P(pc, HATCH_PC_MACHINE_GUN);
  if (tank->config.mg_ammo > 0 && !mg)
    return hatch_fail("Machine gun template missing");
  if (mg) {
    void *transform = hatch_weapon_mount(mg);
    void *mount = hatch_call(transform, "get_parent", 0, 0);
    if (!mount || mount == gun)
      return hatch_fail("Machine gun audio mount missing");
    float coax[3] = {0};
    hatch_model_point(root, gun, tank->disk.pivots + 6, coax);
    // MachineGun.Start gets AudioSource from this parent, ParticleSystem from
    // itself.
    hatch_parent(mount, gun, coax, identity, one);
    hatch_parent(transform, mount, zero, identity, one);
  }
  return !hatch_engine_error;
}

static int hatch_machine_gun_ready(void *pc) {
  void *mg = P(pc, HATCH_PC_MACHINE_GUN);
  return !mg || (unity_exists(mg) && unity_exists(P(mg, HATCH_MG_PARTICLES)) &&
                 unity_exists(P(mg, HATCH_MG_AUDIO)));
}
