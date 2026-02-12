/*
 * ESP32 Emu Turbo — Power Management
 * IP5306 charge-and-play IC, I2C interface (address 0x75)
 *
 * Register map (I2C variant):
 *   0x70: SYS_CTL0 — charge enable, boost enable
 *   0x71: SYS_CTL1 — boost settings
 *   0x72: SYS_CTL2 — shutdown settings
 *   0x78: READ0    — charge status bits
 *   0x7A: READ2    — battery level (4 LEDs)
 */

#include "power.h"
#include "board_config.h"

#include "esp_log.h"
#include "driver/i2c_master.h"

static const char *TAG = "power";

/* IP5306 register addresses */
#define IP5306_REG_SYS_CTL0     0x00
#define IP5306_REG_READ0        0x70
#define IP5306_REG_READ1        0x71
#define IP5306_REG_READ2        0x78

static i2c_master_bus_handle_t s_bus = NULL;
static i2c_master_dev_handle_t s_dev = NULL;
static bool s_available = false;

static esp_err_t ip5306_read_reg(uint8_t reg, uint8_t *val)
{
    return i2c_master_transmit_receive(s_dev, &reg, 1, val, 1, 100);
}

esp_err_t power_init(void)
{
    ESP_LOGI(TAG, "Initializing IP5306 power management (I2C)");

    /* I2C master bus */
    i2c_master_bus_config_t bus_cfg = {
        .i2c_port   = IP5306_I2C_PORT,
        .sda_io_num = IP5306_I2C_SDA,
        .scl_io_num = IP5306_I2C_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };

    esp_err_t ret = i2c_new_master_bus(&bus_cfg, &s_bus);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "I2C bus init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    /* Add IP5306 device */
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address  = IP5306_I2C_ADDR,
        .scl_speed_hz    = IP5306_I2C_FREQ_HZ,
    };

    ret = i2c_master_bus_add_device(s_bus, &dev_cfg, &s_dev);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "I2C device add failed: %s", esp_err_to_name(ret));
        return ret;
    }

    /* Probe: try reading a register */
    uint8_t val;
    ret = ip5306_read_reg(IP5306_REG_READ0, &val);
    if (ret == ESP_OK) {
        s_available = true;
        ESP_LOGI(TAG, "IP5306 detected (I2C @ 0x%02X)", IP5306_I2C_ADDR);
    } else {
        s_available = false;
        ESP_LOGW(TAG, "IP5306 not responding — non-I2C variant or not connected");
        ESP_LOGW(TAG, "Power functions will return defaults");
    }

    return ESP_OK;
}

int power_get_battery_percent(void)
{
    if (!s_available) return -1;

    uint8_t val;
    if (ip5306_read_reg(IP5306_REG_READ2, &val) != ESP_OK) return -1;

    /*
     * Bits [3:0] indicate battery level (4 LEDs):
     *   0x0F = 4 LEDs = 100%
     *   0x07 = 3 LEDs = 75%
     *   0x03 = 2 LEDs = 50%
     *   0x01 = 1 LED  = 25%
     *   0x00 = 0 LEDs = 0% (shutdown imminent)
     */
    int level = val & 0x0F;
    if (level == 0x0F) return 100;
    if (level == 0x07) return 75;
    if (level == 0x03) return 50;
    if (level == 0x01) return 25;
    return 0;
}

bool power_is_charging(void)
{
    if (!s_available) return false;

    uint8_t val;
    if (ip5306_read_reg(IP5306_REG_READ0, &val) != ESP_OK) return false;

    /* Bit 3: charge full flag (1 = fully charged, 0 = charging or not connected) */
    /* Bit 4: charge enable (1 = charging active) */
    return (val & 0x08) == 0;  /* not fully charged = still charging */
}
