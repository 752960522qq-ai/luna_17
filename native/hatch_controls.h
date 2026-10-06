#pragma once
static int hatch_bind_controls(HatchTank *t, void *go, void *pc, void *status,
                               void *turret, void *gun, void *rendererklass,
                               void *transformklass) {
  void *old_turret = P(pc, 0x28), *old_gun = P(pc, 0x30);
  float zero[3] = {0}, identity[4] = {0, 0, 0, 1}, one[3] = {1, 1, 1};
  if (old_turret)
    hatch_parent(old_turret, turret, zero, identity, one);
  if (old_gun)
    hatch_parent(old_gun, gun, zero, identity, one);
  managed_store(pc, 0x28, turret);
  managed_store(pc, 0x30, gun);
  void *tm = hatch_get_child_component(go, "", "TurretMove"),
       *body = hatch_get_child_component(go, "", "BodyMove");
  if (!tm || !body || hatch_engine_error)
    return hatch_fail("T34 control components missing");
  hatch_field(tm, "thisTrf", turret);
  void *guns = ha_array(transformklass, 1);
  managed_store(guns, 0x20, gun);
  hatch_field(tm, "gunTrfs", guns);
  void *wheels = ha_array(transformklass, t->config.wheel_count),
       *susp = ha_array(transformklass, t->config.wheel_count);
  int wi = 0;
  for (int side = 0; side < 2; side++)
    for (uint32_t i = 0; i < t->node_count; i++)
      if ((t->nodes[i].disk->flags & 16) &&
          (t->nodes[i].disk->flags & (side ? 256 : 128))) {
        managed_store(wheels, 0x20 + wi * 8, hatch_transforms[i]);
        int parent = t->nodes[i].disk->parent;
        managed_store(susp, 0x20 + wi * 8,
                      parent >= 0 && (t->nodes[parent].disk->flags & 32)
                          ? hatch_transforms[parent]
                          : hatch_transforms[i]);
        wi++;
      }
  hatch_field(body, "largeWheelLodTrfs", wheels);
  hatch_field(body, "susWheelTrfs", susp);
  void *empty = ha_array(transformklass, 0);
  hatch_field(body, "partsTransforms", empty);
  hatch_field(body, "smallWheelLodTrfs", empty);
  I(body, 0x68) = 1;
  F(body, 0x88) = t->config.rest;
  F(body, 0xa8) = 1;
  I(body, 0xac) = 1;
  I(body, 0xb0) = t->config.wheel_count / 2;
  void *small = ha_array(transformklass, 64);
  int small_count = 0;
  for (int side = 0; side < 2; side++)
    for (uint32_t i = 0; i < t->node_count; i++)
      if ((t->nodes[i].disk->flags & 512) &&
          (t->nodes[i].disk->flags & (side ? 256 : 128)) && small_count < 64)
        managed_store(small, 0x20 + small_count++ * 8, hatch_transforms[i]);
  void *smalls = ha_array(transformklass, small_count);
  for (int i = 0; i < small_count; i++)
    managed_store(smalls, 0x20 + i * 8, P(small, 0x20 + i * 8));
  hatch_field(body, "smallWheelLodTrfs", smalls);
  void *tracks = ha_array(rendererklass, 2);
  int track_count = 0;
  for (uint32_t i = 0; i < t->node_count && track_count < 2; i++)
    if (t->nodes[i].disk->flags & 64) {
      void *a = hatch_all(hatch_objects[i], rendererklass);
      if (a && I(a, 0x18) > 0)
        managed_store(tracks, 0x20 + track_count++ * 8, P(a, 0x20));
    }
  if (track_count == 2)
    hatch_field(body, "scrollLodRends", tracks);
  void *rb = hatch_get_child_component(go, "UnityEngine", "Rigidbody");
  if (rb) {
    float mass = t->config.weight * 1000;
    hatch_set(rb, "set_mass", &mass);
  }
  void *boxes = hatch_all(go, hatch_class("UnityEngine", "BoxCollider"));
  unsigned box_mask = 0;
  if (boxes && I(boxes, 0x18) < 64)
    for (int i = 0; i < I(boxes, 0x18); i++) {
      void *box = P(boxes, 0x20 + i * 8),
           *owner = hatch_call(box, "get_gameObject", 0, 0);
      char name[128];
      utf8_name(hatch_call(owner, "get_name", 0, 0), name, sizeof(name));
      int k = (owner == go || (unity_exists(owner) && unity_exists(go) &&
                               P(owner, 0x10) == P(go, 0x10)))
                  ? 0
              : !strcmp(name, "Turret")    ? 1
              : !strcmp(name, "Unit Info") ? 2
                                           : -1;
      if (k >= 0) {
        hatch_set(box, "set_size", t->disk.boxes + k * 6);
        hatch_set(box, "set_center", t->disk.boxes + k * 6 + 3);
        box_mask |= 1u << k;
      }
    }
  if (box_mask != 7)
    return hatch_fail("Required collision regions missing");
  const char *track_classes[] = {"RealTrackMove", "Mesh", "MeshFilter"};
  const char *track_fields[] = {"rTrackMoves", "sTrackMeshes",
                                "sTrackMeshFilters"};
  for (int k = 0; k < 3; k++) {
    void *c = hatch_class(k ? "UnityEngine" : "", track_classes[k]);
    if (c)
      hatch_field(status, track_fields[k], ha_array(c, 0));
  }

  return !hatch_engine_error;
}
