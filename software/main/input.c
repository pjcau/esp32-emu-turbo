/*
 * ESP32 Emu Turbo — Input Driver
 * 12 tact buttons, active-low with external 10k pull-up + 100nF RC debounce
 */

#include "input.h"
#include "board_config.h"

#include "esp_log.h"
#include "driver/gpio.h"

static const char *TAG = "input";

/* GPIO-to-bitmask mapping table */
static const struct {
    gpio_num_t gpio;
    uint16_t   mask;
    const char *name;
} s_buttons[] = {
    { BTN_UP,     BTN_MASK_UP,     "UP"     },
    { BTN_DOWN,   BTN_MASK_DOWN,   "DOWN"   },
    { BTN_LEFT,   BTN_MASK_LEFT,   "LEFT"   },
    { BTN_RIGHT,  BTN_MASK_RIGHT,  "RIGHT"  },
    { BTN_A,      BTN_MASK_A,      "A"      },
    { BTN_B,      BTN_MASK_B,      "B"      },
    { BTN_X,      BTN_MASK_X,      "X"      },
    { BTN_Y,      BTN_MASK_Y,      "Y"      },
    { BTN_START,  BTN_MASK_START,  "START"  },
    { BTN_SELECT, BTN_MASK_SELECT, "SELECT" },
    { BTN_L,      BTN_MASK_L,      "L"      },
    { BTN_R,      BTN_MASK_R,      "R"      },
};

#define NUM_BUTTONS (sizeof(s_buttons) / sizeof(s_buttons[0]))

esp_err_t input_init(void)
{
    ESP_LOGI(TAG, "Initializing %d buttons", (int)NUM_BUTTONS);

    for (int i = 0; i < NUM_BUTTONS; i++) {
        gpio_config_t cfg = {
            .pin_bit_mask = 1ULL << s_buttons[i].gpio,
            .mode         = GPIO_MODE_INPUT,
            .pull_up_en   = GPIO_PULLUP_DISABLE,   /* external 10k on PCB */
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type    = GPIO_INTR_DISABLE,
        };
        esp_err_t err = gpio_config(&cfg);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "Failed to configure GPIO%d (%s): %s",
                     s_buttons[i].gpio, s_buttons[i].name, esp_err_to_name(err));
        }
    }

    ESP_LOGI(TAG, "Input initialized: %d buttons", (int)NUM_BUTTONS);
    return ESP_OK;
}

uint16_t input_read(void)
{
    uint16_t state = 0;
    for (int i = 0; i < NUM_BUTTONS; i++) {
        /* Active-low: GPIO reads 0 when pressed */
        if (gpio_get_level(s_buttons[i].gpio) == 0) {
            state |= s_buttons[i].mask;
        }
    }
    return state;
}

const char *input_button_name(int bit)
{
    if (bit >= 0 && bit < (int)NUM_BUTTONS) {
        return s_buttons[bit].name;
    }
    return "?";
}
