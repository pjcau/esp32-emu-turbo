/*
 * ESP32 Emu Turbo — Input Driver
 * 12 tact buttons, active-low with external 10k pull-up + 100nF RC debounce
 */

#pragma once

#include <stdint.h>
#include "esp_err.h"

/**
 * Configure all 12 button GPIOs as inputs.
 * External pull-ups and debounce capacitors are on the PCB.
 */
esp_err_t input_init(void);

/**
 * Read all button states. Returns a bitmask where 1 = pressed.
 * Use BTN_MASK_* constants from board_config.h to test individual buttons.
 */
uint16_t input_read(void);

/**
 * Get the name of a button from its mask bit position.
 */
const char *input_button_name(int bit);
