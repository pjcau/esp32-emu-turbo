/**
 * GB/GBC Emulator Core — gnuboy adapter
 * Bridges gnuboy to emu_core_t interface.
 */

#ifdef SIM_BUILD

#include "emu_core.h"
#include "rom_check.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../components/gnuboy/gnuboy.h"

static uint16_t g_fb[EMU_SCREEN_W * EMU_SCREEN_H];
static uint16_t g_gb_fb[160 * 144];
static int16_t g_audio_buf[4096];
static int g_audio_samples = 0;
static uint16_t g_buttons = 0;
static int g_initialized = 0;

static void video_callback(void *buf) {
    /* Scale 160×144 → 480×320 centered */
    uint16_t *src = (uint16_t *)buf;
    int src_w = 160, src_h = 144;
    int scale = 2;  /* 2x = 320×288, centered in 480×320 */
    int off_x = (EMU_SCREEN_W - src_w * scale) / 2;
    int off_y = (EMU_SCREEN_H - src_h * scale) / 2;

    memset(g_fb, 0, sizeof(g_fb));
    for (int sy = 0; sy < src_h; sy++) {
        for (int sx = 0; sx < src_w; sx++) {
            uint16_t pixel = src[sy * src_w + sx];
            for (int dy = 0; dy < scale; dy++) {
                for (int dx = 0; dx < scale; dx++) {
                    int px = off_x + sx * scale + dx;
                    int py = off_y + sy * scale + dy;
                    if (px >= 0 && px < EMU_SCREEN_W && py >= 0 && py < EMU_SCREEN_H)
                        g_fb[py * EMU_SCREEN_W + px] = pixel;
                }
            }
        }
    }
}

static void audio_callback(void *buf, size_t length) {
    int samples = length / sizeof(int16_t);
    if (samples > 4096) samples = 4096;
    memcpy(g_audio_buf, buf, samples * sizeof(int16_t));
    g_audio_samples = samples;
}

static int gb_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    printf("[GB] Initializing gnuboy core...\n");

    /* GB_PIXEL_565_LE = native RGB565, GB_AUDIO_MONO_S16 */
    if (gnuboy_init(EMU_AUDIO_RATE, GB_AUDIO_MONO_S16, GB_PIXEL_565_LE,
                    video_callback, audio_callback) != 0) {
        printf("[GB] ERROR: gnuboy_init failed\n");
        return -1;
    }

    gnuboy_set_framebuffer(g_gb_fb);
    gnuboy_set_soundbuffer(g_audio_buf, sizeof(g_audio_buf));

    if (gnuboy_load_rom((const void *)rom, size) != 0) {
        printf("[GB] ERROR: ROM loading failed\n");
        return -1;
    }

    gnuboy_reset(true);
    g_initialized = 1;
    printf("[GB] gnuboy ready: %s (%zuKB)\n", info->title, size / 1024);
    return 0;
}

static int gb_run_frame(void) {
    if (!g_initialized) return -1;
    /* Map input: our bitmask → GB bitmask */
    int pad = 0;
    if (g_buttons & 0x0001) pad |= GB_PAD_UP;
    if (g_buttons & 0x0002) pad |= GB_PAD_DOWN;
    if (g_buttons & 0x0004) pad |= GB_PAD_LEFT;
    if (g_buttons & 0x0008) pad |= GB_PAD_RIGHT;
    if (g_buttons & 0x0010) pad |= GB_PAD_A;
    if (g_buttons & 0x0020) pad |= GB_PAD_B;
    if (g_buttons & 0x0100) pad |= GB_PAD_START;
    if (g_buttons & 0x0200) pad |= GB_PAD_SELECT;
    gnuboy_set_pad(pad);
    gnuboy_run(true);
    return 0;
}

static const uint16_t *gb_get_fb(void) { return g_fb; }

static int gb_get_audio(int16_t *buf, int max) {
    int n = (g_audio_samples > max) ? max : g_audio_samples;
    if (n > 0) memcpy(buf, g_audio_buf, n * sizeof(int16_t));
    g_audio_samples = 0;
    return n;
}

static void gb_set_input(uint16_t b) { g_buttons = b; }
static void gb_reset(void) { if (g_initialized) gnuboy_reset(true); }
static void gb_shutdown(void) {
    if (g_initialized) { gnuboy_free_rom(); g_initialized = 0; }
    printf("[GB] Core shutdown\n");
}

const emu_core_t gb_real_core = {
    .name = "GB (gnuboy)", .native_w = 160, .native_h = 144, .fps = 60,
    .init = gb_init, .run_frame = gb_run_frame, .get_framebuffer = gb_get_fb,
    .get_audio = gb_get_audio, .set_input = gb_set_input,
    .reset = gb_reset, .shutdown = gb_shutdown,
};

const emu_core_t gbc_real_core = {
    .name = "GBC (gnuboy)", .native_w = 160, .native_h = 144, .fps = 60,
    .init = gb_init, .run_frame = gb_run_frame, .get_framebuffer = gb_get_fb,
    .get_audio = gb_get_audio, .set_input = gb_set_input,
    .reset = gb_reset, .shutdown = gb_shutdown,
};

#endif
