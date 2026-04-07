/* NES benchmark — isolated to avoid symbol conflicts */
#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_attr.h"
#include "bench.h"

#undef IRAM_ATTR
#include "nofrendo.h"
#include "nes/nes.h"
#include "nes/input.h"
#include "nes/rom.h"

static uint8_t g_vidbuf[NES_SCREEN_PITCH * NES_SCREEN_HEIGHT];
static void blit_noop(uint8_t *bmp) { (void)bmp; }

void bench_nes(const char *path) {
    size_t sz;
    uint8_t *rom = bench_load_file(path, &sz);
    if (!rom) return;
    bench_nes_rom(rom, sz);
    heap_caps_free(rom);
}

void bench_nes_rom(uint8_t *rom, size_t sz) {
    nes_t *nes = nes_init(SYS_NES_NTSC, 32000, false, NULL);
    if (!nes) { printf("[BENCH] NES: init failed\n"); heap_caps_free(rom); return; }

    rom_t *cart = rom_loadmem(rom, sz);
    if (!cart || nes_insertcart(cart) != 0) {
        printf("[BENCH] NES: ROM load failed\n");
        nes_shutdown(); heap_caps_free(rom); return;
    }

    nes_setvidbuf(g_vidbuf);
    nes->blit_func = blit_noop;

    for (int i = 0; i < WARMUP_FRAMES; i++) nes_emulate(true);

    int64_t start = esp_timer_get_time();
    for (int i = 0; i < BENCH_FRAMES; i++) nes_emulate(true);
    int64_t elapsed = esp_timer_get_time() - start;

    bench_print_result("NES", BENCH_FRAMES, elapsed);
    nes_shutdown();
}
