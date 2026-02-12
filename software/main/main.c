/*
 * ESP32 Emu Turbo — Phase 1 Hardware Validation Test Harness
 *
 * Initializes all peripherals and runs through a test sequence:
 *   1. Power management (IP5306 battery status)
 *   2. Display (ST7796S color bars)
 *   3. Input (12-button live readout)
 *   4. SD card (mount + ROM listing)
 *   5. Audio (440 Hz test tone)
 *   6. Interactive mode (button display + FPS counter)
 */

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_lcd_panel_ops.h"

#include "board_config.h"
#include "display.h"
#include "input.h"
#include "sdcard.h"
#include "audio.h"
#include "power.h"

static const char *TAG = "main";

/* ── Simple status display ─────────────────────────────────────────── */

/* RGB565 colors */
#define COLOR_BLACK   0x0000
#define COLOR_WHITE   0xFFFF
#define COLOR_RED     0xF800
#define COLOR_GREEN   0x07E0
#define COLOR_BLUE    0x001F
#define COLOR_YELLOW  0xFFE0
#define COLOR_CYAN    0x07FF

/*
 * Draw a solid rectangle. Used for simple status indicators
 * since we don't have font rendering in this bootstrap.
 */
static void draw_rect(int x, int y, int w, int h, uint16_t color)
{
    esp_lcd_panel_handle_t panel = display_get_panel();
    if (!panel) return;

    uint16_t *buf = heap_caps_malloc(w * sizeof(uint16_t), MALLOC_CAP_DMA);
    if (!buf) return;

    for (int i = 0; i < w; i++) buf[i] = color;
    for (int row = y; row < y + h && row < LCD_V_RES; row++) {
        esp_lcd_panel_draw_bitmap(panel, x, row, x + w, row + 1, buf);
    }
    free(buf);
}

/*
 * Draw a simple "LED indicator" — a colored square for each test result.
 * Green = PASS, Red = FAIL, Yellow = WARNING/SKIP
 */
static void draw_status(int row, uint16_t color)
{
    int y = 10 + row * 50;
    draw_rect(10, y, 300, 40, color);
}

/* ── Test sequence ─────────────────────────────────────────────────── */

static void run_tests(void)
{
    int test_row = 0;

    /* ── 1. Power Management ── */
    ESP_LOGI(TAG, "=== Test 1: Power Management (IP5306) ===");
    esp_err_t ret = power_init();
    if (ret == ESP_OK) {
        int batt = power_get_battery_percent();
        bool charging = power_is_charging();
        if (batt >= 0) {
            ESP_LOGI(TAG, "Battery: %d%%, Charging: %s", batt, charging ? "YES" : "NO");
            draw_status(test_row, COLOR_GREEN);
        } else {
            ESP_LOGW(TAG, "IP5306 not available (non-I2C variant?)");
            draw_status(test_row, COLOR_YELLOW);
        }
    } else {
        ESP_LOGW(TAG, "Power init skipped: %s", esp_err_to_name(ret));
        draw_status(test_row, COLOR_YELLOW);
    }
    test_row++;

    /* ── 2. Display test — color bars ── */
    ESP_LOGI(TAG, "=== Test 2: Display (color bars) ===");
    ret = display_draw_color_bars();
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "Color bars displayed — verify visually");
    } else {
        ESP_LOGE(TAG, "Color bars failed: %s", esp_err_to_name(ret));
    }
    vTaskDelay(pdMS_TO_TICKS(3000));  /* Let user see the bars */

    /* Clear and show test indicators */
    display_fill(COLOR_BLACK);
    /* Redraw power status */
    draw_status(0, (power_get_battery_percent() >= 0) ? COLOR_GREEN : COLOR_YELLOW);
    draw_status(test_row, COLOR_GREEN);  /* Display itself is working */
    test_row++;

    /* ── 3. Input ── */
    ESP_LOGI(TAG, "=== Test 3: Input (12 buttons) ===");
    ret = input_init();
    if (ret == ESP_OK) {
        uint16_t state = input_read();
        ESP_LOGI(TAG, "Button state: 0x%04X (no buttons should be pressed)", state);
        draw_status(test_row, COLOR_GREEN);
    } else {
        ESP_LOGE(TAG, "Input init failed");
        draw_status(test_row, COLOR_RED);
    }
    test_row++;

    /* ── 4. SD Card ── */
    ESP_LOGI(TAG, "=== Test 4: SD Card ===");
    ret = sdcard_init();
    if (ret == ESP_OK) {
        int roms = sdcard_list_roms();
        ESP_LOGI(TAG, "SD card OK, %d ROM(s) found", roms);
        draw_status(test_row, COLOR_GREEN);
    } else {
        ESP_LOGW(TAG, "SD card not available: %s", esp_err_to_name(ret));
        draw_status(test_row, COLOR_YELLOW);
    }
    test_row++;

    /* ── 5. Audio ── */
    ESP_LOGI(TAG, "=== Test 5: Audio (440 Hz tone) ===");
    ret = audio_init();
    if (ret == ESP_OK) {
        draw_status(test_row, COLOR_GREEN);
        ESP_LOGI(TAG, "Playing test tone...");
        audio_play_test_tone(2000);  /* 2 seconds */
    } else {
        ESP_LOGE(TAG, "Audio init failed: %s", esp_err_to_name(ret));
        draw_status(test_row, COLOR_RED);
    }
    test_row++;

    ESP_LOGI(TAG, "====================================");
    ESP_LOGI(TAG, "  All hardware tests complete");
    ESP_LOGI(TAG, "  Entering interactive mode...");
    ESP_LOGI(TAG, "====================================");
}

/* ── Interactive mode: live button + FPS display ───────────────────── */

static void interactive_loop(void)
{
    ESP_LOGI(TAG, "Interactive mode: press buttons to test, serial output shows state");

    uint16_t prev_state = 0;
    int frame_count = 0;
    int64_t fps_start = esp_timer_get_time();

    while (1) {
        uint16_t state = input_read();

        /* Log button changes */
        if (state != prev_state) {
            uint16_t changed = state ^ prev_state;
            for (int i = 0; i < 12; i++) {
                if (changed & (1 << i)) {
                    ESP_LOGI(TAG, "Button %s: %s",
                             input_button_name(i),
                             (state & (1 << i)) ? "PRESSED" : "RELEASED");
                }
            }
            prev_state = state;

            /* Update display: draw button indicators in bottom area */
            int y_base = LCD_V_RES - 60;
            for (int i = 0; i < 12; i++) {
                int x = 10 + (i % 6) * 50;
                int y = y_base + (i / 6) * 25;
                uint16_t color = (state & (1 << i)) ? COLOR_CYAN : COLOR_BLACK;
                draw_rect(x, y, 40, 20, color);
            }
        }

        /* FPS counter (logged every 5 seconds) */
        frame_count++;
        int64_t now = esp_timer_get_time();
        int64_t elapsed = now - fps_start;
        if (elapsed >= 5000000) {  /* 5 seconds */
            float fps = (float)frame_count * 1000000.0f / (float)elapsed;
            ESP_LOGI(TAG, "Poll rate: %.1f Hz", fps);
            frame_count = 0;
            fps_start = now;
        }

        vTaskDelay(pdMS_TO_TICKS(1));  /* 1 ms poll interval */
    }
}

/* ── Entry point ───────────────────────────────────────────────────── */

void app_main(void)
{
    ESP_LOGI(TAG, "╔══════════════════════════════════════╗");
    ESP_LOGI(TAG, "║  ESP32 Emu Turbo — Hardware Test     ║");
    ESP_LOGI(TAG, "║  Phase 1: Hardware Abstraction       ║");
    ESP_LOGI(TAG, "╚══════════════════════════════════════╝");

    /* Display must init first — all other tests show status on screen */
    esp_err_t ret = display_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "CRITICAL: Display init failed! Check wiring.");
        ESP_LOGE(TAG, "Continuing with serial-only output...");
    }

    run_tests();
    interactive_loop();
}
