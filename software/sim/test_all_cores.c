/**
 * ESP32 Emu Turbo — Automated Core Test Suite
 *
 * Tests all 6 real emulator cores: init, run 60 frames, verify
 * framebuffer output and audio generation. Reports PASS/FAIL per core.
 *
 * Build: cd software/sim && make test_all
 * Run:   ./test_all_cores ../../test-roms
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

static jmp_buf g_jump;
static volatile int g_crashed = 0;

static void crash_handler(int sig) {
    g_crashed = 1;
    longjmp(g_jump, 1);
}

typedef struct {
    const char *rom_path;
    const char *name;
    platform_t platform;
} test_case_t;

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

static int test_core(const char *rom_dir, const test_case_t *tc) {
    char path[512];
    snprintf(path, sizeof(path), "%s/%s", rom_dir, tc->rom_path);

    printf("\n── %s ──\n", tc->name);

    /* Load ROM */
    uint8_t *rom = NULL;
    long size = 0;
    if (load_file(path, &rom, &size) != 0) {
        printf("  SKIP: ROM not found: %s\n", path);
        return -1;
    }

    /* ROM check */
    rom_info_t info = rom_check(rom, size, tc->rom_path);
    printf("  ROM:      %s (%ldKB)\n", info.title[0] ? info.title : tc->name, size / 1024);
    printf("  Platform: %s\n", rom_platform_name(info.platform));
    printf("  Valid:    %s\n", info.valid ? "YES" : "NO");
    if (!info.valid) {
        printf("  FAIL: invalid ROM header\n");
        free(rom);
        return 1;
    }

    /* Get core */
    const emu_core_t *core = emu_get_core(tc->platform);
    if (!core) {
        printf("  FAIL: no core for %s\n", rom_platform_name(tc->platform));
        free(rom);
        return 1;
    }
    printf("  Core:     %s (%dx%d @ %dfps)\n", core->name, core->native_w, core->native_h, core->fps);

    /* Init — catch crashes from cores with missing setup */
    g_crashed = 0;
    signal(SIGABRT, crash_handler);
    signal(SIGSEGV, crash_handler);

    if (setjmp(g_jump) != 0) {
        printf("  FAIL: core crashed (signal caught)\n");
        signal(SIGABRT, SIG_DFL);
        signal(SIGSEGV, SIG_DFL);
        free(rom);
        return 1;
    }

    int init_ok = core->init(rom, size, &info);
    if (init_ok != 0) {
        printf("  FAIL: core init returned error\n");
        signal(SIGABRT, SIG_DFL);
        signal(SIGSEGV, SIG_DFL);
        free(rom);
        return 1;
    }

    /* Run 60 frames */
    int video_ok = 0, audio_ok = 0;
    int16_t audio_buf[2048];

    for (int frame = 0; frame < 60; frame++) {
        core->set_input(0);  /* no buttons */
        if (core->run_frame() != 0) {
            printf("  FAIL: run_frame crashed at frame %d\n", frame);
            core->shutdown();
            free(rom);
            return 1;
        }

        /* Check framebuffer has non-zero pixels */
        const uint16_t *fb = core->get_framebuffer();
        if (fb && !video_ok) {
            for (int i = 0; i < EMU_SCREEN_W * EMU_SCREEN_H; i++) {
                if (fb[i] != 0) { video_ok = 1; break; }
            }
        }

        /* Check audio has non-zero samples */
        int samples = core->get_audio(audio_buf, 2048);
        if (samples > 0 && !audio_ok) {
            for (int i = 0; i < samples; i++) {
                if (audio_buf[i] != 0) { audio_ok = 1; break; }
            }
        }
    }

    /* Display result */
    printf("  Frames:   60/60 OK\n");
    printf("  Video:    %s (non-zero pixels in framebuffer)\n", video_ok ? "PASS" : "FAIL");
    printf("  Audio:    %s (non-zero samples generated)\n", audio_ok ? "PASS" : "WARN (silent)");

    int pass = video_ok;  /* audio can be silent on some ROMs */

    core->shutdown();
    signal(SIGABRT, SIG_DFL);
    signal(SIGSEGV, SIG_DFL);
    free(rom);

    printf("  Result:   %s\n", pass ? "PASS" : "FAIL");
    return pass ? 0 : 1;
}

int main(int argc, char **argv) {
    const char *rom_dir = (argc > 1) ? argv[1] : "../../test-roms";

    printf("╔══════════════════════════════════════╗\n");
    printf("║  Emulator Core Test Suite            ║\n");
    printf("║  6 cores × 60 frames each            ║\n");
    printf("╚══════════════════════════════════════╝\n");

    /* Init SDL (needed for audio init in some cores) */
    sim_init();

    test_case_t tests[] = {
        { "nes/owlia.nes",            "NES — Owlia",              PLATFORM_NES },
        { "gb/blarggs-cpu-instrs.gb", "GB — Blargg's CPU Tests",  PLATFORM_GB },
        { "gbc/ucity.gbc",            "GBC — µCity",              PLATFORM_GBC },
        { "sms/silvervalley.sms",     "SMS — Silver Valley",      PLATFORM_SMS },
        { "gg/Swabby-GG-1.11.gg",    "GG — Swabby",              PLATFORM_GG },
        { "pce/reflectron.pce",       "PCE — Reflectron",         PLATFORM_PCE },
    };
    int num_tests = sizeof(tests) / sizeof(tests[0]);

    int passed = 0, failed = 0, skipped = 0;

    for (int i = 0; i < num_tests; i++) {
        int result = test_core(rom_dir, &tests[i]);
        if (result == 0) passed++;
        else if (result < 0) skipped++;
        else failed++;
    }

    sim_shutdown();

    printf("\n══════════════════════════════════════\n");
    printf("  Results: %d passed, %d failed, %d skipped\n", passed, failed, skipped);
    printf("══════════════════════════════════════\n");

    return failed;
}
