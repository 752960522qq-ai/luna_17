#pragma once

static char enemy_catalog[6][MAX_TANKS][112];
static volatile int enemy_count[6], enemy_pending = -1, enemy_result, enemy_request_lock;
static void *enemy_source[6];

static void build_enemy_catalog(void *generator) {
    for (int nation = 0; nation < 6; ++nation) {
        void *array = P(generator, 0x60 + nation * 8);
        int count = array ? I(array, 0x18) : 0;
        if (count < 0 || count > MAX_TANKS) count = 0;
        if (enemy_source[nation] == array && enemy_count[nation] == count) continue;
        __atomic_store_n(&enemy_count[nation], 0, __ATOMIC_RELEASE);
        for (int i = 0; i < count; ++i) {
            void *prefab = P(array, 0x20 + i * 8);
            void *m = method(prefab, "get_name", 0);
            void *name = m ? ((void *(*)(void *, const void *))P(m, 0))(prefab, m) : 0;
            utf8_name(name, enemy_catalog[nation][i], sizeof(enemy_catalog[nation][i]));
            if (!enemy_catalog[nation][i][0]) snprintf(enemy_catalog[nation][i], 112, "AI #%d", i + 1);
        }
        enemy_source[nation] = array;
        __atomic_store_n(&enemy_count[nation], count, __ATOMIC_RELEASE);
    }
}

// Use a local exception channel: a failed spawn must not poison tank imports.
static void *enemy_invoke(void *m, void *object, void **args, int *error) {
    if (!m) { *error = -2; return 0; }
    void *exception = 0;
    void *result = ha_invoke(m, object, args, &exception);
    if (exception) *error = -2;
    return result;
}
static __attribute__((noinline)) void *enemy_status(void *go, int *error) {
    void *type = hatch_type_object(hatch_class("", "UnitStatus"));
    bool inactive = true;
    void *args[] = {type, &inactive};
    void *m = type ? hatch_method(P(go, 0), "GetComponentInChildren", 2, hatch_class("System", "Type")) : 0;
    return enemy_invoke(m, go, args, error);
}
static int enemy_own_collider(void *collider, int *error) {
    void *transform = enemy_invoke(method(collider, "get_transform", 0), collider, 0, error);
    if (*error || !unity_exists(transform) || !unity_exists(player_control)) return 0;
    void *player = P(player_control, FIELD_PLAYERCONTROL_THISTRF);
    if (transform == player) return 1;
    void *args[] = {player};
    void *answer = enemy_invoke(method(transform, "IsChildOf", 1), transform, args, error);
    return answer && B(answer, 0x10);
}

typedef struct { Vec3 origin, direction; } EnemyRay;
typedef struct { Vec3 point, normal; unsigned face; float distance, uv[2]; int collider; } EnemyHit;

static __attribute__((noinline)) int enemy_target_point(void *game, Vec3 *point, Vec3 *direction) {
    int error = 0;
    void *control = P(game, FIELD_GAMECONTROL_MCAMCTRL);
    void *camera = unity_exists(control) ? P(control, 0x28) : 0;
    if (!unity_exists(camera)) return -2;
    void *screen = hatch_class("UnityEngine", "Screen");
    if (!screen) return -2;
    void *w = enemy_invoke(class_method(screen, "get_width", 0), 0, 0, &error);
    void *h = enemy_invoke(class_method(screen, "get_height", 0), 0, 0, &error);
    if (error || !w || !h || I(w, 0x10) <= 0 || I(h, 0x10) <= 0) return -2;
    Vec3 center = {I(w, 0x10) * .5f, I(h, 0x10) * .5f, 0};
    void *args[] = {&center};
    // ViewportPointToRay was stripped from this game's metadata. The retained
    // one-argument ScreenPointToRay overload accepts the actual screen center.
    void *boxed = enemy_invoke(method(camera, "ScreenPointToRay", 1), camera, args, &error);
    if (error || !boxed) return -2;
    EnemyRay ray; memcpy(&ray, (uint8_t *)boxed + 0x10, sizeof(ray));
    float length = sqrtf(ray.direction.x * ray.direction.x + ray.direction.y * ray.direction.y + ray.direction.z * ray.direction.z);
    if (!isfinite(length) || length < .01f || !isfinite(ray.origin.x) || !isfinite(ray.origin.y) || !isfinite(ray.origin.z)) return -2;
    ray.direction.x /= length; ray.direction.y /= length; ray.direction.z /= length;
    *direction = ray.direction;
    void *physics = hatch_class("UnityEngine", "Physics");
    void *cast = physics ? class_method(physics, "Raycast", 6) : 0;
    void *hit_class = hatch_class("UnityEngine", "RaycastHit");
    void *get_collider = hit_class ? class_method(hit_class, "get_collider", 0) : 0;
    if (!cast || !get_collider) return -2;
    float remaining = 3000.f;
    int mask = -5, triggers = 1; // Unity default layers, ignore triggers.
    for (int attempt = 0; attempt < 24 && remaining > .01f; ++attempt) {
        EnemyHit hit = {0};
        void *query[] = {&ray.origin, &ray.direction, &hit, &remaining, &mask, &triggers};
        void *answer = enemy_invoke(cast, 0, query, &error);
        if (error) return -2;
        if (!answer || !B(answer, 0x10)) return -3;
        if (!isfinite(hit.distance) || hit.distance < 0 || hit.distance > remaining ||
            !isfinite(hit.point.x) || !isfinite(hit.point.y) || !isfinite(hit.point.z)) return -2;
        void *collider = ((void *(*)(EnemyHit *, const void *))P(get_collider, 0))(&hit, get_collider);
        if (!unity_exists(collider)) return -2;
        if (!enemy_own_collider(collider, &error)) {
            if (error) return error;
            if (!isfinite(hit.normal.y) || hit.normal.y < .3f) return -4;
            *point = hit.point;
            return 1;
        }
        if (error) return error;
        float step = hit.distance + .05f;
        ray.origin.x += ray.direction.x * step;
        ray.origin.y += ray.direction.y * step;
        ray.origin.z += ray.direction.z * step;
        remaining -= step;
    }
    return -3;
}

static __attribute__((noinline)) void spawn_enemy(void *game, int command) {
    int nation = (command >> 16) & 255, index = command & 0xffff;
    void *gen = P(game, FIELD_GAMECONTROL_TANKGENMANAGER);
    if (state != 3 || !unity_exists(gen) || nation > 5 || index >= enemy_count[nation] || swap.new_go) { enemy_result = -1; return; }
    void *array = P(gen, 0x60 + nation * 8);
    if (!array || index >= I(array, 0x18) || array != enemy_source[nation]) { enemy_result = -1; return; }
    Vec3 position, direction;
    int result = enemy_target_point(game, &position, &direction);
    if (result != 1) { enemy_result = result; return; }
    void *prefab = P(array, 0x20 + index * 8);
    int error = 0;
    void *prefab_status = unity_exists(prefab) ? enemy_status(prefab, &error) : 0;
    void *tag = ha_string("AI");
    if (error || !unity_exists(prefab_status) || !tag) { enemy_result = -2; return; }
    float yaw = atan2f(-direction.x, -direction.z) * .5f;
    Quat rotation = {0, sinf(yaw), 0, cosf(yaw)};
    // Start just above the picked surface; physics settles the original AI
    // prefab. Its OnEnable must see an explicit enemy IFF, even for the same
    // country as the player. Restore the shared template immediately.
    position.y += .15f;
    uint8_t saved_iff = B(prefab_status, 0x20);
    B(prefab_status, 0x20) = 2;
    void *go = FN(RVA_1994A88, void *(*)(void *, void *, int, int, Vec3, Quat, bool, const void *))(gen, tag, nation, index, position, rotation, false, 0);
    B(prefab_status, 0x20) = saved_iff;
    if (!unity_exists(go)) { enemy_result = -5; return; }
    void *status = enemy_status(go, &error);
    if (error || !unity_exists(status)) {
        FN(RVA_3431140, void (*)(void *, bool, const void *))(go, false, 0);
        enemy_result = -5; return;
    }
    B(status, 0x20) = 2;
    B(status, 0x202) = 0;
    enemy_result = 1;
}
