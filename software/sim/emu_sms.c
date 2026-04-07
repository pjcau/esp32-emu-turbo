/**
 * SMS/GG Emulator Core — smsplus adapter
 * Bridges smsplus to emu_core_t interface.
 * Handles: Master System (256x192) and Game Gear (160x144).
 */

#ifdef SIM_BUILD

#include "emu_core.h"
#include "rom_check.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../components/smsplus/shared.h"

static uint16_t g_fb[EMU_SCREEN_W * EMU_SCREEN_H];
static uint16_t g_buttons = 0;
static int g_initialized = 0;
static int g_is_gg = 0;
static uint8_t *g_screen_buf = NULL;

static void scale_to_fb(int src_w, int src_h) {
    /* Scale source → 480×320 centered, maintaining aspect ratio */
    int scale_h = EMU_SCREEN_H;
    int scale_w = (src_w * EMU_SCREEN_H) / src_h;
    if (scale_w > EMU_SCREEN_W) {
        scale_w = EMU_SCREEN_W;
        scale_h = (src_h * EMU_SCREEN_W) / src_w;
    }
    int off_x = (EMU_SCREEN_W - scale_w) / 2;
    int off_y = (EMU_SCREEN_H - scale_h) / 2;

    /* Get palette */
    uint16_t palette[256];
    render_copy_palette(palette);

    memset(g_fb, 0, sizeof(g_fb));

    int vp_x = bitmap.viewport.x;
    int vp_y = bitmap.viewport.y;

    for (int dy = 0; dy < scale_h; dy++) {
        int sy = vp_y + (dy * src_h) / scale_h;
        for (int dx = 0; dx < scale_w; dx++) {
            int sx = vp_x + (dx * src_w) / scale_w;
            uint8_t idx = g_screen_buf[sy * bitmap.pitch + sx];
            int px = off_x + dx, py = off_y + dy;
            if (px < EMU_SCREEN_W && py < EMU_SCREEN_H)
                g_fb[py * EMU_SCREEN_W + px] = palette[idx & 0x1F];
        }
    }
}

static int emu_sms_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    g_is_gg = (info->platform == PLATFORM_GG);
    printf("[SMS] Initializing smsplus core (%s)...\n", g_is_gg ? "Game Gear" : "Master System");

    int w = g_is_gg ? 160 : 256;
    int h = g_is_gg ? 144 : 192;

    /* Setup bitmap */
    g_screen_buf = calloc(256 * 240, 1);
    if (!g_screen_buf) return -1;

    memset(&bitmap, 0, sizeof(bitmap));
    bitmap.data = g_screen_buf;
    bitmap.width = 256;
    bitmap.height = 240;
    bitmap.pitch = 256;
    bitmap.granularity = 1;

    /* Setup sound */
    memset(&snd, 0, sizeof(snd));
    snd.sample_rate = EMU_AUDIO_RATE;
    snd.fps = 60;
    snd.fm_clock = 3579545;
    snd.psg_clock = 3579545;

    /* Load ROM */
    if (load_rom((void *)rom, size, size) != 1) {
        printf("[SMS] ERROR: ROM loading failed\n");
        free(g_screen_buf);
        g_screen_buf = NULL;
        return -1;
    }

    system_poweron();
    g_initialized = 1;
    printf("[SMS] smsplus ready: %s (%zuKB)\n", info->title, size / 1024);
    return 0;
}

static int emu_sms_run_frame(void) {
    if (!g_initialized) return -1;

    /* Map input */
    input.pad[0] = 0;
    input.system = 0;
    if (g_buttons & 0x0001) input.pad[0] |= INPUT_UP;
    if (g_buttons & 0x0002) input.pad[0] |= INPUT_DOWN;
    if (g_buttons & 0x0004) input.pad[0] |= INPUT_LEFT;
    if (g_buttons & 0x0008) input.pad[0] |= INPUT_RIGHT;
    if (g_buttons & 0x0010) input.pad[0] |= INPUT_BUTTON1;  /* A */
    if (g_buttons & 0x0020) input.pad[0] |= INPUT_BUTTON2;  /* B */
    if (g_buttons & 0x0100) input.system |= INPUT_START;     /* Start (GG) */
    if (g_buttons & 0x0200) input.system |= INPUT_PAUSE;     /* Select → Pause */

    system_frame(0);

    int vw = bitmap.viewport.w > 0 ? bitmap.viewport.w : (g_is_gg ? 160 : 256);
    int vh = bitmap.viewport.h > 0 ? bitmap.viewport.h : (g_is_gg ? 144 : 192);
    scale_to_fb(vw, vh);
    return 0;
}

static const uint16_t *emu_sms_get_fb(void) { return g_fb; }

static int emu_sms_get_audio(int16_t *buf, int max) {
    int n = snd.sample_count;
    if (n > max) n = max;
    if (n > 0 && snd.output[0]) {
        /* Mix L+R to mono */
        for (int i = 0; i < n; i++) {
            buf[i] = (snd.output[0][i] + snd.output[1][i]) / 2;
        }
    }
    return n;
}

static void emu_sms_set_input(uint16_t b) { g_buttons = b; }
static void emu_sms_reset(void) { if (g_initialized) system_reset(); }
static void emu_sms_shutdown(void) {
    if (g_initialized) {
        system_shutdown();
        if (g_screen_buf) { free(g_screen_buf); g_screen_buf = NULL; }
        g_initialized = 0;
    }
    printf("[SMS] Core shutdown\n");
}

const emu_core_t sms_real_core = {
    .name = "SMS (smsplus)", .native_w = 256, .native_h = 192, .fps = 60,
    .init = emu_sms_init, .run_frame = emu_sms_run_frame, .get_framebuffer = emu_sms_get_fb,
    .get_audio = emu_sms_get_audio, .set_input = emu_sms_set_input,
    .reset = emu_sms_reset, .shutdown = emu_sms_shutdown,
};

const emu_core_t gg_real_core = {
    .name = "GG (smsplus)", .native_w = 160, .native_h = 144, .fps = 60,
    .init = emu_sms_init, .run_frame = emu_sms_run_frame, .get_framebuffer = emu_sms_get_fb,
    .get_audio = emu_sms_get_audio, .set_input = emu_sms_set_input,
    .reset = emu_sms_reset, .shutdown = emu_sms_shutdown,
};

#endif
