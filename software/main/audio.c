/*
 * ESP32 Emu Turbo — Audio Driver
 * I2S PDM TX mode → PAM8403 Class-D amplifier → 28mm speaker
 *
 * Architecture: ESP32-S3 PDM output on I2S_DOUT (GPIO17) produces a 1-bit
 * sigma-delta stream. The existing RC network (0.47uF coupling cap + 20k bias
 * resistors + PAM8403 input impedance) acts as a low-pass filter to extract
 * the analog audio signal. No external DAC needed.
 *
 * PDM TX only uses the DOUT pin (BCLK/LRCK are not externally connected,
 * which matches the PCB design where only GPIO17 is routed to PAM8403).
 */

#include "audio.h"
#include "board_config.h"

#include "esp_log.h"
#include "esp_check.h"
#include "driver/i2s_pdm.h"
#include "freertos/FreeRTOS.h"

#include <math.h>
#include <string.h>

static const char *TAG = "audio";

static i2s_chan_handle_t s_tx_chan = NULL;

esp_err_t audio_init(void)
{
    ESP_LOGI(TAG, "Initializing I2S PDM audio (%d Hz, %d-bit)",
             AUDIO_SAMPLE_RATE, AUDIO_BITS);

    /* Allocate a new TX channel */
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM, I2S_ROLE_MASTER);
    chan_cfg.dma_desc_num  = 4;
    chan_cfg.dma_frame_num = 256;

    ESP_RETURN_ON_ERROR(
        i2s_new_channel(&chan_cfg, &s_tx_chan, NULL),
        TAG, "I2S channel alloc failed"
    );

    /* PDM TX mode: 1-bit sigma-delta output on DOUT pin.
     * The oversampling ratio and internal clock are managed by the driver.
     * Only the DOUT pin is needed — no BCLK/WS external connections. */
    i2s_pdm_tx_config_t pdm_cfg = {
        .clk_cfg = I2S_PDM_TX_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
        .slot_cfg = I2S_PDM_TX_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO),
        .gpio_cfg = {
            .clk = I2S_GPIO_UNUSED,
            .dout = I2S_DOUT,
            .invert_flags = {
                .clk_inv = false,
            },
        },
    };

    ESP_RETURN_ON_ERROR(
        i2s_channel_init_pdm_tx_mode(s_tx_chan, &pdm_cfg),
        TAG, "I2S PDM TX mode init failed"
    );

    ESP_RETURN_ON_ERROR(
        i2s_channel_enable(s_tx_chan),
        TAG, "I2S channel enable failed"
    );

    ESP_LOGI(TAG, "Audio initialized: I2S PDM TX %d Hz mono", AUDIO_SAMPLE_RATE);
    return ESP_OK;
}

esp_err_t audio_play_test_tone(int duration_ms)
{
    if (!s_tx_chan) return ESP_ERR_INVALID_STATE;

    /* Three short 1 kHz beeps rather than one continuous tone: with no PDM
     * reconstruction filter on the board (R38) the carrier hisses for as
     * long as the channel plays, and a beep PATTERN stays recognizable over
     * that hiss where a single tone drowned in it. 1 kHz sits near the 28mm
     * speaker's efficiency peak and the ear's sensitive band. */
    const int freq = 1000;
    const int total_samples = (AUDIO_SAMPLE_RATE * duration_ms) / 1000;
    const int seg = total_samples / 6;   /* beep,gap,beep,gap,beep,gap */
    const int chunk = 256;

    int16_t buf[chunk];
    size_t bytes_written;

    ESP_LOGI(TAG, "Playing 3x %d Hz beeps over %d ms", freq, duration_ms);

    for (int i = 0; i < total_samples; i += chunk) {
        int n = (total_samples - i < chunk) ? (total_samples - i) : chunk;
        for (int j = 0; j < n; j++) {
            int s = i + j;
            bool on = seg > 0 && (s / seg) % 2 == 0;   /* segments 0,2,4 beep */
            float t = (float)s / AUDIO_SAMPLE_RATE;
            buf[j] = on ? (int16_t)(16000.0f * sinf(2.0f * M_PI * freq * t)) : 0;
        }
        i2s_channel_write(s_tx_chan, buf, n * sizeof(int16_t), &bytes_written, portMAX_DELAY);
    }

    /* Flush with silence */
    memset(buf, 0, sizeof(buf));
    i2s_channel_write(s_tx_chan, buf, sizeof(buf), &bytes_written, portMAX_DELAY);

    ESP_LOGI(TAG, "Test tone complete");
    return ESP_OK;
}

esp_err_t audio_play_note(int freq_hz, int duration_ms)
{
    if (!s_tx_chan) return ESP_ERR_INVALID_STATE;

    const int total = (AUDIO_SAMPLE_RATE * duration_ms) / 1000;
    const int ramp = AUDIO_SAMPLE_RATE / 200;   /* 5 ms fade in/out: no click */
    const int chunk = 256;
    int16_t buf[chunk];
    size_t bytes_written;

    for (int i = 0; i < total; i += chunk) {
        int n = (total - i < chunk) ? (total - i) : chunk;
        for (int j = 0; j < n; j++) {
            int s = i + j;
            float env = 1.0f;
            if (freq_hz <= 0) env = 0.0f;                          /* rest */
            else if (s < ramp) env = (float)s / ramp;
            else if (total - s < ramp) env = (float)(total - s) / ramp;
            float t = (float)s / AUDIO_SAMPLE_RATE;
            buf[j] = (int16_t)(16000.0f * env * sinf(2.0f * M_PI * freq_hz * t));
        }
        i2s_channel_write(s_tx_chan, buf, n * sizeof(int16_t), &bytes_written, portMAX_DELAY);
    }
    return ESP_OK;
}

esp_err_t audio_play_melody(void)
{
    if (!s_tx_chan) return ESP_ERR_INVALID_STATE;

    /* Super Mario Bros. overworld intro: E5 E5 E5 C5 E5 G5 G4 — instantly
     * recognizable on a 28mm speaker, ~1.6 s. 0 Hz = rest. */
    static const struct { int hz, ms; } notes[] = {
        {659, 120}, {0, 40}, {659, 120}, {0, 160}, {659, 120}, {0, 160},
        {523, 120}, {0, 40}, {659, 120}, {0, 160}, {784, 200}, {0, 400},
        {392, 200},
    };
    ESP_LOGI(TAG, "Playing melody (%u notes)", (unsigned)(sizeof(notes) / sizeof(notes[0])));
    for (unsigned i = 0; i < sizeof(notes) / sizeof(notes[0]); i++)
        audio_play_note(notes[i].hz, notes[i].ms);

    int16_t buf[256];
    size_t bytes_written;
    memset(buf, 0, sizeof(buf));
    i2s_channel_write(s_tx_chan, buf, sizeof(buf), &bytes_written, portMAX_DELAY);
    ESP_LOGI(TAG, "Melody complete");
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
