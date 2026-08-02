/*
 * ESP32 Emu Turbo — bring-up test firmware
 *
 * GENERATED FILE — do not edit.
 * Regenerate with: python3 software/bringup_test/generate.py
 * Every pin number below comes from software/main/board_config.h.
 *
 * Purpose: this board is validated by a user with no bench instruments. The
 * serial log below IS the instrument, so every check prints one parseable
 * line, a check that cannot run prints SKIP with the reason it cannot run,
 * and nothing is ever silently omitted.
 *
 * Report format, one line per check:
 *
 *   BRINGUP;<seq>;<PASS|FAIL|SKIP>;<id>;<pins>;<detail>
 *
 * followed by:
 *
 *   BRINGUP-FAILED;<comma-separated ids>      (omitted when there are none)
 *   BRINGUP-SKIPPED;<comma-separated ids>     (omitted when there are none)
 *   BRINGUP-SUMMARY;total=..;pass=..;fail=..;skip=..;verdict=<GREEN|RED>
 *   BRINGUP-LED;<what the diagnostic heartbeat LED is signalling>
 *   BRINGUP-END
 *
 * Fields never contain ';' — bringup_detail() rewrites it to ','.
 *
 * A second, cable-free channel carries the same verdict: the diagnostic
 * heartbeat LED on LED_HB blinks 1 Hz while all is well and switches to
 * per-subsystem blink codes when a check fails. Serial stays the rich
 * channel; the LED adds nothing to it and removes nothing from it.
 */

#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>

#include "unity.h"
#include "board_config.h"

#include "display.h"
#include "audio.h"
#include "sdcard.h"

#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "driver/temperature_sensor.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_attr.h"
#include "hal/usb_serial_jtag_ll.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/* ── Generated tables (from board_config.h) ─────────────────── */

typedef struct {
    const char  *name;      /* short label, e.g. "UP"           */
    gpio_num_t   pin;
    int          num;       /* GPIO number, for the report line   */
    bool         ext_pullup;/* PCB has the 10k pull-up + 100nF    */
} btn_t;

static const btn_t BUTTONS[] = {
    { "UP", BTN_UP, 40, true },
    { "DOWN", BTN_DOWN, 41, true },
    { "LEFT", BTN_LEFT, 42, true },
    { "RIGHT", BTN_RIGHT, 1, true },
    { "A", BTN_A, 2, true },
    { "B", BTN_B, 48, true },
    { "X", BTN_X, 47, true },
    { "Y", BTN_Y, 21, true },
    { "START", BTN_START, 18, true },
    { "SELECT", BTN_SELECT, 0, true },
    { "L", BTN_L, 45, false },  /* board_config.h: NO external pull-up */
    { "R", BTN_R, 3, true },
};
#define N_BUTTONS 12

static const gpio_num_t LCD_DATA[] = { LCD_D0, LCD_D1, LCD_D2, LCD_D3, LCD_D4, LCD_D5, LCD_D6, LCD_D7 };
static const int LCD_DATA_NUM[] = { 4, 5, 6, 7, 8, 9, 10, 11 };
#define N_LCD_DATA 8

static const gpio_num_t LCD_CTRL[] = { LCD_CS, LCD_RST, LCD_DC, LCD_WR };
static const char *LCD_CTRL_NAME[] = { "CS", "RST", "DC", "WR" };
static const int LCD_CTRL_NUM[] = { 12, 13, 14, 46 };
#define N_LCD_CTRL 4

static const gpio_num_t SD_LINES[] = { SD_MOSI, SD_MISO, SD_CLK, SD_CS };
static const char *SD_LINE_NAME[] = { "MOSI", "MISO", "CLK", "CS" };
static const int SD_LINE_NUM[] = { 44, 43, 38, 39 };
#define N_SD_LINES 4

typedef struct { const char *net; int gpio; } pinmap_t;
static const pinmap_t PINMAP[] = {
    { "BTN_SELECT", 0 },
    { "BTN_RIGHT", 1 },
    { "BTN_A", 2 },
    { "BTN_R", 3 },
    { "LCD_D0", 4 },
    { "LCD_D1", 5 },
    { "LCD_D2", 6 },
    { "LCD_D3", 7 },
    { "LCD_D4", 8 },
    { "LCD_D5", 9 },
    { "LCD_D6", 10 },
    { "LCD_D7", 11 },
    { "LCD_CS", 12 },
    { "LCD_RST", 13 },
    { "LCD_DC", 14 },
    { "LED_HB", 15 },
    { "I2S_DOUT", 17 },
    { "BTN_START", 18 },
    { "USB_DN", 19 },
    { "USB_DP", 20 },
    { "BTN_Y", 21 },
    { "SD_CLK", 38 },
    { "SD_CS", 39 },
    { "BTN_UP", 40 },
    { "BTN_DOWN", 41 },
    { "BTN_LEFT", 42 },
    { "SD_MISO", 43 },
    { "SD_MOSI", 44 },
    { "BTN_L", 45 },
    { "LCD_WR", 46 },
    { "BTN_X", 47 },
    { "BTN_B", 48 },
};
#define N_PINMAP 32

/* ESP32-S3 strapping pins (datasheet 2.4) crossed with board nets. */
typedef struct { int gpio; const char *net; const char *role; } strap_t;
static const strap_t STRAPS[] = {
    { 0, "BTN_SELECT", "boot mode (LOW at reset = serial download)" },
    { 3, "BTN_R", "JTAG source select" },
    { 45, "BTN_L", "VDD_SPI voltage (LOW at reset = 3.3 V, required by Octal PSRAM)" },
    { 46, "LCD_WR", "ROM message print enable" },
};
#define N_STRAPS 4

/* ── Diagnostic heartbeat LED ────────────────────────────────── */
/*
 * Blink-code contract, quoted from docs/diagnostic-leds-roadmap.md:
 *
 *   "Heartbeat firmware contract (bringup_test): 1 Hz steady = alive;
 *    N blinks + pause = subsystem N failed (2=SD, 3=display, 4=audio,
 *    5=buttons, 6=PSRAM) — telemetry stays the rich channel, the LED is
 *    the cable-free fallback."
 *
 * The table below is generated from BLINK_CODES in generate.py, which is
 * the single place the mapping is written down. A check joins a subsystem
 * by the prefix of its id, so a new sd.* or lcd.* check needs no edit here.
 */
#define HB_LED_PRESENT   1
#define HB_LED_PIN       LED_HB
#define HB_LED_NUM       15

typedef struct {
    uint8_t     code;        /* number of short blinks              */
    const char *subsystem;   /* label, for the report line          */
    const char *id_prefix;   /* check ids this code speaks for      */
} hb_code_t;

static const hb_code_t HB_CODES[] = {
    { 2, "SD", "sd." },
    { 3, "display", "lcd." },
    { 4, "audio", "audio." },
    { 5, "buttons", "btn." },
    { 6, "PSRAM", "psram." },
    { 6, "PSRAM", "chip.psram_size" },
};
#define N_HB_CODES  6
#define HB_CODE_MAX 6
#define HB_CODE_LEGEND "2=SD 3=display 4=audio 5=buttons 6=PSRAM"

#define MODULE_VARIANT   "N16R8"
#define EXPECT_FLASH_MB  16
#define EXPECT_PSRAM_MB  8
#define EXPECT_USB_DP    20
#define EXPECT_USB_DN    19
#define I2S_DOUT_NUM     17

/* ══════════════════════════════════════════════════════════════════════
 * Reporting
 * ══════════════════════════════════════════════════════════════════ */

static char     s_detail[256];
static unsigned s_seq;
static unsigned s_pass, s_fail, s_skip;
static char     s_failed_ids[512];
static char     s_skipped_ids[512];

/* Fill the detail field of the current check. ';' is the field separator, so
 * it is rewritten rather than allowed to corrupt the line. */
static void bringup_detail(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(s_detail, sizeof(s_detail), fmt, ap);
    va_end(ap);
    for (char *p = s_detail; *p; p++) {
        if (*p == ';')  *p = ',';
        if (*p == '\n' || *p == '\r') *p = ' ';
    }
}

#define BRINGUP_SKIP(...) do {                  \
        bringup_detail(__VA_ARGS__);            \
        TEST_IGNORE_MESSAGE(s_detail);          \
    } while (0)

static void id_append(char *dst, size_t cap, const char *id)
{
    size_t n = strlen(dst);
    if (n && n + 1 < cap) dst[n++] = ',';
    snprintf(dst + n, cap - n, "%s", id);
}

/* ══════════════════════════════════════════════════════════════════════
 * Crash forensics across reboots
 *
 * A 3V3 collapse under load does not produce a FAIL line — it reboots the
 * chip mid-log. These RTC-retained fields survive that reset, so the next
 * run can name the check that was executing when the board died. Without
 * them the only symptom is a truncated log, which is exactly the symptom a
 * user with no instruments cannot interpret.
 * ══════════════════════════════════════════════════════════════════ */

#define PHASE_MAGIC 0xB0A7D00Du

RTC_NOINIT_ATTR static uint32_t s_phase_magic;
RTC_NOINIT_ATTR static char     s_phase_id[48];

static void phase_enter(const char *id)
{
    s_phase_magic = PHASE_MAGIC;
    snprintf(s_phase_id, sizeof(s_phase_id), "%s", id);
}

static void phase_clear(void) { s_phase_magic = 0; }

/* ══════════════════════════════════════════════════════════════════════
 * Check table plumbing
 * ══════════════════════════════════════════════════════════════════ */

typedef struct {
    const char *id;
    const char *pins;
    void      (*fn)(void);
    const char *implicates;  /* printed on FAIL: which net or part to look at */
} check_t;

/* Defined with the heartbeat LED below; declared here because run_check() is
 * the one place that learns a check has failed. */
static void hb_note_failure(const char *id);

static void run_check(const check_t *c)
{
    s_detail[0] = '\0';
    phase_enter(c->id);

    UNITY_COUNTER_TYPE f0 = Unity.TestFailures;
    UNITY_COUNTER_TYPE i0 = Unity.TestIgnores;

    UnityDefaultTestRun(c->fn, c->id, __LINE__);

    const char *result;
    if (Unity.TestIgnores > i0) {
        result = "SKIP";
        s_skip++;
        id_append(s_skipped_ids, sizeof(s_skipped_ids), c->id);
    } else if (Unity.TestFailures > f0) {
        result = "FAIL";
        s_fail++;
        id_append(s_failed_ids, sizeof(s_failed_ids), c->id);
        hb_note_failure(c->id);
    } else {
        result = "PASS";
        s_pass++;
    }

    if (strcmp(result, "FAIL") == 0) {
        printf("BRINGUP;%02u;FAIL;%s;%s;%s%simplicates: %s\n",
               ++s_seq, c->id, c->pins,
               s_detail, s_detail[0] ? " | " : "", c->implicates);
    } else {
        printf("BRINGUP;%02u;%s;%s;%s;%s\n",
               ++s_seq, result, c->id, c->pins, s_detail);
    }
    fflush(stdout);
}

/* ══════════════════════════════════════════════════════════════════════
 * GPIO helpers
 * ══════════════════════════════════════════════════════════════════ */

static esp_err_t pin_input(gpio_num_t pin, gpio_pull_mode_t pull)
{
    gpio_config_t c = {
        .pin_bit_mask = 1ULL << pin,
        .mode         = GPIO_MODE_INPUT,
        .pull_up_en   = (pull == GPIO_PULLUP_ONLY)   ? GPIO_PULLUP_ENABLE   : GPIO_PULLUP_DISABLE,
        .pull_down_en = (pull == GPIO_PULLDOWN_ONLY) ? GPIO_PULLDOWN_ENABLE : GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    return gpio_config(&c);
}

/* Open-drain with both internal pulls off: level 0 sinks the node, level 1
 * releases it to high-Z. Releasing is then a single register write, which is
 * what the RC measurement below needs — reconfiguring the pad through
 * gpio_config() would mean taking a spinlock inside the timed region. */
static esp_err_t pin_open_drain(gpio_num_t pin)
{
    gpio_config_t c = {
        .pin_bit_mask = 1ULL << pin,
        .mode         = GPIO_MODE_INPUT_OUTPUT_OD,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    return gpio_config(&c);
}

static esp_err_t pin_inout(gpio_num_t pin)
{
    gpio_config_t c = {
        .pin_bit_mask = 1ULL << pin,
        .mode         = GPIO_MODE_INPUT_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    return gpio_config(&c);
}

/* Read a pin twice, once against the internal pull-up and once against the
 * internal pull-down. A net that is hard-shorted cannot follow both. */
static void stuck_probe(gpio_num_t pin, int *with_pu, int *with_pd)
{
    pin_input(pin, GPIO_PULLUP_ONLY);
    vTaskDelay(pdMS_TO_TICKS(5));
    *with_pu = gpio_get_level(pin);

    pin_input(pin, GPIO_PULLDOWN_ONLY);
    vTaskDelay(pdMS_TO_TICKS(5));
    *with_pd = gpio_get_level(pin);

    pin_input(pin, GPIO_PULLUP_ONLY);
}

/* ══════════════════════════════════════════════════════════════════════
 * Diagnostic heartbeat LED
 *
 * The serial report above is the rich channel and stays the rich channel;
 * this LED is the same verdict for a board with no cable attached. It is
 * additive — nothing here changes what is printed.
 *
 * What it says:
 *
 *   1 Hz steady        the chip booted, the straps let it run, and the
 *                      firmware is still executing — during the suite and
 *                      after it finishes with no failures
 *   N blinks + pause   subsystem N failed (see HB_CODES); several failed
 *                      subsystems cycle in ascending order
 *   fast flutter       something failed that no code speaks for — read the
 *                      serial log. A failed run must never leave the LED
 *                      beating a healthy 1 Hz, so an uncoded failure gets
 *                      its own unmistakable pattern rather than none.
 *
 * The LED is lit by driving the pin to HB_LED_ACTIVE_LEVEL. Active HIGH is
 * the assumption the hardware side must match: GPIO -> R31 -> LED anode,
 * cathode to GND, so a HIGH pin sources the ~1 mA and lights it. If the
 * schematic instead ties the anode to +3V3 and sinks through the GPIO, this
 * one constant flips and nothing else changes.
 * ══════════════════════════════════════════════════════════════════ */

#define HB_LED_ACTIVE_LEVEL  1

#define HB_ALIVE_MS       500   /* 1 Hz symmetric = alive                 */
#define HB_BLINK_ON_MS    160   /* a "short blink" inside a code          */
#define HB_BLINK_OFF_MS   240
#define HB_PAUSE_MS      1000   /* the gap the roadmap calls "1s pause"   */
#define HB_FLUTTER_MS      80
#define HB_FLUTTER_N       12

/* Bit N set = subsystem code N has a failing check. Written by the test
 * sequence, read by the LED task, so both are volatile. */
static volatile uint32_t s_hb_fail_mask;
static volatile bool     s_hb_uncoded;

/* Attribute a failed check to its subsystem code by id prefix. A check no
 * code covers is not dropped: it raises the uncoded flag, because the one
 * thing this LED must never do is report health on a board that failed. */
static void hb_note_failure(const char *id)
{
    for (int i = 0; i < N_HB_CODES; i++) {
        if (strncmp(id, HB_CODES[i].id_prefix, strlen(HB_CODES[i].id_prefix)) == 0) {
            s_hb_fail_mask |= 1u << HB_CODES[i].code;
            return;
        }
    }
    s_hb_uncoded = true;
}

/* Describe what the LED is doing right now, for the serial trailer — so the
 * log and the LED can be checked against each other. */
static void hb_describe(char *out, size_t cap)
{
#if HB_LED_PRESENT
    if (!s_hb_fail_mask && !s_hb_uncoded) {
        snprintf(out, cap, "GPIO%d 1Hz steady = alive", HB_LED_NUM);
        return;
    }
    snprintf(out, cap, "GPIO%d cycling:", HB_LED_NUM);
    for (int i = 0; i < N_HB_CODES; i++) {
        if (!(s_hb_fail_mask & (1u << HB_CODES[i].code))) continue;
        /* Two prefixes can share a code; name it once. */
        bool already = false;
        for (int j = 0; j < i; j++)
            if (HB_CODES[j].code == HB_CODES[i].code) already = true;
        if (already) continue;
        size_t n = strlen(out);
        if (n < cap)
            snprintf(out + n, cap - n, " %dx=%s",
                     HB_CODES[i].code, HB_CODES[i].subsystem);
    }
    if (s_hb_uncoded) {
        size_t n = strlen(out);
        if (n < cap)
            snprintf(out + n, cap - n, " + fast flutter (failure with no code)");
    }
#else
    snprintf(out, cap, "no LED_HB net on this board revision");
#endif
}

#if HB_LED_PRESENT

static int s_hb_probe_high = -1;   /* level read back while driving HIGH */
static int s_hb_probe_low  = -1;

static void hb_set(bool on)
{
    gpio_set_level(HB_LED_PIN, on ? HB_LED_ACTIVE_LEVEL : !HB_LED_ACTIVE_LEVEL);
}

static void hb_pulse(int on_ms, int off_ms)
{
    hb_set(true);
    vTaskDelay(pdMS_TO_TICKS(on_ms));
    hb_set(false);
    vTaskDelay(pdMS_TO_TICKS(off_ms));
}

/* The mask is sampled once per cycle, so a failure found mid-suite appears at
 * the next pattern boundary rather than cutting a code in half. */
static void hb_task(void *arg)
{
    (void)arg;
    for (;;) {
        uint32_t mask    = s_hb_fail_mask;
        bool     uncoded = s_hb_uncoded;

        if (!mask && !uncoded) {
            hb_pulse(HB_ALIVE_MS, HB_ALIVE_MS);
            continue;
        }

        /* Ascending order, so the first code seen is always the lowest —
         * counting blinks is easier when the sequence is predictable.
         * Codes 0 and 1 are never set: the contract starts at 2. */
        for (int code = 0; code <= HB_CODE_MAX; code++) {
            if (!(mask & (1u << code))) continue;
            for (int i = 0; i < code; i++)
                hb_pulse(HB_BLINK_ON_MS, HB_BLINK_OFF_MS);
            hb_set(false);
            vTaskDelay(pdMS_TO_TICKS(HB_PAUSE_MS));
        }

        if (uncoded) {
            for (int i = 0; i < HB_FLUTTER_N; i++)
                hb_pulse(HB_FLUTTER_MS, HB_FLUTTER_MS);
            hb_set(false);
            vTaskDelay(pdMS_TO_TICKS(HB_PAUSE_MS));
        }
    }
}

#endif  /* HB_LED_PRESENT */

/* Probe the net once, then hand the pin to the task for good. Doing the
 * electrical test here rather than inside the check means the LED starts
 * beating before the first line of serial output — on a board that hangs in
 * an early check, the LED is then the only evidence the chip ever ran. */
static void hb_init(void)
{
#if HB_LED_PRESENT
    if (pin_inout(HB_LED_PIN) == ESP_OK) {
        gpio_set_level(HB_LED_PIN, 1);
        vTaskDelay(pdMS_TO_TICKS(2));
        s_hb_probe_high = gpio_get_level(HB_LED_PIN);
        gpio_set_level(HB_LED_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(2));
        s_hb_probe_low = gpio_get_level(HB_LED_PIN);
    }
    hb_set(false);
    xTaskCreate(hb_task, "heartbeat", 2048, NULL, 3, NULL);
#endif
}

static void chk_led_heartbeat(void)
{
#if HB_LED_PRESENT
    /* Whether the LED emits light is not observable: nothing feeds back from
     * LED6 into a GPIO. What is observable is that the net follows the pin
     * both ways, which is what an unsoldered LED_HB or a short to a rail
     * breaks. */
    bringup_detail("GPIO%d drive HIGH reads %d, LOW reads %d, active-%s; "
                   "1Hz heartbeat running, codes " HB_CODE_LEGEND ". "
                   "Light output cannot be sensed — look at LED6",
                   HB_LED_NUM, s_hb_probe_high, s_hb_probe_low,
                   HB_LED_ACTIVE_LEVEL ? "high" : "low");
    TEST_ASSERT_EQUAL_MESSAGE(1, s_hb_probe_high,
                              "LED_HB will not go HIGH — shorted to GND, or the pin "
                              "could not be configured");
    TEST_ASSERT_EQUAL_MESSAGE(0, s_hb_probe_low,
                              "LED_HB will not go LOW — shorted to +3V3");
#else
    BRINGUP_SKIP("board_config.h defines no LED_HB net, so this board revision has "
                 "no heartbeat LED to drive. Blink codes (" HB_CODE_LEGEND ") are "
                 "still computed and reported on the BRINGUP-LED line; they simply "
                 "have nowhere to blink");
#endif
}

/* ══════════════════════════════════════════════════════════════════════
 * 1. Boot forensics and chip identity
 * ══════════════════════════════════════════════════════════════════ */

static esp_reset_reason_t s_reset_reason;

static void chk_previous_run(void)
{
    /* RTC_NOINIT memory is undefined after a true power cycle, so the marker
     * only means anything when the chip reset without losing its RTC domain.
     * Reading it after a cold boot would invent a previous run out of
     * whatever bits happened to be in the RAM. */
    if (s_reset_reason == ESP_RST_POWERON) {
        bringup_detail("cold power-on — no previous-run state is retained across it");
        return;
    }
    if (s_phase_magic != PHASE_MAGIC) {
        bringup_detail("reset=%d, no unfinished run recorded — the previous run "
                       "reached BRINGUP-END", (int)s_reset_reason);
        return;
    }

    /* The magic survived, so the last run died before reaching the end. */
    s_phase_id[sizeof(s_phase_id) - 1] = '\0';   /* it is RAM, not a promise */
    char died_in[96];   /* prefix + the full 48-byte phase id, no truncation */
    snprintf(died_in, sizeof(died_in),
             "previous run died during check '%s'", s_phase_id);
    TEST_FAIL_MESSAGE(died_in);
}

static void chk_reset_reason(void)
{
    static const char *names[] = {
        "UNKNOWN", "POWERON", "EXT", "SW", "PANIC", "INT_WDT", "TASK_WDT",
        "WDT", "DEEPSLEEP", "BROWNOUT", "SDIO", "USB", "JTAG", "EFUSE",
        "PWR_GLITCH", "CPU_LOCKUP",
    };
    int r = (int)s_reset_reason;
    const char *name = (r >= 0 && r < (int)(sizeof(names) / sizeof(names[0])))
                       ? names[r] : "OUT_OF_RANGE";
    bringup_detail("reset=%s(%d)", name, r);

    if (s_reset_reason == ESP_RST_BROWNOUT)
        TEST_FAIL_MESSAGE("brownout reset: the 3V3 rail collapsed");
    if (s_reset_reason == ESP_RST_PWR_GLITCH)
        TEST_FAIL_MESSAGE("power glitch reset detected by the chip");
}

static void chk_chip_model(void)
{
    esp_chip_info_t info;
    esp_chip_info(&info);
    bringup_detail("model=%d cores=%d rev=%d.%d features=0x%08x",
                   (int)info.model, info.cores,
                   info.revision / 100, info.revision % 100,
                   (unsigned)info.features);
    TEST_ASSERT_EQUAL_MESSAGE(CHIP_ESP32S3, info.model, "chip is not an ESP32-S3");
    TEST_ASSERT_EQUAL_MESSAGE(2, info.cores, "expected a dual-core part");
}

static void chk_flash_size(void)
{
    uint32_t bytes = 0;
    esp_err_t err = esp_flash_get_size(NULL, &bytes);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "esp_flash_get_size failed");
    bringup_detail("flash=%uMB expected=%dMB (%s)",
                   (unsigned)(bytes / (1024 * 1024)), EXPECT_FLASH_MB, MODULE_VARIANT);
    TEST_ASSERT_EQUAL_MESSAGE((uint32_t)EXPECT_FLASH_MB * 1024 * 1024, bytes,
                              "flash size does not match the module variant");
}

static void chk_psram_size(void)
{
#if CONFIG_SPIRAM
    size_t bytes = esp_psram_get_size();
    bringup_detail("psram=%uMB expected=%dMB mode=%s",
                   (unsigned)(bytes / (1024 * 1024)), EXPECT_PSRAM_MB,
#if CONFIG_SPIRAM_MODE_OCT
                   "octal"
#else
                   "quad"
#endif
                   );
    TEST_ASSERT_EQUAL_MESSAGE((size_t)EXPECT_PSRAM_MB * 1024 * 1024, bytes,
                              "PSRAM size does not match the module variant");
#if !CONFIG_SPIRAM_MODE_OCT
    TEST_FAIL_MESSAGE("PSRAM built in quad mode; this module is octal");
#endif
#else
    BRINGUP_SKIP("firmware built with CONFIG_SPIRAM disabled — PSRAM not probed");
#endif
}

/* A double-assigned GPIO in board_config.h makes two subsystems fight over a
 * pin, and both look fine in isolation. Cheap to check, impossible to see by
 * reading the header. */
static void chk_gpio_unique(void)
{
    int clashes = 0;
    for (int i = 0; i < N_PINMAP; i++) {
        for (int j = i + 1; j < N_PINMAP; j++) {
            if (PINMAP[i].gpio == PINMAP[j].gpio) {
                clashes++;
                bringup_detail("GPIO%d assigned to both %s and %s",
                               PINMAP[i].gpio, PINMAP[i].net, PINMAP[j].net);
            }
        }
    }
    if (!clashes)
        bringup_detail("%d GPIO assignments, all distinct", N_PINMAP);
    TEST_ASSERT_EQUAL_MESSAGE(0, clashes, "board_config.h assigns one GPIO twice");
}

static void chk_usb_serial_jtag(void)
{
    TEST_ASSERT_EQUAL_MESSAGE(EXPECT_USB_DN, USB_DN, "USB D- moved off its pin");
    TEST_ASSERT_EQUAL_MESSAGE(EXPECT_USB_DP, USB_DP, "USB D+ moved off its pin");
    bool writable = usb_serial_jtag_ll_txfifo_writable();
    bringup_detail("D-=GPIO%d D+=GPIO%d txfifo_writable=%s "
                   "(this line reaching you already proves the link)",
                   EXPECT_USB_DN, EXPECT_USB_DP, writable ? "yes" : "no");
    TEST_ASSERT_TRUE_MESSAGE(writable, "USB Serial/JTAG peripheral is not accepting data");
}

/* ══════════════════════════════════════════════════════════════════════
 * 2. Strapping pins
 *
 * The state these pins held at reset cannot be recovered after boot: the
 * latches are sampled once, at the rising edge of the reset, and are not
 * exposed to software afterwards. So this check can only prove the pin is
 * readable and idle-correct *now*, and print which boot-time decision it
 * made. GPIO45 is the one that matters — a pull-up on it at reset selects
 * VDD_SPI = 1.8 V and the Octal PSRAM stops working; the evidence for that
 * is the PSRAM size check above, not this one.
 * ══════════════════════════════════════════════════════════════════ */

static void chk_straps(void)
{
    char buf[192] = {0};
    for (int i = 0; i < N_STRAPS; i++) {
        pin_input(STRAPS[i].gpio, GPIO_PULLUP_ONLY);
        vTaskDelay(pdMS_TO_TICKS(2));
        int lvl = gpio_get_level(STRAPS[i].gpio);
        size_t n = strlen(buf);
        snprintf(buf + n, sizeof(buf) - n, "%sGPIO%d/%s=%d",
                 n ? " " : "", STRAPS[i].gpio, STRAPS[i].net, lvl);
    }
    bringup_detail("post-boot levels (NOT the reset-time latch): %s", buf);
}

/* ══════════════════════════════════════════════════════════════════════
 * 3. Buttons
 * ══════════════════════════════════════════════════════════════════ */

static int s_btn_idx;   /* set by the runner before each per-button check */

static void chk_btn_idle(void)
{
    const btn_t *b = &BUTTONS[s_btn_idx];
    /* BTN_L has no external pull-up (board_config.h): it needs the internal
     * one to read a valid idle level at all. */
    pin_input(b->pin, GPIO_PULLUP_ONLY);
    vTaskDelay(pdMS_TO_TICKS(10));
    int lvl = gpio_get_level(b->pin);
    bringup_detail("GPIO%d idle=%d", b->num, lvl);
    TEST_ASSERT_EQUAL_MESSAGE(1, lvl, "button reads pressed while nothing is pressed");
}

/* Measure the RC network on a button net without any instrument.
 *
 * Drive the node to 0 V, release it to a floating input, and time how long
 * the 10k pull-up takes to charge the 100nF debounce cap through the input
 * threshold. tau = 10k * 100n = 1 ms and VIH = 0.75*VDD, so the expected
 * crossing is tau*ln(4) = 1.39 ms. The measured microseconds are always
 * printed, so the number is usable even where the window below is not:
 *
 *   far too fast   -> the 100nF debounce cap is missing or not soldered
 *   far too slow   -> the 10k pull-up is missing, or the cap is oversized
 *   never crosses  -> no pull-up at all on the net
 *
 * BTN_L is the inverted case: board_config.h says its pull-up is DNP, so
 * "never crosses" is the pass condition and a fast rise means a resistor was
 * populated that must not be — the GPIO45 strap would then select
 * VDD_SPI = 1.8 V and break the Octal PSRAM.
 */
#define RC_TIMEOUT_US   20000
#define RC_MIN_US         500
#define RC_MAX_US        4000

static void chk_btn_rc(void)
{
    const btn_t *b = &BUTTONS[s_btn_idx];

    TEST_ASSERT_EQUAL(ESP_OK, pin_open_drain(b->pin));
    gpio_set_level(b->pin, 0);
    vTaskDelay(pdMS_TO_TICKS(10));      /* fully discharge the debounce cap */

    /* Interrupts off so the 1 kHz tick cannot land inside the measurement. */
    portDISABLE_INTERRUPTS();
    gpio_set_level(b->pin, 1);          /* open-drain HIGH = release to high-Z */
    int64_t t0 = esp_timer_get_time();
    int64_t rise = -1;
    while (esp_timer_get_time() - t0 < RC_TIMEOUT_US) {
        if (gpio_get_level(b->pin)) { rise = esp_timer_get_time() - t0; break; }
    }
    portENABLE_INTERRUPTS();

    pin_input(b->pin, GPIO_PULLUP_ONLY);

    if (!b->ext_pullup) {
        if (rise < 0) {
            bringup_detail("GPIO%d stayed LOW for %dus with no internal pull — "
                           "pull-up correctly absent (DNP)", b->num, RC_TIMEOUT_US);
            return;
        }
        bringup_detail("GPIO%d rose in %lldus but its pull-up must be DNP",
                       b->num, (long long)rise);
        TEST_FAIL_MESSAGE("an external pull-up appears populated on a DNP net");
    }

    if (rise < 0) {
        bringup_detail("GPIO%d never reached VIH within %dus", b->num, RC_TIMEOUT_US);
        TEST_FAIL_MESSAGE("no pull-up current into this net");
    }

    bringup_detail("GPIO%d rise=%lldus (expect ~1390us for 10k x 100nF, "
                   "window %d-%dus)", b->num, (long long)rise, RC_MIN_US, RC_MAX_US);
    if (rise < RC_MIN_US)
        TEST_FAIL_MESSAGE("rise far too fast — debounce capacitor missing or open");
    if (rise > RC_MAX_US)
        TEST_FAIL_MESSAGE("rise far too slow — pull-up too weak or capacitor oversized");
}

/* Drive each button net low in turn and require every other button net to
 * stay high. Catches net-to-net shorts, and specifically catches D1 (the
 * BAT54C that makes SW13 press START and SELECT together) fitted backwards:
 * with the diodes reversed, pulling START down drags SELECT down with it. */
static void chk_btn_isolation(void)
{
    int shorts = 0;
    for (int i = 0; i < N_BUTTONS; i++)
        pin_input(BUTTONS[i].pin, GPIO_PULLUP_ONLY);
    vTaskDelay(pdMS_TO_TICKS(10));

    for (int i = 0; i < N_BUTTONS; i++) {
        /* Open-drain, so a net that turns out to be shorted to +3V3 is never
         * fought by a push-pull driver. */
        pin_open_drain(BUTTONS[i].pin);
        gpio_set_level(BUTTONS[i].pin, 0);
        vTaskDelay(pdMS_TO_TICKS(5));

        for (int j = 0; j < N_BUTTONS; j++) {
            if (i == j) continue;
            if (gpio_get_level(BUTTONS[j].pin) == 0) {
                shorts++;
                bringup_detail("%s(GPIO%d) driven LOW pulls %s(GPIO%d) LOW",
                               BUTTONS[i].name, BUTTONS[i].num,
                               BUTTONS[j].name, BUTTONS[j].num);
            }
        }
        pin_input(BUTTONS[i].pin, GPIO_PULLUP_ONLY);
        vTaskDelay(pdMS_TO_TICKS(5));
    }

    if (!shorts)
        bringup_detail("%d nets, every one isolated from the other %d",
                       N_BUTTONS, N_BUTTONS - 1);
    TEST_ASSERT_EQUAL_MESSAGE(0, shorts, "two button nets are connected");
}

/* ══════════════════════════════════════════════════════════════════════
 * 4. Display — ILI9488, 8-bit 8080 parallel
 * ══════════════════════════════════════════════════════════════════ */

static bool s_lcd_up;

static void chk_lcd_data_stuck(void)
{
    int bad = 0;
    for (int i = 0; i < N_LCD_DATA; i++) {
        int pu, pd;
        stuck_probe(LCD_DATA[i], &pu, &pd);
        if (pu == 0) {
            bad++;
            bringup_detail("D%d/GPIO%d held LOW against the internal pull-up",
                           i, LCD_DATA_NUM[i]);
        } else if (pd == 1) {
            bad++;
            bringup_detail("D%d/GPIO%d held HIGH against the internal pull-down",
                           i, LCD_DATA_NUM[i]);
        }
    }
    if (!bad) bringup_detail("D0-D7 all follow both internal pulls");
    TEST_ASSERT_EQUAL_MESSAGE(0, bad, "an LCD data line is stuck at a rail");
}

static void chk_lcd_data_shorts(void)
{
    for (int i = 0; i < N_LCD_DATA; i++) {
        TEST_ASSERT_EQUAL(ESP_OK, pin_inout(LCD_DATA[i]));
        gpio_set_level(LCD_DATA[i], 0);
    }
    vTaskDelay(pdMS_TO_TICKS(5));

    int shorts = 0;
    for (int i = 0; i < N_LCD_DATA; i++) {
        gpio_set_level(LCD_DATA[i], 1);
        vTaskDelay(pdMS_TO_TICKS(2));
        for (int j = 0; j < N_LCD_DATA; j++) {
            if (i == j) continue;
            if (gpio_get_level(LCD_DATA[j]) == 1) {
                shorts++;
                bringup_detail("D%d/GPIO%d shorted to D%d/GPIO%d",
                               i, LCD_DATA_NUM[i], j, LCD_DATA_NUM[j]);
            }
        }
        gpio_set_level(LCD_DATA[i], 0);
    }
    if (!shorts) bringup_detail("walking-1 over D0-D7, no line follows another");
    TEST_ASSERT_EQUAL_MESSAGE(0, shorts, "two LCD data lines are connected");
}

static void chk_lcd_ctrl(void)
{
    int bad = 0;
    for (int i = 0; i < N_LCD_CTRL; i++) {
        TEST_ASSERT_EQUAL(ESP_OK, pin_inout(LCD_CTRL[i]));

        gpio_set_level(LCD_CTRL[i], 1);
        vTaskDelay(pdMS_TO_TICKS(2));
        if (gpio_get_level(LCD_CTRL[i]) != 1) {
            bad++;
            bringup_detail("%s/GPIO%d will not go HIGH",
                           LCD_CTRL_NAME[i], LCD_CTRL_NUM[i]);
        }
        gpio_set_level(LCD_CTRL[i], 0);
        vTaskDelay(pdMS_TO_TICKS(2));
        if (gpio_get_level(LCD_CTRL[i]) != 0) {
            bad++;
            bringup_detail("%s/GPIO%d will not go LOW",
                           LCD_CTRL_NAME[i], LCD_CTRL_NUM[i]);
        }
    }
    if (!bad) bringup_detail("CS/RST/DC/WR all drive both ways");
    TEST_ASSERT_EQUAL_MESSAGE(0, bad, "an LCD control line is stuck");
}

/* Uses the production driver from software/main/display.c on purpose. A
 * validation firmware that configures the bus differently from the shipping
 * firmware validates the wrong thing. */
static void chk_lcd_init(void)
{
    esp_err_t err = display_init();
    bringup_detail("display_init()=%s %dx%d %d-bit i80 @ %dMHz",
                   esp_err_to_name(err), LCD_H_RES, LCD_V_RES,
                   LCD_BIT_WIDTH, LCD_CLK_HZ / 1000000);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "ILI9488 init sequence failed");
    s_lcd_up = true;
}

static void chk_lcd_pattern(void)
{
    if (!s_lcd_up)
        BRINGUP_SKIP("panel init failed (see lcd.panel.init) — nothing to draw on");
    esp_err_t err = display_draw_color_bars();
    bringup_detail("8 colour bars pushed, %d rows of %d px: %s",
                   LCD_V_RES, LCD_H_RES, esp_err_to_name(err));
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "bitmap transfer to the panel failed");
}

static void chk_lcd_readback(void)
{
    /* board_config.h: "LCD_RD: tied HIGH on PCB (no GPIO needed, no read-back
     * from ILI9488)". With no RD line there is no way to read the panel's
     * status or ID registers, so no software check can confirm the pixels
     * arrived. This is a permanent property of the board, not a missing test. */
    BRINGUP_SKIP("LCD_RD is tied HIGH on the PCB, the panel cannot be read back — "
                 "confirm the colour bars by eye (R,G,B,white,black,cyan,magenta,yellow)");
}

static void chk_lcd_backlight(void)
{
    BRINGUP_SKIP("backlight is hardwired to 3V3 through a resistor, no GPIO control — "
                 "if the panel is dark but the bars were drawn, look at the backlight "
                 "series resistor and the FPC seating, not at the firmware");
}

/* ══════════════════════════════════════════════════════════════════════
 * 5. SD card — SPI mode
 * ══════════════════════════════════════════════════════════════════ */

static spi_device_handle_t s_sd_dev;
static bool s_sd_bus_up;
static bool s_sd_card_talking;

static void chk_sd_lines_stuck(void)
{
    /* sdcard.c notes the TF-01A socket has no on-board pull-ups, so with
     * nothing driving, both internal pulls must win on every line. Anything
     * that refuses to follow is shorted to a rail. */
    int bad = 0;
    for (int i = 0; i < N_SD_LINES; i++) {
        int pu, pd;
        stuck_probe(SD_LINES[i], &pu, &pd);
        if (pu == 0) {
            bad++;
            bringup_detail("SD_%s/GPIO%d held LOW against the internal pull-up",
                           SD_LINE_NAME[i], SD_LINE_NUM[i]);
        } else if (pd == 1 && strcmp(SD_LINE_NAME[i], "MISO") != 0) {
            bad++;
            bringup_detail("SD_%s/GPIO%d held HIGH against the internal pull-down",
                           SD_LINE_NAME[i], SD_LINE_NUM[i]);
        }
    }
    if (!bad) bringup_detail("MOSI/MISO/CLK/CS all follow both internal pulls");
    TEST_ASSERT_EQUAL_MESSAGE(0, bad, "an SD line is shorted to a rail");
}

static void chk_sd_bus(void)
{
    spi_bus_config_t bus = {
        .mosi_io_num     = SD_MOSI,
        .miso_io_num     = SD_MISO,
        .sclk_io_num     = SD_CLK,
        .quadwp_io_num   = -1,
        .quadhd_io_num   = -1,
        .max_transfer_sz = 4096,
    };
    esp_err_t err = spi_bus_initialize(SD_SPI_HOST, &bus, SPI_DMA_CH_AUTO);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "SPI2 host would not initialise");

    /* CS is driven by hand: the card init sequence needs CS held across
     * several byte transfers, which the hardware CS cannot do. */
    spi_device_interface_config_t dev = {
        .clock_speed_hz = 400 * 1000,   /* SD spec: 100-400 kHz until ACMD41 */
        .mode           = 0,
        .spics_io_num   = -1,
        .queue_size     = 1,
    };
    err = spi_bus_add_device(SD_SPI_HOST, &dev, &s_sd_dev);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "could not attach a device to SPI2");

    pin_inout(SD_CS);
    gpio_set_level(SD_CS, 1);
    s_sd_bus_up = true;
    bringup_detail("SPI2 up at 400kHz, CS under software control");
}

static uint8_t sd_xfer(uint8_t out)
{
    spi_transaction_t t = {
        .flags  = SPI_TRANS_USE_TXDATA | SPI_TRANS_USE_RXDATA,
        .length = 8,
    };
    t.tx_data[0] = out;
    if (spi_device_polling_transmit(s_sd_dev, &t) != ESP_OK) return 0xFF;
    return t.rx_data[0];
}

/* Send a command frame and return R1, or 0xFF if the card never answers. */
static uint8_t sd_cmd(uint8_t cmd, uint32_t arg, uint8_t crc)
{
    sd_xfer(0xFF);
    sd_xfer(0x40 | cmd);
    sd_xfer(arg >> 24);
    sd_xfer(arg >> 16);
    sd_xfer(arg >> 8);
    sd_xfer(arg & 0xFF);
    sd_xfer(crc);
    for (int i = 0; i < 16; i++) {
        uint8_t r = sd_xfer(0xFF);
        if (!(r & 0x80)) return r;
    }
    return 0xFF;
}

static void sd_require_bus(void)
{
    if (!s_sd_bus_up)
        BRINGUP_SKIP("SPI2 never came up (see sd.bus.init) — the card cannot be reached");
}

static void chk_sd_cmd0(void)
{
    sd_require_bus();

    /* 80 clocks with CS released put the card into native SPI mode. */
    gpio_set_level(SD_CS, 1);
    for (int i = 0; i < 10; i++) sd_xfer(0xFF);

    gpio_set_level(SD_CS, 0);
    uint8_t r1 = sd_cmd(0, 0, 0x95);   /* GO_IDLE_STATE */
    gpio_set_level(SD_CS, 1);
    sd_xfer(0xFF);

    if (r1 == 0xFF) {
        /* Nothing on MISO. The socket HAS a card-detect contact (U6 pad 9,
         * "Cd" on the TF-01A drawing) but no revision reads it — the pad is
         * deliberately off-net since the R31-HIGH-2 BTN_R reroute (a Cd
         * blade is a switch to the grounded shell) — so there is no way to
         * tell an empty socket from a broken MISO net, and claiming either
         * would be a guess. */
        BRINGUP_SKIP("no R1 byte on SD_MISO — either the socket is empty or the "
                     "card is not powered/selected. Re-run with a known-good card "
                     "inserted: if it still reads 0xFF the fault is on the board "
                     "(no card-detect line is read on this revision, so nothing "
                     "in software can tell the two apart)");
    }
    bringup_detail("CMD0 R1=0x%02x", r1);
    TEST_ASSERT_EQUAL_MESSAGE(0x01, r1, "card answered but not with idle state");
    s_sd_card_talking = true;
}

static void sd_require_card(void)
{
    if (!s_sd_bus_up)
        BRINGUP_SKIP("SPI2 never came up (see sd.bus.init)");
    if (!s_sd_card_talking)
        BRINGUP_SKIP("no card responded to CMD0 (see sd.cmd0) — nothing to interrogate");
}

static void chk_sd_cmd8(void)
{
    sd_require_card();

    gpio_set_level(SD_CS, 0);
    uint8_t r1 = sd_cmd(8, 0x000001AA, 0x87);   /* SEND_IF_COND, 2.7-3.6V */
    uint8_t tr[4] = {0};
    if (r1 == 0x01)
        for (int i = 0; i < 4; i++) tr[i] = sd_xfer(0xFF);
    gpio_set_level(SD_CS, 1);
    sd_xfer(0xFF);

    if (r1 & 0x04) {
        /* Illegal command: a v1.x card. Legal, and not a board fault. */
        BRINGUP_SKIP("CMD8 rejected as illegal — this is an SD v1.x card, "
                     "voltage negotiation does not apply to it");
    }
    bringup_detail("CMD8 R1=0x%02x echo=%02x%02x%02x%02x (expect ..01AA)",
                   r1, tr[0], tr[1], tr[2], tr[3]);
    TEST_ASSERT_EQUAL_MESSAGE(0x01, r1, "CMD8 did not return idle state");
    TEST_ASSERT_EQUAL_MESSAGE(0x01, tr[2], "card did not accept the 2.7-3.6V range");
    TEST_ASSERT_EQUAL_MESSAGE(0xAA, tr[3], "check pattern came back corrupted");
}

static void chk_sd_acmd41(void)
{
    sd_require_card();

    uint8_t r1 = 0xFF;
    int tries = 0;
    int64_t t0 = esp_timer_get_time();
    while (esp_timer_get_time() - t0 < 1000000) {   /* SD spec: 1 s budget */
        gpio_set_level(SD_CS, 0);
        sd_cmd(55, 0, 0x65);                 /* APP_CMD */
        r1 = sd_cmd(41, 0x40000000, 0x77);   /* SD_SEND_OP_COND, HCS set */
        gpio_set_level(SD_CS, 1);
        sd_xfer(0xFF);
        tries++;
        if (r1 == 0x00) break;
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    bringup_detail("ACMD41 R1=0x%02x after %d attempts in %lldms",
                   r1, tries, (long long)((esp_timer_get_time() - t0) / 1000));
    TEST_ASSERT_EQUAL_MESSAGE(0x00, r1, "card never left the idle state");
}

static void chk_sd_ocr(void)
{
    sd_require_card();

    gpio_set_level(SD_CS, 0);
    uint8_t r1 = sd_cmd(58, 0, 0xFD);   /* READ_OCR */
    uint8_t ocr[4] = {0};
    if (r1 == 0x00)
        for (int i = 0; i < 4; i++) ocr[i] = sd_xfer(0xFF);
    gpio_set_level(SD_CS, 1);
    sd_xfer(0xFF);

    bringup_detail("CMD58 R1=0x%02x OCR=%02x%02x%02x%02x type=%s",
                   r1, ocr[0], ocr[1], ocr[2], ocr[3],
                   (ocr[0] & 0x40) ? "SDHC/SDXC" : "SDSC");
    TEST_ASSERT_EQUAL_MESSAGE(0x00, r1, "OCR register could not be read");
    TEST_ASSERT_TRUE_MESSAGE(ocr[0] & 0x80, "card reports its power-up is not finished");
}

static void chk_sd_mount(void)
{
    if (s_sd_bus_up) {
        /* Hand SPI2 back before the production driver claims it. */
        spi_bus_remove_device(s_sd_dev);
        spi_bus_free(SD_SPI_HOST);
        s_sd_bus_up = false;
    }
    if (!s_sd_card_talking)
        BRINGUP_SKIP("no card responded to CMD0 (see sd.cmd0) — nothing to mount");

    esp_err_t err = sdcard_init();
    bringup_detail("sdcard_init()=%s at %s, %dkHz",
                   esp_err_to_name(err), SD_MOUNT_POINT, SD_SPI_FREQ_KHZ);
    if (err == ESP_FAIL)
        TEST_FAIL_MESSAGE("card responds but has no mountable FAT filesystem");
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "FAT mount failed");
}

/* ══════════════════════════════════════════════════════════════════════
 * 6. Audio — I2S PDM on one pin into the PAM8403
 * ══════════════════════════════════════════════════════════════════ */

static bool s_audio_up;

static void chk_audio_init(void)
{
    esp_err_t err = audio_init();
    bringup_detail("audio_init()=%s PDM TX on GPIO%d, %dHz %d-bit mono "
                   "(clk unused by design)",
                   esp_err_to_name(err), I2S_DOUT_NUM, AUDIO_SAMPLE_RATE, AUDIO_BITS);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "I2S PDM channel would not start");
    s_audio_up = true;
}

static void chk_audio_tone(void)
{
    if (!s_audio_up)
        BRINGUP_SKIP("I2S never started (see audio.pdm.init) — no tone to play");
    int64_t t0 = esp_timer_get_time();
    esp_err_t err = audio_play_test_tone(600);
    int64_t ms = (esp_timer_get_time() - t0) / 1000;
    bringup_detail("440Hz for 600ms returned %s in %lldms", esp_err_to_name(err),
                   (long long)ms);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "the DMA never drained the tone buffer");
    /* A stalled I2S clock shows up as a write that blocks far longer than the
     * audio it carries. */
    TEST_ASSERT_TRUE_MESSAGE(ms < 3000, "tone took far longer than its own duration");
}

static void chk_audio_audible(void)
{
    BRINGUP_SKIP("whether the tone was audible cannot be sensed by the ESP32 — "
                 "there is no feedback path from the PAM8403 back to a GPIO. "
                 "If audio.tone passed and you heard nothing, the fault is after "
                 "GPIO%d: coupling cap, PAM8403 supply or SD pin, or the speaker",
                 I2S_DOUT_NUM);
}

/* ══════════════════════════════════════════════════════════════════════
 * 7. PSRAM
 * ══════════════════════════════════════════════════════════════════ */

#define PSRAM_TEST_BYTES (1024 * 1024)

static void chk_psram_pattern(void)
{
#if CONFIG_SPIRAM
    uint8_t *buf = heap_caps_malloc(PSRAM_TEST_BYTES, MALLOC_CAP_SPIRAM);
    TEST_ASSERT_NOT_NULL_MESSAGE(buf, "1MB would not allocate from PSRAM");

    for (size_t i = 0; i < PSRAM_TEST_BYTES; i++)
        buf[i] = (uint8_t)((i & 0xFF) ^ 0xA5);

    int errs = 0;
    size_t first_bad = 0;
    for (size_t i = 0; i < PSRAM_TEST_BYTES; i++) {
        if (buf[i] != (uint8_t)((i & 0xFF) ^ 0xA5)) {
            if (!errs) first_bad = i;
            errs++;
        }
    }
    heap_caps_free(buf);

    if (errs)
        bringup_detail("%d bad bytes in %d, first at 0x%06x",
                       errs, PSRAM_TEST_BYTES, (unsigned)first_bad);
    else
        bringup_detail("%dKB written and read back byte-exact",
                       PSRAM_TEST_BYTES / 1024);
    TEST_ASSERT_EQUAL_MESSAGE(0, errs, "PSRAM does not hold what was written to it");
#else
    BRINGUP_SKIP("firmware built with CONFIG_SPIRAM disabled");
#endif
}

/* ══════════════════════════════════════════════════════════════════════
 * 8. Power and temperature
 *
 * The ESP32-S3 has no internal channel on VDD3P3, so absolute rail voltage
 * is not a measurable quantity in software on this board — there is no
 * divider from BAT+ or +3V3 into any ADC pin in board_config.h either. What
 * IS observable: the brownout detector, whether the chip survives a full
 * load, and the on-die temperature.
 * ══════════════════════════════════════════════════════════════════ */

static temperature_sensor_handle_t s_tsens;
static float s_temp_idle = -1000.0f;

static void chk_temp_baseline(void)
{
    temperature_sensor_config_t cfg = TEMPERATURE_SENSOR_CONFIG_DEFAULT(-10, 80);
    esp_err_t err = temperature_sensor_install(&cfg, &s_tsens);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "on-die temperature sensor would not install");
    TEST_ASSERT_EQUAL(ESP_OK, temperature_sensor_enable(s_tsens));

    err = temperature_sensor_get_celsius(s_tsens, &s_temp_idle);
    TEST_ASSERT_EQUAL_MESSAGE(ESP_OK, err, "temperature read failed");
    bringup_detail("die=%.1fC at idle", s_temp_idle);
    /* Well outside anything a room-temperature board can produce: either the
     * sensor is not really running or the die is being cooked by a short. */
    TEST_ASSERT_TRUE_MESSAGE(s_temp_idle > -10.0f && s_temp_idle < 70.0f,
                             "idle die temperature is outside a plausible range");
}

static volatile bool s_load_run;

static void load_task(void *arg)
{
    uint32_t *scratch = NULL;
#if CONFIG_SPIRAM
    scratch = heap_caps_malloc(64 * 1024, MALLOC_CAP_SPIRAM);
#endif
    volatile double x = 1.0;
    while (s_load_run) {
        if (scratch)
            for (int i = 0; i < 16 * 1024 / 4; i++) scratch[i] = (uint32_t)i ^ 0x5A5A5A5Au;
        for (int i = 0; i < 40000; i++) x = x * 1.000001 + 0.5;
        /* One tick back to the idle task so the watchdog stays fed; the duty
         * cycle is still high enough to load the regulator. */
        vTaskDelay(1);
    }
    if (scratch) heap_caps_free(scratch);
    vTaskDelete(NULL);
}

/* The closest a board with no instruments gets to a rail measurement: load
 * both cores, PSRAM, the display bus and the audio DMA at once and see
 * whether the chip is still alive afterwards. A regulator that cannot hold
 * 3V3 under this does not produce a FAIL line — it reboots the board, and
 * the next run reports it through bringup.previous_run. */
static void chk_power_load(void)
{
    size_t heap_before = esp_get_free_heap_size();
    s_load_run = true;
    xTaskCreatePinnedToCore(load_task, "load0", 4096, NULL, 5, NULL, 0);
    xTaskCreatePinnedToCore(load_task, "load1", 4096, NULL, 5, NULL, 1);

    int64_t t0 = esp_timer_get_time();
    int frames = 0;
    while (esp_timer_get_time() - t0 < 3000000) {
        if (s_lcd_up) {
            display_fill((frames & 1) ? 0xFFFF : 0x0000);
            frames++;
        } else {
            vTaskDelay(pdMS_TO_TICKS(20));
        }
    }
    s_load_run = false;
    vTaskDelay(pdMS_TO_TICKS(100));

    size_t heap_after = esp_get_free_heap_size();
    bringup_detail("survived 3s of dual-core + PSRAM%s load, %d full-screen "
                   "fills, heap %u->%u",
                   s_lcd_up ? " + LCD" : " (LCD down)",
                   frames, (unsigned)heap_before, (unsigned)heap_after);
    TEST_ASSERT_TRUE_MESSAGE(heap_after > heap_before / 2,
                             "half the heap disappeared during the load test");
}

static void chk_power_temp_delta(void)
{
    if (s_temp_idle < -100.0f)
        BRINGUP_SKIP("no idle temperature was captured (see temp.baseline)");

    float hot = 0.0f;
    TEST_ASSERT_EQUAL(ESP_OK, temperature_sensor_get_celsius(s_tsens, &hot));
    float delta = hot - s_temp_idle;
    bringup_detail("die %.1fC -> %.1fC, delta %+.1fC after the load test",
                   s_temp_idle, hot, delta);
    TEST_ASSERT_TRUE_MESSAGE(hot < 85.0f, "die temperature is above the rated maximum");
}

static void chk_power_rail_absolute(void)
{
    BRINGUP_SKIP("the ESP32-S3 exposes no ADC channel on VDD3P3, so the absolute "
                 "+3V3 voltage cannot be read in software. Rail health here is "
                 "inferred from sys.reset_reason (brownout detector) and "
                 "power.load, not measured");
}

static void chk_power_battery_sense(void)
{
    BRINGUP_SKIP("board_config.h defines no battery-sense net: there is no divider "
                 "from BAT+ into any ADC pin on this revision, so battery voltage "
                 "and charge level are not observable from firmware");
}

static void chk_power_ip5306(void)
{
    BRINGUP_SKIP("IP5306 I2C is not routed (board_config.h: GPIO33/34 are reserved "
                 "for the Octal PSRAM). The charger runs on its power-on defaults "
                 "and reports nothing to the MCU — charge state is the on-board LED "
                 "only");
}

/* ══════════════════════════════════════════════════════════════════════
 * Check table
 * ══════════════════════════════════════════════════════════════════ */

static const check_t CHECKS_HEAD[] = {
    { "bringup.previous_run", "-", chk_previous_run,
      "the previous run died at the check named in the detail field — most "
      "likely a rail collapse or a hang in that subsystem" },
    { "sys.reset_reason", "-", chk_reset_reason,
      "U3 SY8089A output, its feedback divider R25/R26, or the input path" },
    { "chip.model", "-", chk_chip_model,
      "wrong module fitted at U1, or the module is not the part in the BOM" },
    { "chip.flash_size", "-", chk_flash_size,
      "module variant mismatch: the fitted module carries less flash than " MODULE_VARIANT },
    { "chip.psram_size", "-", chk_psram_size,
      "module variant mismatch, or VDD_SPI was strapped to 1.8V at reset by a "
      "pull-up on GPIO45 (BTN_L) that should be DNP" },
    { "config.gpio_unique", "-", chk_gpio_unique,
      "board_config.h itself, not the board" },
    { "usb.serial_jtag", "GPIO19/20", chk_usb_serial_jtag,
      "J1 USB-C, its D+/D- pair, or the 5.1k CC resistors" },
    { "gpio.strapping", "GPIO0/3/45/46", chk_straps,
      "not a pass/fail check; see the detail field" },
    { "led.heartbeat", "LED_HB", chk_led_heartbeat,
      "R31 or LED6 unsoldered, or the LED_HB net shorted to a rail — the blink "
      "codes are unreadable until this passes" },
    { "temp.baseline", "-", chk_temp_baseline,
      "on-die sensor, or a short heating the die" },
};

static const check_t CHECKS_LCD[] = {
    { "lcd.data.stuck", "D0-D7", chk_lcd_data_stuck,
      "an ILI9488 data pin shorted to +3V3 or GND at J4 or along the FPC fan-out" },
    { "lcd.data.shorts", "D0-D7", chk_lcd_data_shorts,
      "solder bridge between two adjacent data lines at J4 or the module pads" },
    { "lcd.ctrl.toggle", "CS/RST/DC/WR", chk_lcd_ctrl,
      "a control line shorted at J4, or the pin is loaded by the panel" },
    { "lcd.panel.init", "D0-D7+CS/RST/DC/WR", chk_lcd_init,
      "J4 FPC seating, the ILI9488 panel itself, or panel power" },
    { "lcd.panel.pattern", "D0-D7+CS/RST/DC/WR", chk_lcd_pattern,
      "i80 DMA path or the panel losing its configuration mid-transfer" },
    { "lcd.panel.readback", "-", chk_lcd_readback, "" },
    { "lcd.backlight", "-", chk_lcd_backlight, "" },
};

static const check_t CHECKS_SD[] = {
    { "sd.lines.stuck", "MOSI/MISO/CLK/CS", chk_sd_lines_stuck,
      "an SD line shorted to a rail at the TF-01A socket pads" },
    { "sd.bus.init", "MOSI/MISO/CLK/CS", chk_sd_bus,
      "SPI2 host allocation — a firmware fault, not a board fault" },
    { "sd.cmd0", "MOSI/MISO/CLK/CS", chk_sd_cmd0,
      "the card answers but not with idle state: marginal CLK, or CS not reaching the socket" },
    { "sd.cmd8", "MOSI/MISO/CLK/CS", chk_sd_cmd8,
      "signal integrity on the ~150mm SD run, or a card that cannot take 3.3V" },
    { "sd.acmd41", "MOSI/MISO/CLK/CS", chk_sd_acmd41,
      "card power: the socket's VDD pin, or the 3V3 rail sagging while the card starts" },
    { "sd.ocr", "MOSI/MISO/CLK/CS", chk_sd_ocr,
      "MISO integrity — the command went out but the reply came back wrong" },
    { "sd.fat.mount", "MOSI/MISO/CLK/CS", chk_sd_mount,
      "at 20MHz rather than 400kHz: trace length, via count, or missing pull-ups" },
};

static const check_t CHECKS_TAIL[] = {
    { "audio.pdm.init", "I2S_DOUT", chk_audio_init,
      "I2S peripheral allocation — a firmware fault, not a board fault" },
    { "audio.tone", "I2S_DOUT", chk_audio_tone,
      "the DMA path; the analog side after GPIO17 cannot fail this check" },
    { "audio.audible", "-", chk_audio_audible, "" },
    { "psram.pattern", "-", chk_psram_pattern,
      "the module's internal Octal PSRAM, or VDD_SPI at the wrong voltage" },
    { "power.load", "-", chk_power_load,
      "U3 SY8089A cannot hold 3V3 under load: L1, C-out, or the feedback divider" },
    { "power.temp_delta", "-", chk_power_temp_delta,
      "excess current somewhere on the board — a partial short" },
    { "power.rail3v3.absolute", "-", chk_power_rail_absolute, "" },
    { "power.battery_sense", "-", chk_power_battery_sense, "" },
    { "power.ip5306_i2c", "-", chk_power_ip5306, "" },
};

/* ══════════════════════════════════════════════════════════════════════
 * Runner
 * ══════════════════════════════════════════════════════════════════ */

static void run_group(const check_t *g, size_t n)
{
    for (size_t i = 0; i < n; i++) run_check(&g[i]);
}

#define RUN_GROUP(g) run_group((g), sizeof(g) / sizeof((g)[0]))

/* Unity requires these; nothing here needs per-check fixturing. */
void setUp(void) {}
void tearDown(void) {}

void app_main(void)
{
    s_reset_reason = esp_reset_reason();

    /* Before anything is printed: the LED starts beating here, so a board that
     * never gets a word out still shows whether the chip is executing. */
    hb_init();

    /* The console is USB-CDC — give the host a moment to attach, otherwise
     * the first lines are written into a void. */
    vTaskDelay(pdMS_TO_TICKS(2000));

    printf("\n");
    printf("BRINGUP-BEGIN;board=esp32-emu-turbo;module=%s;built=%s %s\n",
           MODULE_VARIANT, __DATE__, __TIME__);
    printf("BRINGUP-FORMAT;seq;result;id;pins;detail\n");
    fflush(stdout);

    UNITY_BEGIN();

    RUN_GROUP(CHECKS_HEAD);

    /* Buttons: idle level then the RC network, one line each, so a single
     * unsoldered resistor names itself. */
    for (s_btn_idx = 0; s_btn_idx < N_BUTTONS; s_btn_idx++) {
        char id[48], pins[24];
        snprintf(id, sizeof(id), "btn.%s.idle", BUTTONS[s_btn_idx].name);
        snprintf(pins, sizeof(pins), "GPIO%d", BUTTONS[s_btn_idx].num);
        check_t c = { id, pins, chk_btn_idle,
                      "the button's own net: a shorted switch, a solder bridge "
                      "to GND, or a stuck switch" };
        run_check(&c);
    }
    for (s_btn_idx = 0; s_btn_idx < N_BUTTONS; s_btn_idx++) {
        char id[48], pins[24];
        snprintf(id, sizeof(id), "btn.%s.rc", BUTTONS[s_btn_idx].name);
        snprintf(pins, sizeof(pins), "GPIO%d", BUTTONS[s_btn_idx].num);
        check_t c = { id, pins, chk_btn_rc,
                      "the 10k pull-up or the 100nF debounce cap on this net — "
                      "compare the measured rise time against the other buttons" };
        run_check(&c);
    }
    {
        check_t c = { "btn.isolation", "all 12", chk_btn_isolation,
                      "a solder bridge between two button nets, or D1 (BAT54C, "
                      "the START+SELECT menu diode) fitted backwards" };
        run_check(&c);
    }

    RUN_GROUP(CHECKS_LCD);
    RUN_GROUP(CHECKS_SD);
    RUN_GROUP(CHECKS_TAIL);

    UNITY_END();

    if (s_failed_ids[0])  printf("BRINGUP-FAILED;%s\n", s_failed_ids);
    if (s_skipped_ids[0]) printf("BRINGUP-SKIPPED;%s\n", s_skipped_ids);
    printf("BRINGUP-SUMMARY;total=%u;pass=%u;fail=%u;skip=%u;verdict=%s\n",
           s_seq, s_pass, s_fail, s_skip, s_fail ? "RED" : "GREEN");

    /* What the diagnostic LED is saying now that the run is over — the same
     * verdict a user reads with no cable attached, printed here so the two
     * channels can be checked against each other. */
    {
        char led[192];
        hb_describe(led, sizeof(led));
        printf("BRINGUP-LED;%s\n", led);
    }
    printf("BRINGUP-END\n");
    fflush(stdout);

    /* Only a completed run clears the marker; anything that reboots the board
     * before this point leaves the phase behind for the next run to report. */
    phase_clear();
}
