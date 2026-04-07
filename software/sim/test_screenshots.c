/**
 * ESP32 Emu Turbo — Screenshot Generator
 *
 * Loads a ROM, runs 300 frames (past boot screens), then saves
 * the framebuffer as a PPM image file.
 *
 * Build: cd software/sim && make test_screenshots
 * Run:   ./test_screenshots <rom_path> <output.ppm>
 *
 * The framebuffer is RGB565 (480x320). We convert to RGB888 for PPM.
 */

#define SIM_BUILD
#include "sim_hal.h"
#include "rom_check.h"
#include "emu_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <setjmp.h>

#define NUM_FRAMES 300

static jmp_buf g_jump;
static volatile int g_crashed = 0;

static void crash_handler(int sig) {
    g_crashed = 1;
    longjmp(g_jump, 1);
}

static int load_file(const char *path, uint8_t **out, long *out_size) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fseek(f, 0, SEEK_END);
    *out_size = ftell(f);
    fseek(f, 0, SEEK_SET);
    *out = malloc(*out_size);
    fread(*out, 1, *out_size, f);
    fclose(f);
    return 0;
}

/** Convert RGB565 to RGB888 and write PPM (P6 binary format) */
static int save_ppm(const char *path, const uint16_t *fb, int w, int h) {
    FILE *f = fopen(path, "wb");
    if (!f) {
        fprintf(stderr, "ERROR: cannot open %s for writing\n", path);
        return -1;
    }
    fprintf(f, "P6\n%d %d\n255\n", w, h);
    for (int i = 0; i < w * h; i++) {
        uint16_t px = fb[i];
        /* RGB565: RRRRR GGGGGG BBBBB */
        uint8_t r = ((px >> 11) & 0x1F) << 3;
        uint8_t g = ((px >> 5)  & 0x3F) << 2;
        uint8_t b = ((px >> 0)  & 0x1F) << 3;
        /* Fill lower bits for full range */
        r |= r >> 5;
        g |= g >> 6;
        b |= b >> 5;
        uint8_t rgb[3] = { r, g, b };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <rom_path> <output.ppm>\n", argv[0]);
        return 1;
    }

    const char *rom_path = argv[1];
    const char *out_path = argv[2];

    /* Load ROM */
    uint8_t *rom = NULL;
    long size = 0;
    if (load_file(rom_path, &rom, &size) != 0) {
        fprintf(stderr, "ERROR: cannot open ROM: %s\n", rom_path);
        return 1;
    }

    /* Detect platform */
    rom_info_t info = rom_check(rom, size, rom_path);
    if (!info.valid) {
        fprintf(stderr, "ERROR: invalid ROM: %s\n", info.error);
        free(rom);
        return 1;
    }

    printf("ROM:      %s (%ldKB)\n", info.title[0] ? info.title : rom_path, size / 1024);
    printf("Platform: %s\n", rom_platform_name(info.platform));

    /* Init SDL (needed by cores) */
    sim_init();

    /* Get core */
    const emu_core_t *core = emu_get_core(info.platform);
    if (!core) {
        fprintf(stderr, "ERROR: no core for platform %s\n", rom_platform_name(info.platform));
        sim_shutdown();
        free(rom);
        return 1;
    }
    printf("Core:     %s (%dx%d @ %dfps)\n", core->name, core->native_w, core->native_h, core->fps);

    /* Crash protection */
    g_crashed = 0;
    signal(SIGABRT, crash_handler);
    signal(SIGSEGV, crash_handler);

    if (setjmp(g_jump) != 0) {
        fprintf(stderr, "ERROR: core crashed\n");
        signal(SIGABRT, SIG_DFL);
        signal(SIGSEGV, SIG_DFL);
        sim_shutdown();
        free(rom);
        return 1;
    }

    /* Init core */
    if (core->init(rom, size, &info) != 0) {
        fprintf(stderr, "ERROR: core init failed\n");
        signal(SIGABRT, SIG_DFL);
        signal(SIGSEGV, SIG_DFL);
        sim_shutdown();
        free(rom);
        return 1;
    }

    /* Run frames */
    printf("Running %d frames...\n", NUM_FRAMES);
    int16_t audio_buf[2048];
    for (int frame = 0; frame < NUM_FRAMES; frame++) {
        core->set_input(0);
        if (core->run_frame() != 0) {
            fprintf(stderr, "ERROR: run_frame failed at frame %d\n", frame);
            core->shutdown();
            signal(SIGABRT, SIG_DFL);
            signal(SIGSEGV, SIG_DFL);
            sim_shutdown();
            free(rom);
            return 1;
        }
        /* Drain audio to prevent buffer overflow */
        core->get_audio(audio_buf, 2048);
    }

    /* Get framebuffer and save */
    const uint16_t *fb = core->get_framebuffer();
    if (!fb) {
        fprintf(stderr, "ERROR: no framebuffer\n");
        core->shutdown();
        signal(SIGABRT, SIG_DFL);
        signal(SIGSEGV, SIG_DFL);
        sim_shutdown();
        free(rom);
        return 1;
    }

    if (save_ppm(out_path, fb, EMU_SCREEN_W, EMU_SCREEN_H) == 0) {
        printf("Saved:    %s (%dx%d)\n", out_path, EMU_SCREEN_W, EMU_SCREEN_H);
    } else {
        core->shutdown();
        signal(SIGABRT, SIG_DFL);
        signal(SIGSEGV, SIG_DFL);
        sim_shutdown();
        free(rom);
        return 1;
    }

    core->shutdown();
    signal(SIGABRT, SIG_DFL);
    signal(SIGSEGV, SIG_DFL);
    sim_shutdown();
    free(rom);

    printf("Done.\n");
    return 0;
}
