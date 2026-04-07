#define SIM_BUILD
#include "sim_hal.h"
#include "rom_check.h"
#include "emu_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main() {
    sim_init();
    sim_display_init();
    const char *path = "../../test-roms/sms/silvervalley.sms";
    FILE *f = fopen(path, "rb"); fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    uint8_t *rom = malloc(sz); fread(rom,1,sz,f); fclose(f);
    rom_info_t info = rom_check(rom, sz, path);
    const emu_core_t *core = emu_get_core(PLATFORM_SMS);
    core->init(rom, sz, &info);
    for (int i = 0; i < 5; i++) {
        core->set_input(0);
        core->run_frame();
    }
    const uint16_t *fb = core->get_framebuffer();
    int nonzero = 0;
    for (int i = 0; i < 480*320; i++) if (fb[i]) nonzero++;
    printf("Nonzero pixels: %d / %d\n", nonzero, 480*320);
    /* Print a few pixel values from center */
    printf("Center pixels: ");
    for (int i = 0; i < 16; i++) printf("%04X ", fb[160*480 + 200 + i]);
    printf("\n");
    core->shutdown();
    sim_shutdown();
    free(rom);
    return 0;
}
