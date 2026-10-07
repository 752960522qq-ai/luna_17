#pragma once
// Rotate about the local axle without converting through Euler angles.
// Unity's Euler decomposition changes branches as X crosses 90 degrees.
static void rotate_wheel(void *wheel, float radians) {
    void *get = method(wheel, "get_localRotation", 0);
    void *set = method(wheel, "set_localRotation", 1);
    if (!get || !set || !isfinite(radians)) return;
    Quat q = ((Quat (*)(void *, const void *))P(get, 0))(wheel, get);
    float s = sinf(radians * .5f), c = cosf(radians * .5f);
    Quat next = {q.x*c + q.w*s, q.y*c + q.z*s,
                 q.z*c - q.y*s, q.w*c - q.x*s};
    float norm = next.x*next.x + next.y*next.y + next.z*next.z + next.w*next.w;
    if (!isfinite(norm) || norm < .0001f) return;
    float inverse = 1.f / __builtin_sqrtf(norm);
    next.x *= inverse; next.y *= inverse;
    next.z *= inverse; next.w *= inverse;
    ((void (*)(void *, Quat, const void *))P(set, 0))(wheel, next, set);
}
