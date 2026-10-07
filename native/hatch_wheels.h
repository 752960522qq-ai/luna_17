#pragma once

// Rigid wheels rotate around local X. Read their exported radial geometry so
// smaller sprockets do not inherit the roadwheels' angular velocity.
static struct { void *transform; float radius; } hatch_wheel_sizes[28];
static unsigned hatch_wheel_size_count;

static float hatch_mesh_wheel_radius(const HatchTank *tank, uint32_t wheel) {
    float squared = 0;
    for (uint32_t i = 0; i < tank->node_count; i++) {
        const HatchNode *mesh = tank->nodes + i;
        const HatchDiskNode *node = mesh->disk;
        if ((i != wheel && node->parent != (int32_t)wheel) || !node->vertices)
            continue;
        for (uint32_t v = 0; v < node->vertices; v++) {
            const float *point = mesh->vertices + v*8;
            float y = point[1]*node->scale[1], z = point[2]*node->scale[2];
            float r = y*y + z*z;
            if (r > squared) squared = r;
        }
    }
    float radius = sqrtf(squared);
    return radius >= .05f && radius <= 2.f ? radius : tank->config.radius;
}

static void hatch_cache_wheel_sizes(const HatchTank *tank, void **transforms) {
    hatch_wheel_size_count = 0;
    for (uint32_t i = 0; i < tank->node_count; i++) {
        if (!(tank->nodes[i].disk->flags & (16 | 512))) continue;
        if (hatch_wheel_size_count >= 28) break;
        unsigned at = hatch_wheel_size_count++;
        hatch_wheel_sizes[at].transform = transforms[i];
        hatch_wheel_sizes[at].radius = hatch_mesh_wheel_radius(tank, i);
    }
}

static float hatch_wheel_radius(void *transform, float fallback) {
    for (unsigned i = 0; i < hatch_wheel_size_count; i++)
        if (hatch_wheel_sizes[i].transform == transform)
            return hatch_wheel_sizes[i].radius;
    return fallback;
}
