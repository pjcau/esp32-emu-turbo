/**
 * SNES Emulator Core — snes9x adapter
 * Bridges snes9x to emu_core_t interface.
 */

#ifdef SIM_BUILD

#include "emu_core.h"
#include "rom_check.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../components/snes9x/snes9x.h"

/* snes9x globals — declared in snes9x headers as typedefs, not struct */

static uint16_t g_fb[EMU_SCREEN_W * EMU_SCREEN_H];
static uint16_t g_buttons = 0;
static int g_initialized = 0;
static uint8_t *g_gfx_screen = NULL;
static uint8_t *g_gfx_sub = NULL;
static uint8_t *g_zbuf = NULL;
static uint8_t *g_sub_zbuf = NULL;

/* snes9x callback: read joypad */
uint32_t S9xReadJoypad(int32_t port) {
    if (port != 0) return 0;
    uint32_t pad = 0;
    if (g_buttons & 0x0001) pad |= SNES_UP_MASK;
    if (g_buttons & 0x0002) pad |= SNES_DOWN_MASK;
    if (g_buttons & 0x0004) pad |= SNES_LEFT_MASK;
    if (g_buttons & 0x0008) pad |= SNES_RIGHT_MASK;
    if (g_buttons & 0x0010) pad |= SNES_A_MASK;
    if (g_buttons & 0x0020) pad |= SNES_B_MASK;
    if (g_buttons & 0x0040) pad |= SNES_X_MASK;
    if (g_buttons & 0x0080) pad |= SNES_Y_MASK;
    if (g_buttons & 0x0100) pad |= SNES_START_MASK;
    if (g_buttons & 0x0200) pad |= SNES_SELECT_MASK;
    if (g_buttons & 0x0400) pad |= SNES_TL_MASK;   /* L */
    if (g_buttons & 0x0800) pad |= SNES_TR_MASK;   /* R */
    if (pad) pad |= 0xFFFF0000;  /* snes9x convention: set high bits if any button pressed */
    return pad;
}

/* Other required snes9x callbacks (no-ops for simulator) */
bool S9xReadMousePosition(int32_t w, int32_t *x, int32_t *y, uint32_t *b) { return false; }
bool S9xReadSuperScopePosition(int32_t *x, int32_t *y, uint32_t *b) { return false; }
void S9xMessage(int32_t type, int32_t num, const char *msg) { printf("[SNES] %s\n", msg); }
bool S9xOpenSoundDevice(int32_t mode, bool stereo, int32_t rate) { return true; }
void S9xAutoSaveSRAM(void) {}
const char *S9xGetFilename(const char *ext) { static char buf[256]; snprintf(buf, 256, "/tmp/snes9x%s", ext); return buf; }

static int snes_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    printf("[SNES] Initializing snes9x core...\n");

    /* Allocate GFX buffers (512×478×2 for hi-res) */
    size_t fb_size = 512 * 478 * 2;
    g_gfx_screen = calloc(1, fb_size);
    g_gfx_sub = calloc(1, fb_size);
    g_zbuf = calloc(1, 512 * 478);
    g_sub_zbuf = calloc(1, 512 * 478);
    if (!g_gfx_screen || !g_gfx_sub || !g_zbuf || !g_sub_zbuf) {
        printf("[SNES] ERROR: out of memory\n");
        return -1;
    }

    GFX.Screen = g_gfx_screen;
    GFX.SubScreen = g_gfx_sub;
    GFX.ZBuffer = g_zbuf;
    GFX.SubZBuffer = g_sub_zbuf;
    GFX.Pitch = 512 * 2;

    memset(&Settings, 0, sizeof(Settings));
    Settings.Transparency = true;
    Settings.SupportHiRes = false;
    Settings.SoundPlaybackRate = EMU_AUDIO_RATE;
    Settings.Stereo = false;
    Settings.SoundBufferSize = 0;

    if (!S9xInitMemory()) { printf("[SNES] ERROR: InitMemory failed\n"); return -1; }
    if (!S9xInitAPU()) { printf("[SNES] ERROR: InitAPU failed\n"); return -1; }
    if (!S9xInitGFX()) { printf("[SNES] ERROR: InitGFX failed\n"); return -1; }
    S9xInitSound(0, 0);
    S9xSetPlaybackRate(EMU_AUDIO_RATE);

    /* Load ROM from memory */
    if (!LoadROMMem((const uint8_t *)rom, size)) {
        printf("[SNES] ERROR: ROM loading failed\n");
        return -1;
    }

    S9xReset();
    g_initialized = 1;
    printf("[SNES] snes9x ready: %s (%zuKB)\n", info->title, size / 1024);
    return 0;
}

static int snes_run_frame(void) {
    if (!g_initialized) return -1;

    S9xMainLoop();

    /* Scale snes9x framebuffer → 480×320 */
    int src_w = IPPU.RenderedScreenWidth > 0 ? IPPU.RenderedScreenWidth : 256;
    int src_h = IPPU.RenderedScreenHeight > 0 ? IPPU.RenderedScreenHeight : 224;
    int pitch = GFX.RealPitch > 0 ? GFX.RealPitch : 512 * 2;

    int scale_h = EMU_SCREEN_H;
    int scale_w = (src_w * scale_h * 7) / (src_h * 6);  /* 7:6 aspect for SNES 8:7 PAR */
    if (scale_w > EMU_SCREEN_W) { scale_w = EMU_SCREEN_W; scale_h = (src_h * EMU_SCREEN_W * 6) / (src_w * 7); }
    int off_x = (EMU_SCREEN_W - scale_w) / 2;
    int off_y = (EMU_SCREEN_H - scale_h) / 2;

    memset(g_fb, 0, sizeof(g_fb));
    for (int dy = 0; dy < scale_h; dy++) {
        int sy = (dy * src_h) / scale_h;
        uint16_t *src_row = (uint16_t *)(g_gfx_screen + sy * pitch);
        for (int dx = 0; dx < scale_w; dx++) {
            int sx = (dx * src_w) / scale_w;
            g_fb[(off_y + dy) * EMU_SCREEN_W + off_x + dx] = src_row[sx];
        }
    }
    return 0;
}

static const uint16_t *snes_get_fb(void) { return g_fb; }

static int snes_get_audio(int16_t *buf, int max) {
    if (!g_initialized) return 0;
    int samples = EMU_AUDIO_RATE / 60;
    if (samples > max) samples = max;
    S9xMixSamples(buf, samples);
    return samples;
}

static void snes_set_input(uint16_t b) { g_buttons = b; }
static void snes_reset(void) { if (g_initialized) S9xReset(); }
static void snes_shutdown(void) {
    if (g_initialized) {
        S9xDeinitGFX();
        S9xDeinitAPU();
        S9xDeinitMemory();
        g_initialized = 0;
    }
    free(g_gfx_screen); g_gfx_screen = NULL;
    free(g_gfx_sub); g_gfx_sub = NULL;
    free(g_zbuf); g_zbuf = NULL;
    free(g_sub_zbuf); g_sub_zbuf = NULL;
    printf("[SNES] Core shutdown\n");
}

const emu_core_t snes_real_core = {
    .name = "SNES (snes9x)", .native_w = 256, .native_h = 224, .fps = 60,
    .init = snes_init, .run_frame = snes_run_frame, .get_framebuffer = snes_get_fb,
    .get_audio = snes_get_audio, .set_input = snes_set_input,
    .reset = snes_reset, .shutdown = snes_shutdown,
};

#endif
