/**
 * ROM Validation — header parsing and integrity checks for all platforms
 */

#pragma once

#include <stdint.h>
#include <stddef.h>

typedef enum {
    PLATFORM_UNKNOWN = 0,
    PLATFORM_NES,
    PLATFORM_SNES,
    PLATFORM_GB,
    PLATFORM_GBC,
    PLATFORM_GEN,    /* Genesis / Mega Drive */
    PLATFORM_SMS,    /* Master System */
    PLATFORM_GG,     /* Game Gear */
    PLATFORM_PCE,    /* PC Engine / TurboGrafx */
} platform_t;

typedef struct {
    platform_t platform;
    char title[64];
    char region[16];
    uint32_t rom_size;
    uint32_t checksum;
    int valid;           /* 1 = header OK, 0 = invalid/corrupt */
    char error[128];     /* error message if invalid */

    /* Platform-specific */
    union {
        struct { int mapper; int prg_size; int chr_size; int mirroring; } nes;
        struct { int rom_type; int ram_size; int has_sram; } snes;
        struct { int cgb_flag; int sgb_flag; int mbc_type; int rom_banks; } gb;
        struct { int system_type; } gen;
    };
} rom_info_t;

/** Detect platform from file extension */
platform_t rom_detect_platform(const char *filename);

/** Parse ROM header and validate integrity */
rom_info_t rom_check(const uint8_t *data, size_t size, const char *filename);

/** Get platform name string */
const char *rom_platform_name(platform_t p);

/** Print ROM info to stdout */
void rom_print_info(const rom_info_t *info);
