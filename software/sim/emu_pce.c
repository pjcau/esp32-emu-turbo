/**
 * PC Engine Emulator Core — pce-go adapter
 * Bridges pce-go to emu_core_t interface.
 */

#ifdef SIM_BUILD

#include "emu_core.h"
#include "rom_check.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../components/pce-go/pce-go.h"
#include "../components/pce-go/pce.h"

static uint16_t g_fb[EMU_SCREEN_W * EMU_SCREEN_H];
static uint16_t g_buttons = 0;
static int g_initialized = 0;
static uint8_t *g_pce_fb = NULL;
static int g_pce_w = 256, g_pce_h = 240;
static uint16_t g_palette[256];

/* OSD callbacks required by pce-go */
uint8_t *osd_gfx_framebuffer(int width, int height) {
    g_pce_w = width;
    g_pce_h = height;
    if (!g_pce_fb) g_pce_fb = calloc(368 * 242, 1);  /* XBUF_WIDTH × XBUF_HEIGHT */
    return g_pce_fb;
}

void osd_vsync(void) {
    /* Convert palette-indexed → RGB565, scale to 480×320 */
    uint16_t *pal = PalettePCE(16);  /* 16-bit RGB565 palette */
    if (pal) memcpy(g_palette, pal, 256 * sizeof(uint16_t));

    int scale_h = EMU_SCREEN_H;
    int scale_w = (g_pce_w * EMU_SCREEN_H) / g_pce_h;
    if (scale_w > EMU_SCREEN_W) { scale_w = EMU_SCREEN_W; scale_h = (g_pce_h * EMU_SCREEN_W) / g_pce_w; }
    int off_x = (EMU_SCREEN_W - scale_w) / 2;
    int off_y = (EMU_SCREEN_H - scale_h) / 2;

    memset(g_fb, 0, sizeof(g_fb));
    for (int dy = 0; dy < scale_h; dy++) {
        int sy = (dy * g_pce_h) / scale_h;
        for (int dx = 0; dx < scale_w; dx++) {
            int sx = (dx * g_pce_w) / scale_w;
            uint8_t idx = g_pce_fb[sy * 368 + sx];  /* XBUF_WIDTH=368 */
            g_fb[(off_y + dy) * EMU_SCREEN_W + off_x + dx] = g_palette[idx];
        }
    }
}

void osd_input_read(uint8_t joypads[8]) {
    memset(joypads, 0, 8);
    uint8_t pad = 0;
    if (g_buttons & 0x0001) pad |= 0x10;  /* UP */
    if (g_buttons & 0x0002) pad |= 0x40;  /* DOWN */
    if (g_buttons & 0x0004) pad |= 0x80;  /* LEFT */
    if (g_buttons & 0x0008) pad |= 0x20;  /* RIGHT */
    if (g_buttons & 0x0010) pad |= 0x01;  /* A (I) */
    if (g_buttons & 0x0020) pad |= 0x02;  /* B (II) */
    if (g_buttons & 0x0200) pad |= 0x04;  /* SELECT */
    if (g_buttons & 0x0100) pad |= 0x08;  /* START (RUN) */
    joypads[0] = pad;
}

static int pce_core_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    printf("[PCE] Initializing pce-go core...\n");

    if (InitPCE(EMU_AUDIO_RATE, false) != 0) {
        printf("[PCE] ERROR: InitPCE failed\n");
        return -1;
    }

    if (LoadCard((uint8_t *)rom, size) != 0) {
        printf("[PCE] ERROR: ROM loading failed\n");
        ShutdownPCE();
        return -1;
    }

    ResetPCE(true);
    g_initialized = 1;
    printf("[PCE] pce-go ready: %s (%zuKB)\n", info->title, size / 1024);
    return 0;
}

static int pce_core_run_frame(void) {
    if (!g_initialized) return -1;
    pce_run();  /* runs one frame, calls osd_gfx_framebuffer + osd_vsync */
    return 0;
}

static const uint16_t *pce_core_get_fb(void) { return g_fb; }

static int pce_core_get_audio(int16_t *buf, int max) {
    if (!g_initialized) return 0;
    int samples = EMU_AUDIO_RATE / 60;
    if (samples > max) samples = max;
    psg_update(buf, samples, 1);  /* mono */
    return samples;
}

static void pce_core_set_input(uint16_t b) { g_buttons = b; }
static void pce_core_reset(void) { if (g_initialized) ResetPCE(true); }
static void pce_core_shutdown(void) {
    if (g_initialized) { ShutdownPCE(); g_initialized = 0; }
    if (g_pce_fb) { free(g_pce_fb); g_pce_fb = NULL; }
    printf("[PCE] Core shutdown\n");
}

const emu_core_t pce_real_core = {
    .name = "PCE (pce-go)", .native_w = 256, .native_h = 240, .fps = 60,
    .init = pce_core_init, .run_frame = pce_core_run_frame,
    .get_framebuffer = pce_core_get_fb, .get_audio = pce_core_get_audio,
    .set_input = pce_core_set_input, .reset = pce_core_reset,
    .shutdown = pce_core_shutdown,
};

#endif
