#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../native/hatch_data.h"

static void check(const unsigned char *original, size_t size, int mode) {
    size_t length = mode == 1 ? size - sizeof(HatchDiskOptions) : size;
    unsigned char *bytes = malloc(length);
    memcpy(bytes, original, length);
    uint32_t total = (uint32_t)length;
    memcpy(bytes + 12, &total, 4);
    HatchDiskOptions *options = (HatchDiskOptions *)(bytes + length - 20);
    // Modify through aligned copies: image payloads need not end on 4 bytes.
    HatchDiskOptions copy;
    memcpy(&copy, options, sizeof(copy));
    if (mode == 2) copy.ballistics = 2;
    if (mode == 3) copy.turret_speed = NAN;
    if (mode == 4) copy.turret_speed = 0;
    if (mode == 5) copy.size = 19;
    if (mode == 6) copy.magic[0] = 'X';
    if (mode >= 2) memcpy(options, &copy, sizeof(copy));
    HatchTank tank;
    int loaded = hatch_parse(&tank, bytes, length);
    assert(loaded == (mode < 2));
    if (loaded) {
        assert(tank.config.ballistics_profile == (mode ? 0 : 1));
        assert(tank.config.turret_speed_exact == (mode ? 0 : 17.5f));
        assert(tank.config.ammo[0] == 36 && tank.config.ammo[1] == 10 &&
               tank.config.ammo[2] == 16);
        assert(tank.config.shell_penetration[1] == 27);
    }
    hatch_release(&tank);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    FILE *file = fopen(argv[1], "rb");
    assert(file);
    fseek(file, 0, SEEK_END);
    size_t size = (size_t)ftell(file);
    rewind(file);
    unsigned char *bytes = malloc(size);
    assert(fread(bytes, 1, size, file) == size);
    fclose(file);
    for (int mode = 0; mode < 7; mode++) check(bytes, size, mode);
    free(bytes);
    puts("7 options checks passed: requested values, legacy defaults, malformed tails");
}
