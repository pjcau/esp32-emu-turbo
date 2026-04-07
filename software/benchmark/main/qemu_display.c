/**
 * QEMU virtual RGB display + UART input for interactive mode
 *
 * Display: esp_lcd_qemu_rgb (480x320 RGB565)
 * Input: reads single-char commands from UART stdin
 *   w/s/a/d = D-pad, j/k = A/B, u/i = X/Y
 *   enter = Start, backspace = Select, q/e = L/R
 */

#include <stdio.h>
#include <string.h>
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_rgb.h"
#include "esp_log.h"
#include "driver/uart.h"
#include "bench.h"

static const char *TAG = "QEMU_DISP";
static esp_lcd_panel_handle_t g_panel = NULL;

#define DISP_W 480
#define DISP_H 320

int qemu_display_init(void) {
    esp_lcd_rgb_panel_config_t config = {
        .timings = {
            .h_res = DISP_W,
            .v_res = DISP_H,
            .pclk_hz = 12000000,
            .hsync_back_porch = 0,
            .hsync_front_porch = 0,
            .hsync_pulse_width = 0,
            .vsync_back_porch = 0,
            .vsync_front_porch = 0,
            .vsync_pulse_width = 0,
        },
        .data_width = 16,
        .bits_per_pixel = 16,
        .num_fbs = 1,
        .flags.refresh_on_demand = true,
    };

    esp_err_t ret = esp_lcd_new_rgb_panel(&config, &g_panel);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "RGB panel init failed: %s", esp_err_to_name(ret));
        return -1;
    }

    esp_lcd_panel_init(g_panel);
    ESP_LOGI(TAG, "QEMU RGB display ready: %dx%d", DISP_W, DISP_H);
    return 0;
}

void qemu_display_write(const uint16_t *fb) {
    if (!g_panel || !fb) return;
    esp_lcd_panel_draw_bitmap(g_panel, 0, 0, DISP_W, DISP_H, fb);
}

/* UART non-blocking input → button bitmask */
uint16_t qemu_input_read(void) {
    uint16_t buttons = 0;
    uint8_t ch;

    /* Non-blocking read from stdin (UART0) */
    while (uart_read_bytes(UART_NUM_0, &ch, 1, 0) > 0) {
        switch (ch) {
            case 'w': buttons |= 0x0001; break;  /* UP */
            case 's': buttons |= 0x0002; break;  /* DOWN */
            case 'a': buttons |= 0x0004; break;  /* LEFT */
            case 'd': buttons |= 0x0008; break;  /* RIGHT */
            case 'j': buttons |= 0x0010; break;  /* A */
            case 'k': buttons |= 0x0020; break;  /* B */
            case 'u': buttons |= 0x0040; break;  /* X */
            case 'i': buttons |= 0x0080; break;  /* Y */
            case '\r':
            case '\n': buttons |= 0x0100; break; /* START */
            case 127:
            case 8:  buttons |= 0x0200; break;   /* SELECT (backspace) */
            case 'q': buttons |= 0x0400; break;  /* L */
            case 'e': buttons |= 0x0800; break;  /* R */
        }
    }
    return buttons;
}
