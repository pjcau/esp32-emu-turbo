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

/* Standard NES palette (64 colors, commonly used) */
static const uint32_t nes_rgb[64] = {
    0x666666, 0x002A88, 0x1412A7, 0x3B00A4, 0x5C007E, 0x6E0040, 0x6C0600, 0x561D00,
    0x333500, 0x0B4800, 0x005200, 0x004F08, 0x00404D, 0x000000, 0x000000, 0x000000,
    0xADADAD, 0x155FD9, 0x4240FF, 0x7527FE, 0xA01ACC, 0xB71E7B, 0xB53120, 0x994E00,
    0x6B6D00, 0x388700, 0x0C9300, 0x008F32, 0x007C8D, 0x000000, 0x000000, 0x000000,
    0xFFFEFF, 0x64B0FF, 0x9290FF, 0xC676FF, 0xF36AFF, 0xFF6ECC, 0xFF8170, 0xEA9E22,
    0xBCBE00, 0x88D800, 0x5CE430, 0x45E082, 0x48CDDE, 0x4F4F4F, 0x000000, 0x000000,
    0xFFFEFF, 0xC0DFFF, 0xD3D2FF, 0xE8C8FF, 0xFBC2FF, 0xFEC4EA, 0xFECCC5, 0xF7D8A5,
    0xE4E594, 0xCFEF96, 0xBDF4AB, 0xB3F3CC, 0xB5EBF2, 0xB8B8B8, 0x000000, 0x000000,
};

static void build_palette(void) {
    for (int i = 0; i < 64; i++) {
        uint32_t rgb = nes_rgb[i];
        uint8_t r = (rgb >> 16) & 0xFF;
        uint8_t g = (rgb >> 8) & 0xFF;
        uint8_t b = rgb & 0xFF;
        g_palette[i] = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
    }
    /* Mirror for emphasis bits (palette indices 64-255 → same as 0-63) */
    for (int i = 64; i < 256; i++) {
        g_palette[i] = g_palette[i & 0x3F];
    }
}

/* ── Video: 256×240 indexed → 480×320 RGB565 (nearest neighbor scale) ── */

static int g_blit_count = 0;

static void blit_callback(uint8_t *bmp) {
    g_blit_count++;
    if (g_blit_count <= 3 || g_blit_count % 60 == 0)
        printf("[NES] blit_callback frame %d\n", g_blit_count);

    /* Scale 256×240 → 480×320 with letterboxing
     * Scale factor: 480/256 = 1.875x, 320/240 = 1.333x
     * Use integer scaling: 1x vertically with centering + 1.875x horizontally
     * Actually, let's do proper nearest-neighbor for both axes */

    int src_w = NES_SCREEN_WIDTH;   /* 256 */
    int src_h = NES_SCREEN_HEIGHT;  /* 240 */
    int dst_w = EMU_SCREEN_W;       /* 480 */
    int dst_h = EMU_SCREEN_H;       /* 320 */

    /* Scale to fit: maintain aspect ratio */
    /* NES is 4:3 (256:240 ≈ 1.067:1). Target is 480:320 = 1.5:1 */
    /* Scale by height: 320/240 = 1.333x → width = 256*1.333 = 341 (fits in 480) */
    int scale_h = dst_h;  /* 320 */
    int scale_w = (src_w * dst_h) / src_h;  /* 256 * 320 / 240 = 341 */
    int off_x = (dst_w - scale_w) / 2;  /* (480 - 341) / 2 = 69 */
    int off_y = 0;

    /* Clear borders */
    if (off_x > 0) {
        for (int y = 0; y < dst_h; y++) {
            for (int x = 0; x < off_x; x++)
                g_fb[y * dst_w + x] = 0;
            for (int x = off_x + scale_w; x < dst_w; x++)
                g_fb[y * dst_w + x] = 0;
        }
    }

    /* Nearest-neighbor scale */
    for (int dy = 0; dy < scale_h; dy++) {
        int sy = (dy * src_h) / scale_h;
        const uint8_t *src_row = bmp + sy * NES_SCREEN_PITCH + NES_SCREEN_OVERDRAW;
        uint16_t *dst_row = g_fb + (dy + off_y) * dst_w + off_x;

        for (int dx = 0; dx < scale_w; dx++) {
            int sx = (dx * src_w) / scale_w;
            dst_row[dx] = g_palette[src_row[sx] & 0x3F];
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
