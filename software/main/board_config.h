/*
 * ESP32 Emu Turbo — Board Configuration
 * All GPIO assignments and hardware constants.
 * Source of truth: hardware/kicad/02-mcu.kicad_sch
 */

#pragma once

#include "driver/gpio.h"

/* ── Display: ST7796S 320x480, 8-bit 8080 parallel ───────────────── */

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
#define LCD_RD              GPIO_NUM_3
#define LCD_BL              GPIO_NUM_45

/* Backlight PWM */
#define LCD_BL_LEDC_TIMER   LEDC_TIMER_0
#define LCD_BL_LEDC_CHANNEL LEDC_CHANNEL_0
#define LCD_BL_LEDC_FREQ    5000      /* 5 kHz PWM */
#define LCD_BL_LEDC_DUTY    200       /* out of 255 (~78%) */

/* ── SD Card: SPI mode ────────────────────────────────────────────── */

#define SD_MOSI             GPIO_NUM_36
#define SD_MISO             GPIO_NUM_37
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

/* ── Buttons: active-low, external 10k pull-up + 100nF debounce ── */

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
#define BTN_L               GPIO_NUM_35
#define BTN_R               GPIO_NUM_19

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

/* ── Power: IP5306 ────────────────────────────────────────────────── */

#define IP5306_I2C_ADDR     0x75
#define IP5306_I2C_SDA      GPIO_NUM_33
#define IP5306_I2C_SCL      GPIO_NUM_34
#define IP5306_I2C_FREQ_HZ  100000    /* 100 kHz */
#define IP5306_I2C_PORT     I2C_NUM_0
