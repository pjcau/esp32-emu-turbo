/**
 * ESP32 Emu Turbo — Simulator HAL (Hardware Abstraction Layer)
 *
 * Maps ESP32 peripherals to SDL2 for desktop simulation:
 *   - ILI9488 display → SDL2 window (480×320)
 *   - 12 buttons → keyboard input
 *   - I2S audio → SDL2 audio output
 *   - SD card → host filesystem
 *
 * Build with: -DSIM_BUILD=1 to activate simulator HAL
 */

#pragma once

#ifdef SIM_BUILD

#ifdef __APPLE__
#include <SDL.h>
#else
#include <SDL2/SDL.h>
#endif
#include <stdint.h>
#include <stdbool.h>

/* ── Display ─────────────────────────────────────────────── */

#define SIM_LCD_WIDTH   480
#define SIM_LCD_HEIGHT  320

/** Initialize SDL2 window for display */
int sim_display_init(void);

/** Write pixel data to display (RGB565 format) */
void sim_display_write(const uint16_t *pixels, int x, int y, int w, int h);

/** Flush display (present to screen) */
void sim_display_flush(void);

/** Destroy display */
void sim_display_destroy(void);

/* ── Buttons ─────────────────────────────────────────────── */

/**
 * Button bitmask (matches board_config.h BTN_MASK_*)
 *
 * Keyboard mapping:
 *   W/A/S/D  = UP/LEFT/DOWN/RIGHT
 *   J/K      = A/B
 *   U/I      = X/Y
 *   Enter    = START
 *   Backspace = SELECT
 *   Q/E      = L/R
 */
#define SIM_BTN_UP      (1 << 0)
#define SIM_BTN_DOWN    (1 << 1)
#define SIM_BTN_LEFT    (1 << 2)
#define SIM_BTN_RIGHT   (1 << 3)
#define SIM_BTN_A       (1 << 4)
#define SIM_BTN_B       (1 << 5)
#define SIM_BTN_X       (1 << 6)
#define SIM_BTN_Y       (1 << 7)
#define SIM_BTN_START   (1 << 8)
#define SIM_BTN_SELECT  (1 << 9)
#define SIM_BTN_L       (1 << 10)
#define SIM_BTN_R       (1 << 11)

/** Poll button state (returns bitmask) */
uint16_t sim_buttons_read(void);

/** Check if quit requested (window close or ESC) */
bool sim_quit_requested(void);

/* ── Audio ───────────────────────────────────────────────── */

#define SIM_AUDIO_RATE   32000
#define SIM_AUDIO_BITS   16
#define SIM_AUDIO_CHANNELS 1

/** Initialize SDL2 audio output */
int sim_audio_init(void);

/** Queue audio samples (signed 16-bit PCM) */
void sim_audio_write(const int16_t *samples, int count);

/** Destroy audio */
void sim_audio_destroy(void);

/* ── SD Card (host filesystem) ───────────────────────────── */

#define SIM_SD_MOUNT "/project/roms"

/** Initialize SD card (just verify mount dir exists) */
int sim_sd_init(void);

/* ── Main loop ───────────────────────────────────────────── */

/** Initialize all simulator subsystems */
int sim_init(void);

/** Process events (call every frame) */
void sim_poll_events(void);

/** Shutdown all subsystems */
void sim_shutdown(void);

#endif /* SIM_BUILD */
