/*
 * ESP32 Emu Turbo — Display Driver
 * ST7796S 320x480, 8-bit 8080 parallel interface via esp_lcd
 */

#include "display.h"
#include "board_config.h"

#include "esp_log.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_st7796.h"
#include "driver/ledc.h"

#include <string.h>
#include <stdlib.h>

static const char *TAG = "display";

static esp_lcd_panel_handle_t s_panel = NULL;

/* ── Backlight PWM ─────────────────────────────────────────────────── */

static void backlight_init(void)
{
    ledc_timer_config_t timer_cfg = {
        .speed_mode      = LEDC_LOW_SPEED_MODE,
        .timer_num       = LCD_BL_LEDC_TIMER,
        .duty_resolution = LEDC_TIMER_8_BIT,
        .freq_hz         = LCD_BL_LEDC_FREQ,
        .clk_cfg         = LEDC_AUTO_CLK,
    };
    ledc_timer_config(&timer_cfg);

    ledc_channel_config_t ch_cfg = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel    = LCD_BL_LEDC_CHANNEL,
        .timer_sel  = LCD_BL_LEDC_TIMER,
        .intr_type  = LEDC_INTR_DISABLE,
        .gpio_num   = LCD_BL,
        .duty       = 0,  /* start OFF (GPIO45 must be LOW at boot) */
        .hpoint     = 0,
    };
    ledc_channel_config(&ch_cfg);
}

void display_set_backlight(uint8_t brightness)
{
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LCD_BL_LEDC_CHANNEL, brightness);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LCD_BL_LEDC_CHANNEL);
}

/* ── Panel init ────────────────────────────────────────────────────── */

esp_err_t display_init(void)
{
    ESP_LOGI(TAG, "Initializing ST7796S 8-bit i80 parallel display");

    /* Backlight PWM — start OFF before display init */
    backlight_init();

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
        .max_transfer_bytes  = LCD_H_RES * LCD_V_RES * sizeof(uint16_t),
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

    /* ST7796S panel driver */
    esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = LCD_RST,
        .rgb_ele_order  = LCD_RGB_ELEMENT_ORDER_BGR,
        .bits_per_pixel = 16,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_st7796(io_handle, &panel_cfg, &s_panel), TAG, "ST7796S panel init failed");

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

    /* Turn on backlight */
    display_set_backlight(LCD_BL_LEDC_DUTY);

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
