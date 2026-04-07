/**
 * NES Emulator Core — nofrendo adapter
 *
 * Bridges the nofrendo NES emulator to our emu_core_t interface.
 * Handles: ROM loading, palette conversion (indexed→RGB565),
 *          video scaling (256×240 → 480×320), audio, input mapping.
 */

#ifdef SIM_BUILD

#include "emu_core.h"
#include "rom_check.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* nofrendo headers */
#include "../components/nofrendo/nofrendo.h"
#include "../components/nofrendo/nes/nes.h"
#include "../components/nofrendo/nes/input.h"
#include "../components/nofrendo/nes/rom.h"
#include "../components/nofrendo/nes/apu.h"
#include "../components/nofrendo/nes/ppu.h"

/* ── State ───────────────────────────────────────────────── */

static uint16_t g_fb[EMU_SCREEN_W * EMU_SCREEN_H];
static uint16_t g_palette[256];  /* NES palette → RGB565 */
static uint8_t  g_vidbuf[NES_SCREEN_PITCH * NES_SCREEN_HEIGHT];
static uint16_t g_buttons = 0;
static int g_initialized = 0;

/* ── Palette: NES indexed → RGB565 ───────────────────────── */

static void build_palette(void) {
    /* Use nofrendo's built-in palette builder for correct RGB565 conversion */
    uint16_t *pal = (uint16_t *)nofrendo_buildpalette(0, 16);
    if (pal) {
        memcpy(g_palette, pal, 256 * sizeof(uint16_t));
        free(pal);
        printf("[NES] Palette built from nofrendo (256 entries)\n");
    } else {
        /* Fallback: grayscale */
        for (int i = 0; i < 256; i++) {
            uint8_t v = (i & 0x3F) * 4;
            g_palette[i] = ((v >> 3) << 11) | ((v >> 2) << 5) | (v >> 3);
        }
        printf("[NES] WARNING: using fallback grayscale palette\n");
    }
}

/* ── Video: 256×240 indexed → 480×320 RGB565 (nearest neighbor scale) ── */

static int g_blit_count = 0;

static void blit_callback(uint8_t *bmp) {
    memset(g_fb, 0, sizeof(g_fb));
    int off_x = (EMU_SCREEN_W - NES_SCREEN_WIDTH) / 2;
    int off_y = (EMU_SCREEN_H - NES_SCREEN_HEIGHT) / 2;

    for (int y = 0; y < NES_SCREEN_HEIGHT; y++) {
        const uint8_t *src = bmp + y * NES_SCREEN_PITCH + NES_SCREEN_OVERDRAW;
        uint16_t *dst = &g_fb[(off_y + y) * EMU_SCREEN_W + off_x];
        for (int x = 0; x < NES_SCREEN_WIDTH; x++) {
            dst[x] = g_palette[src[x]];
        }
    }
}

/* ── Input mapping: our BTN_MASK → NES_PAD ────────────── */

static int map_input(uint16_t buttons) {
    int nes_pad = 0;
    if (buttons & 0x0001) nes_pad |= NES_PAD_UP;
    if (buttons & 0x0002) nes_pad |= NES_PAD_DOWN;
    if (buttons & 0x0004) nes_pad |= NES_PAD_LEFT;
    if (buttons & 0x0008) nes_pad |= NES_PAD_RIGHT;
    if (buttons & 0x0010) nes_pad |= NES_PAD_A;
    if (buttons & 0x0020) nes_pad |= NES_PAD_B;
    /* 0x0040 = X, 0x0080 = Y — NES doesn't have these, map to A/B */
    if (buttons & 0x0040) nes_pad |= NES_PAD_A;   /* X → A (turbo) */
    if (buttons & 0x0080) nes_pad |= NES_PAD_B;   /* Y → B (turbo) */
    if (buttons & 0x0100) nes_pad |= NES_PAD_START;
    if (buttons & 0x0200) nes_pad |= NES_PAD_SELECT;
    /* L/R not used on NES */
    return nes_pad;
}

/* ── emu_core_t implementation ───────────────────────────── */

static int nes_core_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    printf("[NES] Initializing nofrendo core...\n");

    build_palette();
    memset(g_fb, 0, sizeof(g_fb));
    memset(g_vidbuf, 0, sizeof(g_vidbuf));

    /* Init NES system */
    nes_t *nes = nes_init(SYS_NES_NTSC, EMU_AUDIO_RATE, false, NULL);
    if (!nes) {
        printf("[NES] ERROR: nes_init failed\n");
        return -1;
    }

    /* Load ROM from memory */
    rom_t *cart = rom_loadmem((uint8_t *)rom, size);
    if (!cart) {
        printf("[NES] ERROR: ROM loading failed\n");
        nes_shutdown();
        return -1;
    }

    if (nes_insertcart(cart) != 0) {
        printf("[NES] ERROR: cart insertion failed\n");
        nes_shutdown();
        return -1;
    }

    /* Set vidbuf and blit AFTER insertcart — nes_reset() clears vidbuf to NULL */
    nes_setvidbuf(g_vidbuf);
    nes->blit_func = blit_callback;

    /* Connect joypad */
    input_connect(0, NES_JOYPAD);

    g_initialized = 1;
    printf("[NES] nofrendo ready: %s (%zuKB)\n", info->title, size / 1024);
    return 0;
}

static int nes_core_run_frame(void) {
    if (!g_initialized) return -1;

    nes_t *nes = nes_getptr();
    if (!nes) return -1;

    /* Update input */
    input_update(0, map_input(g_buttons));

    /* Run one frame (calls blit_callback with video data) */
    nes_emulate(true);

    return 0;
}

static const uint16_t *nes_core_get_fb(void) {
    return g_fb;
}

static int nes_core_get_audio(int16_t *buf, int max_samples) {
    if (!g_initialized) return 0;

    nes_t *nes = nes_getptr();
    if (!nes || !nes->apu) return 0;

    int samples = nes->apu->samples_per_frame;
    if (samples > max_samples) samples = max_samples;
    if (samples > 0 && nes->apu->buffer) {
        memcpy(buf, nes->apu->buffer, samples * sizeof(int16_t));
    }
    return samples;
}

static void nes_core_set_input(uint16_t buttons) {
    g_buttons = buttons;
}

static void nes_core_reset(void) {
    if (g_initialized) nes_reset(true);
}

static void nes_core_shutdown(void) {
    if (g_initialized) {
        nes_shutdown();
        g_initialized = 0;
        printf("[NES] Core shutdown\n");
    }
}

/* ── Exported core definition ────────────────────────────── */

const emu_core_t nes_real_core = {
    .name = "NES (nofrendo)",
    .native_w = 256,
    .native_h = 240,
    .fps = 60,
    .init = nes_core_init,
    .run_frame = nes_core_run_frame,
    .get_framebuffer = nes_core_get_fb,
    .get_audio = nes_core_get_audio,
    .set_input = nes_core_set_input,
    .reset = nes_core_reset,
    .shutdown = nes_core_shutdown,
};

#endif
