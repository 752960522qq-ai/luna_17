#pragma once
#include "hatch_api.h"
#include "hatch_weapons.h"
static void *hatch_objects[2048], *hatch_transforms[2048];
static void *hatch_texture_objects[128];
#include "hatch_controls.h"
static int hatch_apply_tank(HatchTank *t, void *go, void *pc, void *status) {
  if (!hatch_engine_ok)
    return hatch_fail("Hatch embedding API not ready");
  hatch_engine_error = 0;
  void *gameobject = hatch_class("UnityEngine", "GameObject"),
       *meshklass = hatch_class("UnityEngine", "Mesh"),
       *textureklass = hatch_class("UnityEngine", "Texture2D"),
       *materialklass = hatch_class("UnityEngine", "Material"),
       *rendererklass = hatch_class("UnityEngine", "Renderer"),
       *meshfilterklass = hatch_class("UnityEngine", "MeshFilter"),
       *meshrendererklass = hatch_class("UnityEngine", "MeshRenderer"),
       *imageklass = hatch_class("UnityEngine", "ImageConversion"),
       *vector3 = hatch_class("UnityEngine", "Vector3"),
       *vector2 = hatch_class("UnityEngine", "Vector2"),
       *intklass = hatch_class("System", "Int32"),
       *byteklass = hatch_class("System", "Byte"),
       *stringklass = hatch_class("System", "String"),
       *transformklass = hatch_class("UnityEngine", "Transform");
  if (!gameobject || !meshklass || !textureklass || !materialklass ||
      !rendererklass || !meshfilterklass || !meshrendererklass || !imageklass ||
      !vector3 || !vector2 || !intklass || !byteklass || !stringklass ||
      !transformklass)
    return hatch_fail("Required runtime class was stripped");
  void *root = hatch_call(go, "get_transform", 0, 0);
  void *source_material =
      hatch_hide_template_geometry(go, pc, meshrendererklass);
  if (hatch_engine_error || !source_material)
    return 0;
  // Strong managed arrays keep all temporary Unity wrappers rooted during
  // allocations.
  void *volatile texture_roots = ha_array(textureklass, t->image_count),
                 *volatile object_roots = ha_array(gameobject, t->node_count);
  if (!texture_roots || !object_roots)
    return hatch_fail("Cannot allocate model roots");
  for (uint32_t i = 0; i < t->image_count && !hatch_engine_error; i++) {
    int size = 2;
    void *a[] = {&size, &size};
    void *texture = hatch_new(textureklass, 2, a, intklass),
         *data =
             hatch_array_copy(byteklass, t->images[i].bytes, t->images[i].size,
                              1);
    // The three-parameter overload takes ReadOnlySpan<byte>, not byte[].
    if (hatch_engine_error)
      return 0;
    void *load[] = {texture, data};
    void *ok =
        hatch_call_class(imageklass, 0, "LoadImage", 2, load, textureklass);
    if (hatch_engine_error)
      return 0;
    if (!ok || !B(ok, 0x10)) {
      hatch_engine_error = 1;
      snprintf(hatch_error, sizeof(hatch_error),
               "Texture %u decode failed (%u bytes)", i, t->images[i].size);
    }
    hatch_texture_objects[i] = texture;
    managed_store(texture_roots, 0x20 + i * 8, texture);
  }
  for (uint32_t i = 0; i < t->node_count && !hatch_engine_error; i++) {
    void *s = ha_string(t->nodes[i].disk->name);
    void *a[] = {s};
    void *obj = hatch_new(gameobject, 1, a, stringklass);
    hatch_objects[i] = obj;
    managed_store(object_roots, 0x20 + i * 8, obj);
    hatch_transforms[i] = hatch_call(obj, "get_transform", 0, 0);
  }
  void *turret = 0, *gun = 0, *recoil = 0;
  for (uint32_t i = 0; i < t->node_count && !hatch_engine_error; i++) {
    const HatchDiskNode *n = t->nodes[i].disk;
    hatch_parent(hatch_transforms[i],
                 n->parent < 0 ? root : hatch_transforms[n->parent], n->pos,
                 n->rot, n->scale);
    if (n->flags & 2)
      turret = hatch_transforms[i];
    if (n->flags & 4)
      gun = hatch_transforms[i];
    if (n->flags & 8)
      recoil = hatch_transforms[i];
    if (!n->vertices)
      continue;
    const float *v = t->nodes[i].vertices;
    float *positions = malloc(n->vertices * 12),
          *normals = malloc(n->vertices * 12), *uv = malloc(n->vertices * 8);
    if (!positions || !normals || !uv) {
      free(positions);
      free(normals);
      free(uv);
      return hatch_fail("Insufficient mesh memory");
    }
    for (uint32_t j = 0; j < n->vertices; j++) {
      memcpy(positions + j * 3, v + j * 8, 12);
      memcpy(normals + j * 3, v + j * 8 + 3, 12);
      memcpy(uv + j * 2, v + j * 8 + 6, 8);
    }
    // The shipped game strips set_indexFormat; validated meshes fit UInt16.
    void *mesh = hatch_new(meshklass, 0, 0, 0);
    void *posarr = hatch_array_copy(vector3, positions, n->vertices, 12),
         *normarr = hatch_array_copy(vector3, normals, n->vertices, 12),
         *uvarr = hatch_array_copy(vector2, uv, n->vertices, 8),
         *idxarr =
             hatch_array_copy(intklass, t->nodes[i].indices, n->indices, 4);
    free(positions);
    free(normals);
    free(uv);
    hatch_set(mesh, "set_vertices", posarr);
    hatch_set(mesh, "set_normals", normarr);
    hatch_set(mesh, "set_uv", uvarr);
    hatch_set(mesh, "set_triangles", idxarr);
    hatch_call(mesh, "RecalculateBounds", 0, 0);
    void *filter = hatch_component(hatch_objects[i], meshfilterklass);
    hatch_set(filter, "set_sharedMesh", mesh);
    void *renderer = hatch_component(hatch_objects[i], meshrendererklass);
    void *ma[] = {source_material};
    void *mat = hatch_new(materialklass, 1, ma, materialklass);
    hatch_set(mat, "set_color", (void *)n->factor);
    if (n->color >= 0)
      hatch_set(mat, "set_mainTexture", hatch_texture_objects[n->color]);
    if (n->normal >= 0) {
      void *ta[] = {ha_string("_BumpMap"), hatch_texture_objects[n->normal]};
      hatch_call_class(materialklass, mat, "SetTexture", 2, ta, stringklass);
    }
    hatch_set(renderer, "set_sharedMaterial", mat);
  }
  if (hatch_engine_error || !turret || !gun || !recoil)
    return 0;
  if (!hatch_bind_controls(t, go, pc, status, turret, gun, rendererklass,
                           transformklass))
    return 0;
  if (!hatch_bind_weapons(t, pc, root, gun, recoil))
    return 0;
  managed_store(status, 0x68, ha_string(t->disk.id));
  managed_store(status, 0x70, ha_string(t->disk.gun));
  hatch_set(go, "set_name", ha_string(t->disk.id));
  (void)object_roots;
  (void)texture_roots;
  return !hatch_engine_error;
}
