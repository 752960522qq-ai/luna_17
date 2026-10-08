#pragma once

// Optional tail on the version-one runtime. Older packages have no tail and
// retain physical ballistics and integer turret speeds.
#define HATCH_OPTIONS_MAGIC "HATCHOPT"
enum { HATCH_BALLISTICS_PHYSICAL, HATCH_BALLISTICS_STOCK_TEMPLATE };
enum { HATCH_VEHICLE_TANK, HATCH_VEHICLE_TD, HATCH_VEHICLE_TOWED };
typedef struct {
    char magic[8];
    uint32_t size, ballistics;
    float turret_speed;
} HatchDiskOptions;

static int hatch_read_options(CustomTank *config, const unsigned char *bytes,
                              size_t length) {
    if (!length) return 1;
    if (length != sizeof(HatchDiskOptions) && length != 28)
        return hatch_fail("Invalid Hatch options length");
    HatchDiskOptions options;
    memcpy(&options, bytes, sizeof(options));
    if (memcmp(options.magic, HATCH_OPTIONS_MAGIC, 8) ||
        options.size != length ||
        options.ballistics > HATCH_BALLISTICS_STOCK_TEMPLATE ||
        !isfinite(options.turret_speed) || options.turret_speed < 1 ||
        options.turret_speed > 90)
        return hatch_fail("Invalid Hatch options");
    if (length == 28) {
        uint32_t kind; int32_t angle;
        memcpy(&kind, bytes + 20, 4); memcpy(&angle, bytes + 24, 4);
        if (kind > HATCH_VEHICLE_TOWED || (kind && (angle < 1 || angle > 180)) || (!kind && angle))
            return hatch_fail("Invalid vehicle kind or horizontal traverse");
        config->vehicle_kind = kind; config->traverse_half_angle = angle;
    }
    config->ballistics_profile = options.ballistics;
    config->turret_speed_exact = options.turret_speed;
    return 1;
}
