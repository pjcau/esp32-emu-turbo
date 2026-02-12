/*
 * ESP32 Emu Turbo — Power Management
 * IP5306 charge-and-play IC, I2C interface (address 0x75)
 */

#pragma once

#include "esp_err.h"
#include <stdbool.h>

/**
 * Initialize I2C bus and probe for IP5306 at address 0x75.
 * Returns ESP_OK if the IP5306 responds, ESP_ERR_NOT_FOUND otherwise.
 * If not found, power functions return safe defaults.
 */
esp_err_t power_init(void);

/**
 * Get estimated battery percentage (0, 25, 50, 75, or 100).
 * Based on the IP5306 4-LED level register.
 * Returns -1 if IP5306 is not available.
 */
int power_get_battery_percent(void);

/**
 * Check if the device is currently charging via USB-C.
 * Returns false if IP5306 is not available.
 */
bool power_is_charging(void);
