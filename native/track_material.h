#pragma once

typedef struct {
  float x, y;
} TrackOffset;
static int track_texture_property, track_texture_property_ready;

static int track_set_offset(void *material, float offset) {
  if (!track_texture_property_ready) {
    void *shader = hatch_class("UnityEngine", "Shader");
    void *method_info = shader ? class_method(shader, "PropertyToID", 1) : 0;
    if (!method_info || !ha_string)
      return 0;
    track_texture_property = ((int (*)(void *, const void *))P(method_info, 0))(
        ha_string("_MainTex"), method_info);
    track_texture_property_ready = 1;
  }
  // 5.1.0 retains the int/Vector2 implementation, but strips mainTextureOffset.
  void *method_info = method(material, "SetTextureOffsetImpl", 2);
  if (!method_info)
    return 0;
  ((void (*)(void *, int, TrackOffset, const void *))P(method_info, 0))(
      material, track_texture_property, (TrackOffset){0, offset}, method_info);
  return 1;
}
