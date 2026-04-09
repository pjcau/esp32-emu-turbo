/*
 * ESP32 Emu Turbo — Display Driver
 * ILI9488 320x480, 8-bit 8080 parallel interface via esp_lcd
 *
 * NOTE: ILI9488 in 8-bit parallel mode only supports RGB666 (18-bit color,
 * 3 bytes/pixel). The esp_lcd_ili9488 component handles the RGB565→RGB666
 * conversion internally when bits_per_pixel=16 is specified.
 */

#include "display.h"
#include "board_config.h"

#include "esp_log.h"
#include "esp_check.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_ili9488.h"
#include <string.h>
#include <stdlib.h>

static const char *TAG = "display";

static esp_lcd_panel_handle_t s_panel = NULL;

/* Backlight is hardwired to 3V3 via resistor on PCB — no GPIO control.
 * display_set_backlight() is a no-op for API compatibility. */
void display_set_backlight(uint8_t brightness)
{
    (void)brightness;
    ESP_LOGD(TAG, "Backlight is hardwired ON (no PWM control)");
}

/* ── Panel init ────────────────────────────────────────────────────── */

esp_err_t display_init(void)
{
    ESP_LOGI(TAG, "Initializing ILI9488 8-bit i80 parallel display");

    /* Backlight PWM — start OFF before display init */
    /* Backlight: no init needed (hardwired to 3V3 on PCB) */

    /* Configure the i80 bus */
    esp_lcd_i80_bus_handle_t i80_bus = NULL;
    esp_lcd_i80_bus_config_t bus_cfg = {
        .clk_src     = LCD_CLK_SRC_DEFAULT,
        .dc_gpio_num = LCD_DC,
        .wr_gpio_num = LCD_WR,
        .data_gpio_nums = {
            LCD_D0, LCD_D1, LCD_D2, LCD_D3,
            LCD_D4, LCD_D5, LCD_D6, LCD_D7,
        },
        .bus_width           = LCD_BIT_WIDTH,
        .max_transfer_bytes  = LCD_H_RES * 40 * sizeof(uint16_t),  /* 40 rows = 25KB DMA (was 300KB) */
        .psram_trans_align   = 64,
        .sram_trans_align    = 4,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_i80_bus(&bus_cfg, &i80_bus), TAG, "i80 bus init failed");

    /* Panel IO on the bus */
    esp_lcd_panel_io_handle_t io_handle = NULL;
    esp_lcd_panel_io_i80_config_t io_cfg = {
        .cs_gpio_num       = LCD_CS,
        .pclk_hz           = LCD_CLK_HZ,
        .trans_queue_depth  = 10,
        .dc_levels = {
            .dc_idle_level   = 0,
            .dc_cmd_level    = 0,
            .dc_dummy_level  = 0,
            .dc_data_level   = 1,
        },
        .lcd_cmd_bits   = 8,
        .lcd_param_bits = 8,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_i80(i80_bus, &io_cfg, &io_handle), TAG, "panel IO init failed");

    /* ILI9488 panel driver — RGB666 native, accepts RGB565 input */
    esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = LCD_RST,
        .rgb_ele_order  = LCD_RGB_ELEMENT_ORDER_BGR,
        .bits_per_pixel = 16,  /* driver converts RGB565→RGB666 internally */
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_ili9488(io_handle, &panel_cfg, &s_panel), TAG, "ILI9488 panel init failed");

    /* Reset and init sequence */
    esp_lcd_panel_reset(s_panel);
    esp_lcd_panel_init(s_panel);

    /* Portrait orientation: 320 wide x 480 tall */
    esp_lcd_panel_swap_xy(s_panel, false);
    esp_lcd_panel_mirror(s_panel, false, false);

    /* Display ON */
    esp_lcd_panel_disp_on_off(s_panel, true);

    /* Clear to black */
    display_fill(0x0000);

    /* Backlight is always on (hardwired to 3V3 on PCB) */

    ESP_LOGI(TAG, "Display initialized: %dx%d, %d-bit i80 @ %d MHz",
             LCD_H_RES, LCD_V_RES, LCD_BIT_WIDTH, LCD_CLK_HZ / 1000000);
    return ESP_OK;
}

/* ── Drawing helpers ───────────────────────────────────────────────── */

esp_lcd_panel_handle_t display_get_panel(void)
{
    return s_panel;
}

esp_err_t display_fill(uint16_t color)
{
    /* Allocate one row buffer in PSRAM to avoid exhausting SRAM */
    uint16_t *row = heap_caps_malloc(LCD_H_RES * sizeof(uint16_t), MALLOC_CAP_DMA);
    if (!row) return ESP_ERR_NO_MEM;

    for (int i = 0; i < LCD_H_RES; i++) {
        row[i] = color;
    }

    for (int y = 0; y < LCD_V_RES; y++) {
        esp_lcd_panel_draw_bitmap(s_panel, 0, y, LCD_H_RES, y + 1, row);
    }

    free(row);
    return ESP_OK;
}

esp_err_t display_draw_color_bars(void)
{
    /* 8 vertical color bars: R, G, B, White, Black, Cyan, Magenta, Yellow */
    static const uint16_t colors[] = {
        0xF800, /* Red */
        0x07E0, /* Green */
        0x001F, /* Blue */
        0xFFFF, /* White */
        0x0000, /* Black */
        0x07FF, /* Cyan */
        0xF81F, /* Magenta */
        0xFFE0, /* Yellow */
    };
    const int bar_width = LCD_H_RES / 8;

    uint16_t *row = heap_caps_malloc(LCD_H_RES * sizeof(uint16_t), MALLOC_CAP_DMA);
    if (!row) return ESP_ERR_NO_MEM;

    /* Fill one row with the 8-color pattern */
    for (int b = 0; b < 8; b++) {
        for (int x = b * bar_width; x < (b + 1) * bar_width && x < LCD_H_RES; x++) {
            row[x] = colors[b];
        }
    }

    /* Blit same row to every scanline */
    for (int y = 0; y < LCD_V_RES; y++) {
        esp_lcd_panel_draw_bitmap(s_panel, 0, y, LCD_H_RES, y + 1, row);
    }

    free(row);
    ESP_LOGI(TAG, "Color bars drawn");
    return ESP_OK;
}
