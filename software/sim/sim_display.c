/**
 * Display driver — SDL2 simulator implementation
 * Implements the same API as main/display.h using SDL2
 */

#ifdef SIM_BUILD

#include "sim_hal.h"
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* RGB565 helper */
#define RGB565(r, g, b) ((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3))

static int g_display_ok = 0;

int display_sim_init(void) {
    if (sim_display_init() != 0) return -1;
    g_display_ok = 1;
    printf("[DISPLAY] ILI9488 simulator: %dx%d RGB565\n", SIM_LCD_WIDTH, SIM_LCD_HEIGHT);
    return 0;
}

void display_sim_fill(uint16_t color) {
    if (!g_display_ok) return;
    uint16_t row[SIM_LCD_WIDTH];
    for (int x = 0; x < SIM_LCD_WIDTH; x++) row[x] = color;
    for (int y = 0; y < SIM_LCD_HEIGHT; y++) {
        sim_display_write(row, 0, y, SIM_LCD_WIDTH, 1);
    }
}

void display_sim_draw_rect(int x, int y, int w, int h, uint16_t color) {
    if (!g_display_ok) return;
    uint16_t row[SIM_LCD_WIDTH];
    int cw = (w > SIM_LCD_WIDTH) ? SIM_LCD_WIDTH : w;
    for (int i = 0; i < cw; i++) row[i] = color;
    for (int r = y; r < y + h && r < SIM_LCD_HEIGHT; r++) {
        sim_display_write(row, x, r, cw, 1);
    }
}

int display_sim_draw_color_bars(void) {
    if (!g_display_ok) return -1;
    static const uint16_t colors[] = {
        RGB565(255,0,0), RGB565(0,255,0), RGB565(0,0,255), RGB565(255,255,255),
        RGB565(0,0,0), RGB565(0,255,255), RGB565(255,0,255), RGB565(255,255,0),
    };
    int bar_w = SIM_LCD_WIDTH / 8;
    for (int i = 0; i < 8; i++) {
        display_sim_draw_rect(i * bar_w, 0, bar_w, SIM_LCD_HEIGHT, colors[i]);
    }
    sim_display_flush();
    return 0;
}

void display_sim_flush(void) {
    if (g_display_ok) sim_display_flush();
}

void display_sim_write_pixels(const uint16_t *pixels, int x, int y, int w, int h) {
    if (g_display_ok) sim_display_write(pixels, x, y, w, h);
}

#endif
