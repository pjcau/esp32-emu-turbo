/* PCE benchmark — isolated to avoid symbol conflicts */
#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "bench.h"
#include "pce-go.h"
#include "pce.h"

/* pce_run() runs one frame; pce_run() is an infinite loop — do NOT use it */

static uint8_t *g_pce_fb;

/* OSD callbacks required by pce-go */
uint8_t *osd_gfx_framebuffer(int w, int h) {
    (void)w; (void)h;
    if (!g_pce_fb) g_pce_fb = heap_caps_calloc(368 * 242, 1, MALLOC_CAP_SPIRAM);
    return g_pce_fb;
}
void osd_vsync(void) {}
void osd_input_read(uint8_t joypads[8]) { memset(joypads, 0, 8); }

void bench_pce(const char *path) {
    size_t sz;
    uint8_t *rom = bench_load_file(path, &sz);
    if (!rom) return;
    bench_pce_rom(rom, sz);
    heap_caps_free(rom);
}

void bench_pce_rom(uint8_t *rom, size_t sz) {
    if (InitPCE(32000, false) != 0) {
        printf("[BENCH] PCE: init failed\n");
        heap_caps_free(rom); return;
    }
    if (LoadCard(rom, sz) != 0) {
        printf("[BENCH] PCE: ROM load failed\n");
        heap_caps_free(rom); return;
    }
    ResetPCE(false);

    for (int i = 0; i < WARMUP_FRAMES; i++) pce_run();

    int64_t start = esp_timer_get_time();
    for (int i = 0; i < BENCH_FRAMES; i++) pce_run();
    int64_t elapsed = esp_timer_get_time() - start;

    bench_print_result("PCE", BENCH_FRAMES, elapsed);
    ShutdownPCE();
    if (g_pce_fb) { heap_caps_free(g_pce_fb); g_pce_fb = NULL; }
}
