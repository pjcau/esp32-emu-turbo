/* GB benchmark — isolated to avoid symbol conflicts */
#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "bench.h"
#include "gnuboy.h"

static uint16_t g_gb_fb[160 * 144];
static int16_t g_gb_audio[4096];
static void vid_noop(void *b) { (void)b; }
static void aud_noop(void *b, size_t l) { (void)b; (void)l; }

void bench_gb(const char *path, const char *label) {
    size_t sz;
    uint8_t *rom = bench_load_file(path, &sz);
    if (!rom) return;
    bench_gb_rom(rom, sz, label);
    heap_caps_free(rom);
}

void bench_gb_rom(uint8_t *rom, size_t sz, const char *label) {
    if (gnuboy_init(32000, GB_AUDIO_MONO_S16, GB_PIXEL_565_LE, vid_noop, aud_noop) != 0) {
        printf("[BENCH] %s: init failed\n", label);
        heap_caps_free(rom); return;
    }
    gnuboy_set_framebuffer(g_gb_fb);
    gnuboy_set_soundbuffer(g_gb_audio, sizeof(g_gb_audio));
    if (gnuboy_load_rom(rom, sz) != 0) {
        printf("[BENCH] %s: ROM load failed\n", label);
        heap_caps_free(rom); return;
    }
    gnuboy_reset(true);

    for (int i = 0; i < WARMUP_FRAMES; i++) gnuboy_run(true);

    int64_t start = esp_timer_get_time();
    for (int i = 0; i < BENCH_FRAMES; i++) gnuboy_run(true);
    int64_t elapsed = esp_timer_get_time() - start;

    bench_print_result(label, BENCH_FRAMES, elapsed);
    gnuboy_free_rom();
}
