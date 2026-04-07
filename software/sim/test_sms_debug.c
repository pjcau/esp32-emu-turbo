#define SIM_BUILD
#include "sim_hal.h"
#include "rom_check.h"
#include "emu_core.h"
#include "../components/smsplus/shared.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern uint8_t *g_screen_buf;
int main() {
    sim_init();
    const char *path = "../../test-roms/sms/silvervalley.sms";
    FILE *f = fopen(path, "rb"); fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET);
    uint8_t *rom = malloc(sz); fread(rom,1,sz,f); fclose(f);
    rom_info_t info = rom_check(rom, sz, path);
    const emu_core_t *core = emu_get_core(PLATFORM_SMS);
    core->init(rom, sz, &info);
    for (int i = 0; i < 60; i++) { core->set_input(0); core->run_frame(); }
    /* Check raw bitmap data */
    int vp_x = bitmap.viewport.x, vp_y = bitmap.viewport.y;
    int vp_w = bitmap.viewport.w, vp_h = bitmap.viewport.h;
    printf("viewport: x=%d y=%d w=%d h=%d pitch=%d\n", vp_x, vp_y, vp_w, vp_h, bitmap.pitch);
    /* Count nonzero bytes in bitmap */
    int nz_bmp = 0;
    for (int i = 0; i < 512*240; i++) if (((uint8_t*)bitmap.data)[i]) nz_bmp++;
    printf("bitmap.data nonzero bytes: %d / %d\n", nz_bmp, 512*240);
    /* Sample from center of viewport */
    printf("bitmap row %d: ", vp_y + vp_h/2);
    uint8_t *row = (uint8_t*)bitmap.data + (vp_y + vp_h/2) * bitmap.pitch + vp_x;
    for (int i = 0; i < 16; i++) printf("%02X ", row[i]);
    printf("\n");
    /* Check palette */
    uint16_t pal[256]; memset(pal,0,sizeof(pal));
    render_copy_palette(pal);
    printf("palette[0..7]: ");
    for (int i = 0; i < 8; i++) printf("%04X ", pal[i]);
    printf("\n");
    core->shutdown(); free(rom); return 0;
}
