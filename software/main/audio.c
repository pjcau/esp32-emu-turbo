/*
 * ESP32 Emu Turbo — Audio Driver
 * I2S standard mode → PAM8403 Class-D amplifier → 28mm speaker
 */

#include "audio.h"
#include "board_config.h"

#include "esp_log.h"
#include "driver/i2s_std.h"

#include <math.h>
#include <string.h>

static const char *TAG = "audio";

static i2s_chan_handle_t s_tx_chan = NULL;

esp_err_t audio_init(void)
{
    ESP_LOGI(TAG, "Initializing I2S audio (%d Hz, %d-bit)",
             AUDIO_SAMPLE_RATE, AUDIO_BITS);

    /* Allocate a new TX channel */
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num  = 4;
    chan_cfg.dma_frame_num = 256;

    ESP_RETURN_ON_ERROR(
        i2s_new_channel(&chan_cfg, &s_tx_chan, NULL),
        TAG, "I2S channel alloc failed"
    );

    /* Standard (Philips) mode config */
    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,
            .bclk = I2S_BCLK,
            .ws   = I2S_LRCK,
            .dout = I2S_DOUT,
            .din  = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };

    ESP_RETURN_ON_ERROR(
        i2s_channel_init_std_mode(s_tx_chan, &std_cfg),
        TAG, "I2S std mode init failed"
    );

    ESP_RETURN_ON_ERROR(
        i2s_channel_enable(s_tx_chan),
        TAG, "I2S channel enable failed"
    );

    ESP_LOGI(TAG, "Audio initialized: I2S %d Hz mono", AUDIO_SAMPLE_RATE);
    return ESP_OK;
}

esp_err_t audio_play_test_tone(int duration_ms)
{
    if (!s_tx_chan) return ESP_ERR_INVALID_STATE;

    const int freq = 440;  /* A4 */
    const int total_samples = (AUDIO_SAMPLE_RATE * duration_ms) / 1000;
    const int chunk = 256;

    int16_t buf[chunk];
    size_t bytes_written;

    ESP_LOGI(TAG, "Playing %d Hz tone for %d ms", freq, duration_ms);

    for (int i = 0; i < total_samples; i += chunk) {
        int n = (total_samples - i < chunk) ? (total_samples - i) : chunk;
        for (int j = 0; j < n; j++) {
            float t = (float)(i + j) / AUDIO_SAMPLE_RATE;
            buf[j] = (int16_t)(16000.0f * sinf(2.0f * M_PI * freq * t));
        }
        i2s_channel_write(s_tx_chan, buf, n * sizeof(int16_t), &bytes_written, portMAX_DELAY);
    }

    /* Flush with silence */
    memset(buf, 0, sizeof(buf));
    i2s_channel_write(s_tx_chan, buf, sizeof(buf), &bytes_written, portMAX_DELAY);

    ESP_LOGI(TAG, "Test tone complete");
    return ESP_OK;
}

void audio_stop(void)
{
    if (s_tx_chan) {
        i2s_channel_disable(s_tx_chan);
        i2s_del_channel(s_tx_chan);
        s_tx_chan = NULL;
        ESP_LOGI(TAG, "Audio stopped");
    }
}
