/*
 * ESP32 Emu Turbo — SD Card Driver
 * SPI mode, FAT32 filesystem, ROM file browser
 */

#include "sdcard.h"
#include "board_config.h"

#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/spi_common.h"

#include <dirent.h>
#include <string.h>

static const char *TAG = "sdcard";

static sdmmc_card_t *s_card = NULL;

esp_err_t sdcard_init(void)
{
    ESP_LOGI(TAG, "Initializing SD card (SPI mode)");

    /* SPI bus configuration */
    spi_bus_config_t bus_cfg = {
        .mosi_io_num   = SD_MOSI,
        .miso_io_num   = SD_MISO,
        .sclk_io_num   = SD_CLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4096,
    };

    esp_err_t ret = spi_bus_initialize(SD_SPI_HOST, &bus_cfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI bus init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    /* SD card mount config */
    esp_vfs_fat_sdmmc_mount_config_t mount_cfg = {
        .format_if_mount_failed = false,
        .max_files              = 5,
        .allocation_unit_size   = 16 * 1024,
    };

    /* SPI device for the SD card */
    sdmmc_host_t host = SDSPI_HOST_DEFAULT();
    host.max_freq_khz = SD_SPI_FREQ_KHZ;

    sdspi_device_config_t slot_cfg = SDSPI_DEVICE_CONFIG_DEFAULT();
    slot_cfg.gpio_cs   = SD_CS;
    slot_cfg.host_id   = SD_SPI_HOST;

    ret = esp_vfs_fat_sdspi_mount(SD_MOUNT_POINT, &host, &slot_cfg, &mount_cfg, &s_card);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SD card mount failed: %s", esp_err_to_name(ret));
        spi_bus_free(SD_SPI_HOST);
        return ret;
    }

    /* Log card info */
    sdmmc_card_print_info(stdout, s_card);
    ESP_LOGI(TAG, "SD card mounted at %s", SD_MOUNT_POINT);
    return ESP_OK;
}

int sdcard_list_roms(void)
{
    static const char *systems[] = {
        "nes", "snes", "gb", "gbc", "sms", "gg", "pce", "gen", "lynx", "gw"
    };
    int total = 0;

    ESP_LOGI(TAG, "Scanning ROM directories...");

    for (int s = 0; s < sizeof(systems) / sizeof(systems[0]); s++) {
        char path[64];
        snprintf(path, sizeof(path), "%s/roms/%s", SD_MOUNT_POINT, systems[s]);

        DIR *dir = opendir(path);
        if (!dir) continue;

        int count = 0;
        struct dirent *entry;
        while ((entry = readdir(dir)) != NULL) {
            if (entry->d_type == DT_REG) {
                ESP_LOGI(TAG, "  [%s] %s", systems[s], entry->d_name);
                count++;
            }
        }
        closedir(dir);

        if (count > 0) {
            ESP_LOGI(TAG, "  %s: %d ROM(s)", systems[s], count);
            total += count;
        }
    }

    ESP_LOGI(TAG, "Total ROMs found: %d", total);
    return total;
}

void sdcard_deinit(void)
{
    if (s_card) {
        esp_vfs_fat_sdcard_unmount(SD_MOUNT_POINT, s_card);
        s_card = NULL;
        spi_bus_free(SD_SPI_HOST);
        ESP_LOGI(TAG, "SD card unmounted");
    }
}
