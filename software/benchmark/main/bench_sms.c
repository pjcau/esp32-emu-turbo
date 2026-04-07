/* SMS benchmark — isolated to avoid symbol conflicts */
#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "bench.h"
#include "shared.h"

static uint8_t *sms_buf;

void bench_sms(const char *path, const char *label) {
    size_t sz;
    uint8_t *rom = bench_load_file(path, &sz);
    if (!rom) return;
    bench_sms_rom(rom, sz, label);
    heap_caps_free(rom);
}

void bench_sms_rom(uint8_t *rom, size_t sz, const char *label) {
    system_reset_config();
    option.sndrate = 32000;

    sms_buf = heap_caps_calloc(288 * 300, 1, MALLOC_CAP_SPIRAM);
    memset(&bitmap, 0, sizeof(bitmap));
    bitmap.data = sms_buf;
    bitmap.width = 288;
    bitmap.height = 300;
    bitmap.pitch = 288;
    bitmap.granularity = 1;

    if (load_rom(rom, sz, sz) != 1) {
        printf("[BENCH] %s: ROM load failed\n", label);
        heap_caps_free(rom); heap_caps_free(sms_buf); return;
    }
    system_poweron();

    for (int i = 0; i < WARMUP_FRAMES; i++) {
        input.pad[0] = 0; input.system = 0;
        system_frame(0);
    }

    int64_t start = esp_timer_get_time();
    for (int i = 0; i < BENCH_FRAMES; i++) {
        input.pad[0] = 0; input.system = 0;
        system_frame(0);
    }
    int64_t elapsed = esp_timer_get_time() - start;

    bench_print_result(label, BENCH_FRAMES, elapsed);
    system_shutdown();
    heap_caps_free(sms_buf);
}
