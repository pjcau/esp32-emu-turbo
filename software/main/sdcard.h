/*
 * ESP32 Emu Turbo — SD Card Driver
 * SPI mode, FAT32 filesystem, ROM file browser
 */

#pragma once

#include "esp_err.h"

/**
 * Initialize SPI bus and mount the SD card as FAT32 at SD_MOUNT_POINT.
 * Returns ESP_OK on success, or an error if no card is inserted.
 */
esp_err_t sdcard_init(void);

/**
 * List ROM files found on the SD card.
 * Scans /sdcard/roms/<system>/ directories and logs file names.
 * Returns the total number of ROM files found.
 */
int sdcard_list_roms(void);

/**
 * Unmount the SD card and free the SPI bus.
 */
void sdcard_deinit(void);
