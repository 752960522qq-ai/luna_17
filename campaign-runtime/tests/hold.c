#include "../mission_state.h"
#include <assert.h>
int main(void) {
  AimHold h = {0};
  assert(!expired_hold(&h, 1, 15.f, 2.5f));
  assert(!expired_hold(&h, 1, 17.f, 2.5f));
  assert(expired_hold(&h, 1, 17.5f, 2.5f));
  assert(expired_hold(&h, 1, 18.5f, 2.5f));
  assert(!expired_hold(&h, 0, 19.f, 2.5f));
  assert(!expired_hold(&h, 1, 21.f, 2.5f));
  assert(!expired_hold(&h, 1, 21.f, 2.5f));
  assert(!expired_hold(&h, 0, 22.f, 2.5f));
  assert(!expired_hold(&h, 1, 24.f, 5.f));
  assert(!expired_hold(&h, 1, 28.9f, 5.f));
  assert(expired_hold(&h, 1, 29.f, 5.f));
}
