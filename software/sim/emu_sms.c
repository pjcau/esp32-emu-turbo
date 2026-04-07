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
    uint16_t palette[256];
    memset(palette, 0, sizeof(palette));
    render_mark_palette_dirty();
    render_copy_palette(palette);

    memset(g_fb, 0, sizeof(g_fb));

    if (bitmap.viewport.w > 0) src_w = bitmap.viewport.w;
    if (bitmap.viewport.h > 0) src_h = bitmap.viewport.h;

    int off_x = (EMU_SCREEN_W - src_w) / 2;
    int off_y = (EMU_SCREEN_H - src_h) / 2;

    for (int y = 0; y < src_h && (off_y + y) < EMU_SCREEN_H; y++) {
        const uint8_t *row = (uint8_t *)bitmap.data + y * bitmap.pitch;
        uint16_t *dst = &g_fb[(off_y + y) * EMU_SCREEN_W + off_x];
        for (int x = 0; x < src_w && (off_x + x) < EMU_SCREEN_W; x++) {
            dst[x] = palette[row[x]];
        }
    }
}

static int emu_sms_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    g_is_gg = (info->platform == PLATFORM_GG);
    printf("[SMS] Initializing smsplus core (%s)...\n", g_is_gg ? "Game Gear" : "Master System");

    int w = g_is_gg ? 160 : 256;
    int h = g_is_gg ? 144 : 192;

    /* Initialize option defaults (sets option.sndrate, option.country, etc.)
     * Must be called BEFORE load_rom/system_poweron since sound_init()
     * reads option.sndrate, not snd.sample_rate directly. */
    system_reset_config();
    option.sndrate = EMU_AUDIO_RATE;

    /* Setup bitmap */
    /* render.c copies (viewport.w + 2*viewport.x) bytes per row to bitmap.data.
     * SMS: w=256, x=14 → copies 284 bytes/row. Pitch MUST be >= 284 or rows overlap
     * and corrupt each other. Use 288 (aligned to 8). */
    /* VDP renders up to 264 scanlines. Buffer must fit: 288 * 300 = safe. */
    g_screen_buf = calloc(288 * 300, 1);
    if (!g_screen_buf) return -1;

    memset(&bitmap, 0, sizeof(bitmap));
    bitmap.data = g_screen_buf;
    bitmap.width = 288;
    bitmap.height = 300;
    bitmap.pitch = 288;
    bitmap.granularity = 1;

    /* Load ROM (calls set_rom_config which sets sms.console, sms.display, etc.) */
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
    if (n > 0 && snd.stream[STREAM_PSG_L] && snd.stream[STREAM_PSG_R]) {
        /* Mix PSG L+R streams to mono (snd.output is not allocated
         * because mixer_callback is NULL; read raw PSG streams instead) */
        for (int i = 0; i < n; i++) {
            buf[i] = (snd.stream[STREAM_PSG_L][i] + snd.stream[STREAM_PSG_R][i]) / 2;
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
