/*
 * ESP32 Emu Turbo — Display Driver
 * ST7796S 320x480, 8-bit 8080 parallel interface via esp_lcd
 */

#pragma once

#include "esp_err.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"

/**
 * Initialize the display: i80 bus, ST7796S panel, and backlight PWM.
 * After init the screen is cleared to black with backlight on.
 */
esp_err_t display_init(void);

/**
 * Draw vertical color bars (red, green, blue, white, black, cyan, magenta, yellow)
 * across the full screen. Useful for validating the data bus wiring.
 */
esp_err_t display_draw_color_bars(void);

/**
 * Fill the entire screen with a single RGB565 color.
 */
esp_err_t display_fill(uint16_t color);

/**
 * Set backlight brightness (0 = off, 255 = max).
 */
void display_set_backlight(uint8_t brightness);

/**
 * Get the panel handle for direct drawing via esp_lcd_panel_draw_bitmap().
 */
esp_lcd_panel_handle_t display_get_panel(void);
