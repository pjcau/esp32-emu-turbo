/* SNES benchmark — isolated to avoid symbol conflicts */
#include <stdio.h>
#include <string.h>
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "bench.h"

/* Use explicit paths to avoid collision with nofrendo ppu.h/apu.h */
#include "../../components/snes9x/src/snes9x.h"
#include "../../components/snes9x/src/memmap.h"
#include "../../components/snes9x/src/gfx.h"
#include "../../components/snes9x/src/ppu.h"
#include "../../components/snes9x/src/apu.h"
#include "../../components/snes9x/src/display.h"
#include "../../components/snes9x/src/cpuexec.h"
#include "../../components/snes9x/src/dma.h"
#include "../../components/snes9x/src/pixform.h"

/* Missing symbols — stubs for benchmark */
bool JustifierOffscreen(void) { return true; }
void JustifierButtons(uint32_t *b) { if (b) *b = 0; }
bool S9xFreezeGame(const char *f) { return false; }
bool S9xUnfreezeGame(const char *f) { return false; }

/* Port callbacks — minimal stubs for benchmark */
uint32_t S9xReadJoypad(int32_t port) { return 0; }
bool S9xReadMousePosition(int32_t w, int32_t *x, int32_t *y, uint32_t *b) { return false; }
bool S9xReadSuperScopePosition(int32_t *x, int32_t *y, uint32_t *b) { return false; }
bool S9xInitDisplay(void) { return true; }
void S9xDeinitDisplay(void) {}
void S9xToggleSoundChannel(int32_t c) {}
/* S9xNextController already in ppu.c */
void S9xMessage(int32_t type, int32_t num, const char *msg) { printf("[SNES] %s\n", msg); }
void S9xAutoSaveSRAM(void) {}
void S9xSyncSpeed(void) {}

void bench_snes(const char *path) {
    size_t sz;
    uint8_t *rom = bench_load_file(path, &sz);
    if (!rom) return;
    bench_snes_rom(rom, sz);
    heap_caps_free(rom);
}

void bench_snes_rom(uint8_t *rom, size_t sz) {
    /* Initialize Settings */
    memset(&Settings, 0, sizeof(Settings));
    Settings.APUEnabled = true;
    Settings.Shutdown = true;
    Settings.H_Max = SNES_CYCLES_PER_SCANLINE;
    Settings.HBlankStart = (256 * Settings.H_Max) / SNES_HCOUNTER_MAX;
    Settings.CyclesPercentage = 100;
    Settings.FrameTimeNTSC = 16667;
    Settings.FrameTimePAL = 20000;
    Settings.FrameTime = Settings.FrameTimeNTSC;
    Settings.SoundPlaybackRate = 32000;
    Settings.SoundInputRate = 32000;
    Settings.SoundBufferSize = 256;
    Settings.SoundMixInterval = 0;
    Settings.NextAPUEnabled = true;

    /* S9xInitMemory allocates ~6MB for ROM buffer — needs >8MB PSRAM.
     * QEMU runs with 32MB PSRAM to accommodate SNES. */
    if (!S9xInitMemory()) {
        printf("[BENCH] SNES: S9xInitMemory failed\n");
        return;
    }

    /* Initialize APU */
    if (!S9xInitAPU()) {
        printf("[BENCH] SNES: S9xInitAPU failed\n");
        return;
    }

    S9xInitSound(20, 0);

    /* Allocate GFX buffers — single block to save alloc overhead */
    size_t gfx_sz = SNES_WIDTH * 2 * (SNES_HEIGHT_EXTENDED + 1);
    uint8_t *gfx_block = (uint8_t *)heap_caps_calloc(gfx_sz * 4, 1, MALLOC_CAP_SPIRAM);
    if (!gfx_block) {
        printf("[BENCH] SNES: GFX alloc failed (%zu bytes)\n", gfx_sz * 4);
        return;
    }
    GFX.Pitch = SNES_WIDTH * 2;
    GFX.Screen = gfx_block;
    GFX.SubScreen = gfx_block + gfx_sz;
    GFX.ZBuffer = gfx_block + gfx_sz * 2;
    GFX.SubZBuffer = gfx_block + gfx_sz * 3;
    GFX.RealPitch = GFX.Pitch;
    GFX.Pitch2 = GFX.Pitch;
    GFX.ZPitch = GFX.Pitch;
    GFX.PPL = SNES_WIDTH;
    GFX.PPLx2 = SNES_WIDTH * 2;
    GFX.PixSize = 2;
    GFX.Delta = (GFX.SubScreen - GFX.Screen) >> 1;
    GFX.DepthDelta = GFX.SubZBuffer - GFX.ZBuffer;
    GFX.OBJLines = (SOBJLines *)heap_caps_calloc(SNES_HEIGHT_EXTENDED, sizeof(SOBJLines), MALLOC_CAP_SPIRAM);

    /* Copy ROM data into Memory.ROM and load.
     * LoadROM(NULL) uses ROM_AllocSize as file size, so set it to actual ROM size */
    size_t orig_alloc = Memory.ROM_AllocSize;
    if (sz > orig_alloc)
        sz = orig_alloc;
    memcpy(Memory.ROM, rom, sz);
    Memory.ROM_AllocSize = sz;

    if (!LoadROM(NULL)) {
        Memory.ROM_AllocSize = orig_alloc;
        printf("[BENCH] SNES: LoadROM failed\n");
        return;
    }

    /* Full system reset (CPU + PPU + DMA + APU) */
    extern void S9xReset(void);
    S9xReset();

    printf("[BENCH] SNES: ROM loaded (%zu KB), PC=0x%04X, starting benchmark\n",
           sz / 1024, ICPU.Registers.PC);

    /* Disable PPU rendering — on real hardware it runs on Core 1.
     * We benchmark CPU only (65816 + SPC700 emulation). */
    IPPU.RenderThisFrame = false;

    printf("[BENCH] SNES: running single frame (CPU only, no PPU render)...\n");
    int64_t t0 = esp_timer_get_time();
    S9xMainLoop();
    int64_t dt = esp_timer_get_time() - t0;
    printf("[BENCH] SNES: frame 0 took %lld us (%.1f fps)\n", (long long)dt, 1000000.0f / dt);

    /* If first frame was fast enough, run full benchmark */
    if (dt > 1000000) {
        printf("[BENCH] SNES  : 1 frame in %lld us, avg %lld us/frame, %.1f fps %s\n",
               (long long)dt, (long long)dt, 1000000.0f / dt,
               (1000000.0f / dt >= 60.0f) ? "(OK)" : "(SLOW)");
        return;
    }

    /* Full benchmark with reduced frames */
    int bench_n = (dt < 50000) ? 300 : 30;
    printf("[BENCH] SNES: running %d more frames...\n", bench_n);
    int64_t start = esp_timer_get_time();
    for (int i = 0; i < bench_n; i++)
        S9xMainLoop();
    int64_t elapsed = esp_timer_get_time() - start;

    bench_print_result("SNES", BENCH_FRAMES, elapsed);

    S9xDeinitGFX();
    S9xDeinitDisplay();
}
