/*
 * ESP32 Emu Turbo — Audio Driver
 * I2S PDM TX mode → PAM8403 Class-D amplifier → 28mm speaker
 */

#pragma once

#include "esp_err.h"

/**
 * Initialize I2S in PDM TX mode (sigma-delta output).
 * 32 kHz, 16-bit, mono output on GPIO17.
 * The existing RC filter (0.47uF + 20k bias) converts PDM to analog.
 */
esp_err_t audio_init(void);

/**
 * Play a 440 Hz sine wave test tone for the specified duration (ms).
 * Blocks until playback is complete.
 */
esp_err_t audio_play_test_tone(int duration_ms);

/**
 * Stop audio playback and disable the I2S channel.
 */
void audio_stop(void);
