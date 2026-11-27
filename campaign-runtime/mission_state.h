#pragma once
#include <math.h>
#include <stdbool.h>
/* Use scaled game time. Do not touch health, permanent crew loss, or destroyed
 * vehicles. */
typedef struct {
  float begin, free_until;
  bool tracking;
} AimHold;
static inline bool expired_hold(AimHold *h, bool active, float now,
                                float limit) {
  if (!active) {
    h->tracking = false;
    return false;
  }
  if (now < h->free_until)
    return true;
  if (!h->tracking || now < h->begin) {
    h->begin = now;
    h->tracking = true;
  }
  if (now - h->begin < limit)
    return false;
  h->tracking = false;
  h->free_until = now + 2.f;
  return true;
}
