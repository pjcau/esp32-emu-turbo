idf_component_register(
    SRCS
        "bringup_test.c"
        # Production drivers, compiled from software/main so the bring-up run
        # exercises exactly the code the application ships. main.c is not
        # listed: it owns app_main, and this project has its own.
        "../../main/display.c"
        "../../main/audio.c"
        "../../main/sdcard.c"
    INCLUDE_DIRS
        "."
        "../../main"
    REQUIRES
        unity
        esp_lcd
        esp_driver_i2s
        esp_driver_spi
        esp_driver_gpio
        esp_driver_tsens
        esp_psram
        esp_timer
        spi_flash
        esp_hw_support
        hal
        sdmmc
        fatfs
        vfs
)
