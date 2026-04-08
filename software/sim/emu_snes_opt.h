/**
 * SNES Optimization Profiles for ESP32-S3
 *
 * The ESP32-S3 at 240MHz with 8MB PSRAM faces tight constraints
 * running snes9x. These profiles trade quality for performance.
 *
 * Usage: select a profile at init time based on ROM complexity.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    const char *name;

    /* Frameskip: 0 = none, 1 = render every other, 2 = render 1/3, etc. */
    int frameskip;

    /* Audio: disable to save ~15-20% CPU */
    bool audio_enabled;

    /* Audio sample rate: lower = less CPU. 16000 is intelligible. */
    int audio_rate;

    /* APU Shutdown: aggressively skip idle APU cycles */
    bool apu_shutdown;

    /* CPU Shutdown: skip idle 65C816 cycles */
    bool cpu_shutdown;

    /* Hi-res mode: false = always render at 256px width (saves ~30% in Mode 5/6 games) */
    bool hires_enabled;

    /* Transparency: false = skip color math (saves ~10-15% in heavy scenes) */
    bool transparency;

    /* Render height: 224 for NTSC, can reduce to 192 to skip bottom scanlines */
    int render_height;

    /* Max ROM size in KB (ESP32 has 8MB PSRAM, but need room for buffers) */
    int max_rom_kb;
} snes_profile_t;

/* Profile: Maximum quality (PC simulator, no constraints) */
static const snes_profile_t SNES_PROFILE_FULL = {
    .name = "Full Quality",
    .frameskip = 0,
    .audio_enabled = true,
    .audio_rate = 32000,
    .apu_shutdown = true,
    .cpu_shutdown = true,
    .hires_enabled = true,
    .transparency = true,
    .render_height = 224,
    .max_rom_kb = 6144,  /* 6MB */
};

/* Profile: Balanced (ESP32 target — good tradeoff) */
static const snes_profile_t SNES_PROFILE_BALANCED = {
    .name = "Balanced (ESP32)",
    .frameskip = 1,          /* Render every other frame = 30fps effective */
    .audio_enabled = true,
    .audio_rate = 16000,     /* Half sample rate */
    .apu_shutdown = true,
    .cpu_shutdown = true,
    .hires_enabled = false,  /* Force 256px width */
    .transparency = true,    /* Keep transparency for visual quality */
    .render_height = 224,
    .max_rom_kb = 4096,      /* 4MB — covers most games */
};

/* Profile: Performance (ESP32 — max speed, reduced quality) */
static const snes_profile_t SNES_PROFILE_FAST = {
    .name = "Performance (ESP32)",
    .frameskip = 2,          /* Render every 3rd frame = 20fps effective */
    .audio_enabled = false,  /* No audio */
    .audio_rate = 0,
    .apu_shutdown = true,
    .cpu_shutdown = true,
    .hires_enabled = false,
    .transparency = false,   /* Skip color math */
    .render_height = 224,
    .max_rom_kb = 4096,
};

/* Profile: Turbo (ESP32 — stress games like Star Fox, Yoshi's Island) */
static const snes_profile_t SNES_PROFILE_TURBO = {
    .name = "Turbo (ESP32)",
    .frameskip = 3,          /* Render every 4th frame */
    .audio_enabled = false,
    .audio_rate = 0,
    .apu_shutdown = true,
    .cpu_shutdown = true,
    .hires_enabled = false,
    .transparency = false,
    .render_height = 192,    /* Skip bottom scanlines */
    .max_rom_kb = 3072,      /* 3MB */
};

/**
 * Select profile based on ROM properties.
 * Can be called after ROM header is parsed.
 */
static inline const snes_profile_t *snes_select_profile(
    uint32_t rom_size, bool has_superfx, bool has_sa1, bool is_esp32)
{
    if (!is_esp32) return &SNES_PROFILE_FULL;

    /* SuperFX/SA-1 games are the heaviest */
    if (has_superfx || has_sa1) return &SNES_PROFILE_TURBO;

    /* Large ROMs (>2MB) tend to be more demanding */
    if (rom_size > 2 * 1024 * 1024) return &SNES_PROFILE_BALANCED;

    /* Default ESP32 profile */
    return &SNES_PROFILE_BALANCED;
}
