#define SIM_BUILD
#include "sim_hal.h"
#include "rom_check.h"
#include "emu_core.h"
#include "../components/smsplus/shared.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main() {
    sim_init();
    const char *path = "../../test-roms/sms/silvervalley.sms";
    FILE *f = fopen(path, "rb"); fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    uint8_t *rom = malloc(sz); fread(rom,1,sz,f); fclose(f);
    rom_info_t info = rom_check(rom, sz, path);
    const emu_core_t *core = emu_get_core(PLATFORM_SMS);
    core->init(rom, sz, &info);
    for (int i = 0; i < 120; i++) { core->set_input(0); core->run_frame(); }
    /* Dump raw bitmap row 96 (middle of screen) */
    int row_y = 96;
    uint8_t *row = (uint8_t *)bitmap.data + row_y * bitmap.pitch;
    printf("Row %d (pitch=%d), first 64 bytes:\n", row_y, bitmap.pitch);
    for (int i = 0; i < 64; i++) {
        printf("%02X", row[i]);
        if (i % 16 == 15) printf("\n"); else printf(" ");
    }
    /* Count zero runs */
    printf("\nZero runs in first 284 bytes: ");
    int in_zero = 0, runs = 0;
    for (int i = 0; i < 284; i++) {
        if (row[i] == 0) { if (!in_zero) { runs++; printf("[%d", i); } in_zero = 1; }
        else { if (in_zero) printf("-%d] ", i-1); in_zero = 0; }
    }
    if (in_zero) printf("-%d]", 283);
    printf("\nTotal zero runs: %d\n", runs);
    core->shutdown(); free(rom); return 0;
}
