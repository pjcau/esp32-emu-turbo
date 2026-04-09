/*
 * ESP32 Emu Turbo — Board Configuration
 * All GPIO assignments and hardware constants.
 * Source of truth: hardware/kicad/02-mcu.kicad_sch
 */

#pragma once

#include "driver/gpio.h"

/* ── Display: ILI9488 320x480, 8-bit 8080 parallel ───────────────── */

#define LCD_H_RES           320
#define LCD_V_RES           480
#define LCD_BIT_WIDTH       8
#define LCD_CLK_HZ          (20 * 1000 * 1000)  /* 20 MHz write clock */

/* Data bus D0-D7: GPIO4-11 (contiguous for DMA efficiency) */
#define LCD_D0              GPIO_NUM_4
#define LCD_D1              GPIO_NUM_5
#define LCD_D2              GPIO_NUM_6
#define LCD_D3              GPIO_NUM_7
#define LCD_D4              GPIO_NUM_8
#define LCD_D5              GPIO_NUM_9
#define LCD_D6              GPIO_NUM_10
#define LCD_D7              GPIO_NUM_11

/* Control lines */
#define LCD_CS              GPIO_NUM_12
#define LCD_RST             GPIO_NUM_13
#define LCD_DC              GPIO_NUM_14
#define LCD_WR              GPIO_NUM_46
/* LCD_RD: tied HIGH on PCB (no GPIO needed, no read-back from ILI9488) */
/* LCD_BL: tied to 3V3 on PCB via resistor (always-on backlight) */

/* Backlight: always-on (tied to 3V3 on PCB), no PWM control */

/* ── SD Card: SPI mode ────────────────────────────────────────────── */

#define SD_MOSI             GPIO_NUM_44
#define SD_MISO             GPIO_NUM_43
#define SD_CLK              GPIO_NUM_38
#define SD_CS               GPIO_NUM_39
#define SD_SPI_HOST         SPI2_HOST
#define SD_SPI_FREQ_KHZ     40000     /* 40 MHz */
#define SD_MOUNT_POINT      "/sdcard"

/* ── Audio: I2S → PAM8403 ────────────────────────────────────────── */

#define I2S_BCLK            GPIO_NUM_15
#define I2S_LRCK            GPIO_NUM_16
#define I2S_DOUT            GPIO_NUM_17
#define I2S_NUM             I2S_NUM_0
#define AUDIO_SAMPLE_RATE   32000     /* 32 kHz */
#define AUDIO_BITS          16

/* ── Buttons: active-low, 10k pull-up + 100nF debounce ────────── */
/* NOTE: BTN_L (GPIO45) has NO external pull-up (R14 DNP).
 * GPIO45 is a VDD_SPI strapping pin: external pull-up would force
 * VDD_SPI=1.8V, breaking Octal PSRAM (needs 3.3V).
 * Firmware MUST enable internal pull-up after boot:
 *   gpio_set_pull_mode(BTN_L, GPIO_PULLUP_ONLY);
 * Internal pull-up (~45k) is sufficient for button debounce. */

#define BTN_UP              GPIO_NUM_40
#define BTN_DOWN            GPIO_NUM_41
#define BTN_LEFT            GPIO_NUM_42
#define BTN_RIGHT           GPIO_NUM_1
#define BTN_A               GPIO_NUM_2
#define BTN_B               GPIO_NUM_48
#define BTN_X               GPIO_NUM_47
#define BTN_Y               GPIO_NUM_21
#define BTN_START            GPIO_NUM_18
#define BTN_SELECT          GPIO_NUM_0
#define BTN_L               GPIO_NUM_45
#define BTN_R               GPIO_NUM_3

/* ── USB: native USB on ESP32-S3 (firmware flashing + debug) ────── */

#define USB_DP              GPIO_NUM_20
#define USB_DN              GPIO_NUM_19

/* Button bitmask positions */
#define BTN_MASK_UP         (1 << 0)
#define BTN_MASK_DOWN       (1 << 1)
#define BTN_MASK_LEFT       (1 << 2)
#define BTN_MASK_RIGHT      (1 << 3)
#define BTN_MASK_A          (1 << 4)
#define BTN_MASK_B          (1 << 5)
#define BTN_MASK_X          (1 << 6)
#define BTN_MASK_Y          (1 << 7)
#define BTN_MASK_START      (1 << 8)
#define BTN_MASK_SELECT     (1 << 9)
#define BTN_MASK_L          (1 << 10)
#define BTN_MASK_R          (1 << 11)

/* Menu button: SW13 triggers START+SELECT simultaneously via BAT54C diode D1.
 * Firmware detects the combo — no dedicated GPIO needed. */
#define BTN_MENU_COMBO      (BTN_MASK_START | BTN_MASK_SELECT)

/* ── Power: IP5306 ────────────────────────────────────────────────── */

#define IP5306_I2C_ADDR     0x75
/* IP5306 I2C not routed on PCB — GPIO33/34 reserved for Octal PSRAM */
/* IP5306 is configured via power-on defaults (no I2C control) */
// #define IP5306_I2C_SDA      GPIO_NUM_NC
// #define IP5306_I2C_SCL      GPIO_NUM_NC
#define IP5306_I2C_FREQ_HZ  100000    /* 100 kHz */
#define IP5306_I2C_PORT     I2C_NUM_0
