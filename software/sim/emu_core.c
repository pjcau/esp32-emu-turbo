/**
 * Emulator Core — stub implementations for all platforms
 *
 * Each core reads the ROM header info, displays a "running" screen
 * with ROM details + animated pattern, and responds to buttons.
 * Replace with real emulator cores (nofrendo, gnuboy, snes9x, etc.)
 * when ready.
 */

#ifdef SIM_BUILD

#include "emu_core.h"
#include "rom_check.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ── Shared framebuffer + state ──────────────────────────── */

static uint16_t g_fb[EMU_SCREEN_W * EMU_SCREEN_H];
static rom_info_t g_rom_info;
static uint16_t g_buttons = 0;
static int g_frame = 0;
static int g_native_w, g_native_h;

#define RGB565(r,g,b) ((((r)>>3)<<11)|(((g)>>2)<<5)|((b)>>3))

/* ── Animated test pattern (platform-specific colors) ──── */

static uint16_t platform_color(platform_t p) {
    switch (p) {
    case PLATFORM_NES:  return RGB565(200, 50, 50);   /* Red */
    case PLATFORM_SNES: return RGB565(100, 50, 200);  /* Purple */
    case PLATFORM_GB:   return RGB565(100, 150, 50);  /* Green */
    case PLATFORM_GBC:  return RGB565(50, 150, 200);  /* Teal */
    case PLATFORM_GEN:  return RGB565(50, 50, 200);   /* Blue */
    case PLATFORM_SMS:  return RGB565(200, 100, 50);  /* Orange */
    case PLATFORM_GG:   return RGB565(200, 200, 50);  /* Yellow */
    case PLATFORM_PCE:  return RGB565(200, 50, 200);  /* Magenta */
    default:            return RGB565(128, 128, 128);
    }
}

static void render_test_frame(void) {
    uint16_t bg = RGB565(20, 20, 30);
    uint16_t accent = platform_color(g_rom_info.platform);

    /* Background */
    for (int i = 0; i < EMU_SCREEN_W * EMU_SCREEN_H; i++) g_fb[i] = bg;

    /* Animated scanline pattern (simulates CRT effect) */
    int scroll = g_frame % EMU_SCREEN_H;
    for (int y = 0; y < EMU_SCREEN_H; y++) {
        int sy = (y + scroll) % EMU_SCREEN_H;
        if (sy % 4 == 0) {
            uint8_t intensity = 40 + (sy * 30 / EMU_SCREEN_H);
            uint16_t line_color = RGB565(intensity/3, intensity/3, intensity);
            for (int x = 0; x < EMU_SCREEN_W; x++) {
                g_fb[y * EMU_SCREEN_W + x] = line_color;
            }
        }
    }

    /* Platform border (native resolution area) */
    int ox = (EMU_SCREEN_W - g_native_w) / 2;
    int oy = (EMU_SCREEN_H - g_native_h) / 2;
    for (int x = ox; x < ox + g_native_w; x++) {
        if (x >= 0 && x < EMU_SCREEN_W) {
            if (oy >= 0) g_fb[oy * EMU_SCREEN_W + x] = accent;
            if (oy + g_native_h - 1 < EMU_SCREEN_H)
                g_fb[(oy + g_native_h - 1) * EMU_SCREEN_W + x] = accent;
        }
    }
    for (int y = oy; y < oy + g_native_h; y++) {
        if (y >= 0 && y < EMU_SCREEN_H) {
            if (ox >= 0) g_fb[y * EMU_SCREEN_W + ox] = accent;
            if (ox + g_native_w - 1 < EMU_SCREEN_W)
                g_fb[y * EMU_SCREEN_W + ox + g_native_w - 1] = accent;
        }
    }

    /* Moving sprite (responds to D-pad) */
    static int sx = 240, sy_pos = 160;
    int speed = 3;
    if (g_buttons & 0x0001) sy_pos -= speed;  /* UP */
    if (g_buttons & 0x0002) sy_pos += speed;  /* DOWN */
    if (g_buttons & 0x0004) sx -= speed;      /* LEFT */
    if (g_buttons & 0x0008) sx += speed;      /* RIGHT */
    if (sx < ox) sx = ox;
    if (sx > ox + g_native_w - 16) sx = ox + g_native_w - 16;
    if (sy_pos < oy) sy_pos = oy;
    if (sy_pos > oy + g_native_h - 16) sy_pos = oy + g_native_h - 16;

    /* Draw 16x16 sprite */
    uint16_t sprite_color = (g_buttons & 0x0010) ? RGB565(255,255,0) : accent;  /* A changes color */
    for (int dy = 0; dy < 16; dy++) {
        for (int dx = 0; dx < 16; dx++) {
            int px = sx + dx, py = sy_pos + dy;
            if (px >= 0 && px < EMU_SCREEN_W && py >= 0 && py < EMU_SCREEN_H) {
                g_fb[py * EMU_SCREEN_W + px] = sprite_color;
            }
        }
    }

    g_frame++;
}

/* ── Core implementations (stub — same for all platforms) ── */

static int stub_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    g_rom_info = *info;
    g_frame = 0;
    g_buttons = 0;
    printf("[EMU] %s core initialized: %s (%uKB)\n",
           rom_platform_name(info->platform), info->title, info->rom_size / 1024);
    printf("[EMU] Native resolution: %dx%d → scaled to %dx%d\n",
           g_native_w, g_native_h, EMU_SCREEN_W, EMU_SCREEN_H);
    return 0;
}

static int stub_run_frame(void) {
    render_test_frame();
    return 0;
}

static const uint16_t *stub_get_fb(void) { return g_fb; }

static int stub_get_audio(int16_t *buf, int max) {
    /* Generate a tone that changes with button presses */
    float freq = 220.0f;
    if (g_buttons & 0x0010) freq = 440.0f;   /* A */
    if (g_buttons & 0x0020) freq = 330.0f;   /* B */
    if (g_buttons & 0x0040) freq = 523.0f;   /* X */
    if (g_buttons & 0x0080) freq = 659.0f;   /* Y */

    int samples = (max > EMU_AUDIO_BUF) ? EMU_AUDIO_BUF : max;
    if (g_buttons == 0) {
        memset(buf, 0, samples * sizeof(int16_t));
    } else {
        static float phase = 0;
        float dt = 1.0f / EMU_AUDIO_RATE;
        for (int i = 0; i < samples; i++) {
            buf[i] = (int16_t)(sinf(phase) * 4000.0f);
            phase += 2.0f * M_PI * freq * dt;
            if (phase > 2.0f * M_PI) phase -= 2.0f * M_PI;
        }
    }
    return samples;
}

static void stub_set_input(uint16_t buttons) { g_buttons = buttons; }
static void stub_reset(void) { g_frame = 0; }
static void stub_shutdown(void) { printf("[EMU] Core shutdown\n"); }

/* ── Core definitions per platform ─────────────────────── */

#define DEFINE_CORE(name_str, w, h, target_fps) \
    static int name_str##_init(const uint8_t *rom, size_t size, const rom_info_t *info) { \
        g_native_w = w; g_native_h = h; return stub_init(rom, size, info); \
    } \
    static const emu_core_t name_str##_core = { \
        .name = #name_str, .native_w = w, .native_h = h, .fps = target_fps, \
        .init = name_str##_init, .run_frame = stub_run_frame, \
        .get_framebuffer = stub_get_fb, .get_audio = stub_get_audio, \
        .set_input = stub_set_input, .reset = stub_reset, .shutdown = stub_shutdown, \
    };

/* Real cores — see emu_*.c adapter files */
extern const emu_core_t nes_real_core;   /* emu_nes.c (nofrendo) */
extern const emu_core_t gb_real_core;    /* emu_gb.c (gnuboy) */
extern const emu_core_t gbc_real_core;   /* emu_gb.c (gnuboy) */
extern const emu_core_t sms_real_core;   /* emu_sms.c (smsplus) */
extern const emu_core_t gg_real_core;    /* emu_sms.c (smsplus) */
extern const emu_core_t pce_real_core;   /* emu_pce.c (pce-go) */
extern const emu_core_t snes_real_core;  /* emu_snes.c (snes9x) */
DEFINE_CORE(snes, 256, 224, 60)
DEFINE_CORE(gb,   160, 144, 60)
DEFINE_CORE(gbc,  160, 144, 60)
DEFINE_CORE(gen,  320, 224, 60)
DEFINE_CORE(sms,  256, 192, 60)
DEFINE_CORE(gg,   160, 144, 60)
DEFINE_CORE(pce,  256, 240, 60)

const emu_core_t *emu_get_core(platform_t platform) {
    switch (platform) {
    case PLATFORM_NES:  return &nes_real_core;
    case PLATFORM_SNES: return &snes_core;   /* stub — snes9x needs ESP-IDF build */
    case PLATFORM_GB:   return &gb_real_core;
    case PLATFORM_GBC:  return &gbc_real_core;
    case PLATFORM_GEN:  return &gen_core;      /* stub — no genesis core yet */
    case PLATFORM_SMS:  return &sms_real_core;
    case PLATFORM_GG:   return &gg_real_core;
    case PLATFORM_PCE:  return &pce_real_core;
    default: return NULL;
    }
}

#endif
