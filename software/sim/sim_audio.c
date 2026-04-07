/**
 * Audio driver — SDL2 simulator implementation
 * I2S output simulated via SDL2 audio (32kHz, 16-bit, mono)
 */

#ifdef SIM_BUILD

#include "sim_hal.h"
#include <stdio.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static int g_audio_ok = 0;

int audio_sim_init(void) {
    if (sim_audio_init() != 0) {
        printf("[AUDIO] WARNING: audio not available\n");
        return 0;  /* non-fatal */
    }
    g_audio_ok = 1;
    printf("[AUDIO] I2S simulator: %dHz %d-bit mono\n",
           SIM_AUDIO_RATE, SIM_AUDIO_BITS);
    return 0;
}

void audio_sim_play_test_tone(int duration_ms) {
    if (!g_audio_ok) return;

    int total_samples = (SIM_AUDIO_RATE * duration_ms) / 1000;
    int16_t buf[1024];
    float phase = 0;
    float freq = 440.0f;
    float dt = 1.0f / SIM_AUDIO_RATE;

    printf("[AUDIO] Playing 440Hz tone for %dms...\n", duration_ms);

    int remaining = total_samples;
    while (remaining > 0) {
        int chunk = (remaining > 1024) ? 1024 : remaining;
        for (int i = 0; i < chunk; i++) {
            buf[i] = (int16_t)(sinf(phase) * 8000.0f);
            phase += 2.0f * M_PI * freq * dt;
            if (phase > 2.0f * M_PI) phase -= 2.0f * M_PI;
        }
        sim_audio_write(buf, chunk);
        remaining -= chunk;
    }
}

void audio_sim_write(const int16_t *samples, int count) {
    if (g_audio_ok) sim_audio_write(samples, count);
}

void audio_sim_stop(void) {
    printf("[AUDIO] Stopped\n");
}

#endif
