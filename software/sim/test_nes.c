/**
 * Quick NES test — loads owlia.nes directly and runs 120 frames
 * to verify nofrendo core works.
 */
#define SIM_BUILD
#include "sim_hal.h"
#include "rom_check.h"
#include "emu_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    const char *rom_path = (argc > 1) ? argv[1] : "../../test-roms/nes/owlia.nes";

    printf("NES Core Test: %s\n", rom_path);

    /* Load ROM file */
    FILE *f = fopen(rom_path, "rb");
    if (!f) { printf("ERROR: cannot open %s\n", rom_path); return 1; }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *rom = malloc(size);
    fread(rom, 1, size, f);
    fclose(f);
    printf("ROM loaded: %ldKB\n", size / 1024);

    /* Check ROM */
    rom_info_t info = rom_check(rom, size, rom_path);
    rom_print_info(&info);
    if (!info.valid) { printf("INVALID ROM\n"); return 1; }

    /* Init SDL */
    if (sim_init() != 0) { printf("SDL init failed\n"); return 1; }
    sim_display_init();

    /* Get NES core */
    const emu_core_t *core = emu_get_core(PLATFORM_NES);
    if (!core) { printf("No NES core\n"); return 1; }
    printf("Core: %s (%dx%d)\n", core->name, core->native_w, core->native_h);

    /* Init core */
    if (core->init(rom, size, &info) != 0) {
        printf("Core init FAILED\n");
        return 1;
    }
    printf("Core init OK — running frames...\n");

    /* Run 300 frames (~5 seconds) with display */
    for (int frame = 0; frame < 300 && !sim_quit_requested(); frame++) {
        sim_poll_events();
        core->set_input(sim_buttons_read());
        core->run_frame();

        const uint16_t *fb = core->get_framebuffer();
        if (fb) {
            sim_display_write(fb, 0, 0, 480, 320);
            sim_display_flush();
        }

        int16_t audio[1024];
        int samples = core->get_audio(audio, 1024);
        if (samples > 0) sim_audio_write(audio, samples);

        if (frame < 5 || frame % 60 == 0)
            printf("Frame %d OK (fb=%p)\n", frame, (void*)fb);

        SDL_Delay(16);
    }

    core->shutdown();
    sim_shutdown();
    free(rom);
    printf("Test complete!\n");
    return 0;
}
