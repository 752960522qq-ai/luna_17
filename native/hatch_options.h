#pragma once

// Optional tail on the version-one runtime. Older packages have no tail and
// retain physical ballistics and integer turret speeds.
#define HATCH_OPTIONS_MAGIC "HATCHOPT"
enum { HATCH_BALLISTICS_PHYSICAL, HATCH_BALLISTICS_STOCK_TEMPLATE };
typedef struct {
    char magic[8];
    uint32_t size, ballistics;
    float turret_speed;
} HatchDiskOptions;

static int hatch_read_options(CustomTank *config, const unsigned char *bytes,
                              size_t length) {
    if (!length) return 1;
    if (length != sizeof(HatchDiskOptions))
        return hatch_fail("Invalid Hatch options length");
    HatchDiskOptions options;
    memcpy(&options, bytes, sizeof(options));
    if (memcmp(options.magic, HATCH_OPTIONS_MAGIC, 8) ||
        options.size != sizeof(options) ||
        options.ballistics > HATCH_BALLISTICS_STOCK_TEMPLATE ||
        !isfinite(options.turret_speed) || options.turret_speed < 1 ||
        options.turret_speed > 90)
        return hatch_fail("Invalid Hatch options");
    config->ballistics_profile = options.ballistics;
    config->turret_speed_exact = options.turret_speed;
    return 1;
}
