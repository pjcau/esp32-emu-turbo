/**
 * Emulator Core Interface — generic API for all platforms
 *
 * Each platform implements these functions. The launcher calls them
 * identically regardless of the emulated system.
 */

#pragma once

#include <stdint.h>
#include <stddef.h>
#include "rom_check.h"

#define EMU_SCREEN_W  480  /* output display width */
#define EMU_SCREEN_H  320  /* output display height */
#define EMU_AUDIO_RATE 32000
#define EMU_AUDIO_BUF  1024

typedef struct {
    const char *name;          /* "NES", "SNES", etc. */
    int native_w, native_h;   /* native resolution (e.g. 256x240 for NES) */
    int fps;                   /* target framerate */

    /** Initialize emulator with ROM data. Returns 0 on success. */
    int (*init)(const uint8_t *rom, size_t size, const rom_info_t *info);

    /** Run one frame. Returns 0 on success, -1 on error. */
    int (*run_frame)(void);

    /** Get framebuffer (RGB565, EMU_SCREEN_W × EMU_SCREEN_H) */
    const uint16_t *(*get_framebuffer)(void);

    /** Get audio samples produced this frame (signed 16-bit PCM) */
    int (*get_audio)(int16_t *buf, int max_samples);

    /** Set button state (bitmask matching BTN_MASK_*) */
    void (*set_input)(uint16_t buttons);

    /** Reset the emulator */
    void (*reset)(void);

    /** Shutdown and free resources */
    void (*shutdown)(void);
} emu_core_t;

/** Get the emulator core for a given platform. NULL if unsupported. */
const emu_core_t *emu_get_core(platform_t platform);
