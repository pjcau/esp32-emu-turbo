/**
 * Genesis/Mega Drive Emulator Core — gwenesis adapter
 * Bridges gwenesis to the emu_core_t interface.
 */

#ifdef SIM_BUILD

#include "emu_core.h"
#include "rom_check.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "gwenesis_bus.h"
#include "gwenesis_io.h"
#include "gwenesis_vdp.h"
#include "gwenesis_sn76489.h"
#include "gwenesis_savestate.h"
#include "ym2612.h"
#include "z80inst.h"
#include "m68k.h"

/* Globals required by gwenesis */
int system_clock;
int scan_line;
int frame_counter;

extern int zclk;

int16_t gwenesis_sn76489_buffer[GWENESIS_AUDIO_BUFFER_LENGTH_NTSC];
int sn76489_index;
int sn76489_clock;
int16_t gwenesis_ym2612_buffer[GWENESIS_AUDIO_BUFFER_LENGTH_NTSC];
int ym2612_index;
int ym2612_clock;

extern unsigned char gwenesis_vdp_regs[0x20];
extern unsigned short gwenesis_vdp_status;
extern int screen_width, screen_height;
extern int hint_pending;

static uint16_t g_fb[EMU_SCREEN_W * EMU_SCREEN_H];
static uint8_t g_screen_rgba[320 * 240 * 4]; /* gwenesis renders BGRA32 here */
static uint16_t g_buttons = 0;
static int g_initialized = 0;

/* Save state stubs */
SaveState *saveGwenesisStateOpenForRead(const char *fn) { return (void *)1; }
SaveState *saveGwenesisStateOpenForWrite(const char *fn) { return (void *)1; }
int saveGwenesisStateGet(SaveState *s, const char *tag) { return 0; }
void saveGwenesisStateSet(SaveState *s, const char *tag, int val) {}
void saveGwenesisStateGetBuffer(SaveState *s, const char *tag, void *buf, int len) {}
void saveGwenesisStateSetBuffer(SaveState *s, const char *tag, void *buf, int len) {}

/* Input callback — gwenesis calls this before reading pad state */
void gwenesis_io_get_buttons(void) {
    for (int i = 0; i < 8; i++)
        gwenesis_io_pad_release_button(0, i);

    if (g_buttons & 0x0001) gwenesis_io_pad_press_button(0, PAD_UP);
    if (g_buttons & 0x0002) gwenesis_io_pad_press_button(0, PAD_DOWN);
    if (g_buttons & 0x0004) gwenesis_io_pad_press_button(0, PAD_LEFT);
    if (g_buttons & 0x0008) gwenesis_io_pad_press_button(0, PAD_RIGHT);
    if (g_buttons & 0x0010) gwenesis_io_pad_press_button(0, PAD_C);   /* A -> C (main) */
    if (g_buttons & 0x0020) gwenesis_io_pad_press_button(0, PAD_B);
    if (g_buttons & 0x0040) gwenesis_io_pad_press_button(0, PAD_A);   /* X -> A */
    if (g_buttons & 0x0080) gwenesis_io_pad_press_button(0, PAD_B);   /* Y -> B */
    if (g_buttons & 0x0100) gwenesis_io_pad_press_button(0, PAD_S);   /* Start */
}

static int gen_init(const uint8_t *rom, size_t size, const rom_info_t *info) {
    printf("[GEN] Initializing gwenesis core...\n");

    memset(g_screen_rgba, 0, sizeof(g_screen_rgba));

    /* Set RGB888 screen buffer for gwenesis VDP */
    gwenesis_vdp_set_buffers(g_screen_rgba, NULL);

    /* Load cartridge — gwenesis copies into its own ROM_DATA[] */
    load_cartridge((unsigned char *)rom, size);
    power_on();
    reset_emulation();

    frame_counter = 0;
    g_initialized = 1;
    printf("[GEN] gwenesis ready: %s (%zuKB)\n", info->title, size / 1024);
    return 0;
}

static int gen_run_frame(void) {
    if (!g_initialized) return -1;

    int lines_per_frame = REG1_PAL ? LINES_PER_FRAME_PAL : LINES_PER_FRAME_NTSC;
    int hint_counter = gwenesis_vdp_regs[10];

    screen_width = REG12_MODE_H40 ? 320 : 256;
    screen_height = REG1_PAL ? 240 : 224;

    gwenesis_vdp_render_config();

    system_clock = 0;
    zclk = 0;
    ym2612_clock = 0;
    ym2612_index = 0;
    sn76489_clock = 0;
    sn76489_index = 0;
    scan_line = 0;

    while (scan_line < lines_per_frame) {
        m68k_run(system_clock + VDP_CYCLES_PER_LINE);
        z80_run(system_clock + VDP_CYCLES_PER_LINE);

        if (GWENESIS_AUDIO_ACCURATE == 0) {
            gwenesis_SN76489_run(system_clock + VDP_CYCLES_PER_LINE);
            ym2612_run(system_clock + VDP_CYCLES_PER_LINE);
        }

        if (scan_line < screen_height)
            gwenesis_vdp_render_line(scan_line);

        if ((scan_line == 0) || (scan_line > screen_height))
            hint_counter = REG10_LINE_COUNTER;

        if (--hint_counter < 0) {
            if ((REG0_LINE_INTERRUPT != 0) && (scan_line <= screen_height)) {
                hint_pending = 1;
                if ((gwenesis_vdp_status & STATUS_VIRQPENDING) == 0)
                    m68k_update_irq(4);
            }
            hint_counter = REG10_LINE_COUNTER;
        }

        scan_line++;

        if (scan_line == screen_height) {
            if (REG1_VBLANK_INTERRUPT != 0) {
                gwenesis_vdp_status |= STATUS_VIRQPENDING;
                m68k_set_irq(6);
            }
            z80_irq_line(1);
        }
        if (scan_line == screen_height + 1)
            z80_irq_line(0);

        system_clock += VDP_CYCLES_PER_LINE;
    }

    if (GWENESIS_AUDIO_ACCURATE == 1) {
        gwenesis_SN76489_run(system_clock);
        ym2612_run(system_clock);
    }

    m68k.cycles -= system_clock;
    frame_counter++;

    /* gwenesis renders BGRA32 (4 bytes/pixel) into g_screen_rgba.
     * Layout: [pixel*4+0]=B, [pixel*4+1]=G, [pixel*4+2]=R, [pixel*4+3]=unused
     * Pixels are centered: offset = ((240-screen_height)/2 + line) * 320 + x
     * Convert to RGB565 and scale to 480x320. */
    int src_w = screen_width;
    int src_h = screen_height;
    int y_off = (240 - src_h) / 2;  /* gwenesis centers vertically in 240-line buffer */

    int scale_w = (src_w * EMU_SCREEN_H) / src_h;
    if (scale_w > EMU_SCREEN_W) scale_w = EMU_SCREEN_W;
    int scale_h = (scale_w * src_h) / src_w;
    int off_x = (EMU_SCREEN_W - scale_w) / 2;
    int off_y = (EMU_SCREEN_H - scale_h) / 2;

    memset(g_fb, 0, sizeof(g_fb));
    for (int dy = 0; dy < scale_h; dy++) {
        int sy = (dy * src_h) / scale_h;
        int src_line = (y_off + sy) * 320;
        for (int dx = 0; dx < scale_w; dx++) {
            int sx = (dx * src_w) / scale_w;
            int pixel = (src_line + sx) * 4;
            uint8_t b = g_screen_rgba[pixel + 0];
            uint8_t g = g_screen_rgba[pixel + 1];
            uint8_t r = g_screen_rgba[pixel + 2];
            g_fb[(off_y + dy) * EMU_SCREEN_W + off_x + dx] =
                ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
        }
    }

    return 0;
}

static const uint16_t *gen_get_fb(void) { return g_fb; }

static int gen_get_audio(int16_t *buf, int max) {
    int samples = ym2612_index;
    if (samples > max) samples = max;
    for (int i = 0; i < samples; i++) {
        int mixed = gwenesis_ym2612_buffer[i];
        if (i < sn76489_index)
            mixed += gwenesis_sn76489_buffer[i];
        if (mixed > 32767) mixed = 32767;
        if (mixed < -32768) mixed = -32768;
        buf[i] = (int16_t)mixed;
    }
    return samples;
}

static void gen_set_input(uint16_t b) { g_buttons = b; }

static void gen_reset(void) {
    if (g_initialized) reset_emulation();
}

static void gen_shutdown(void) {
    if (g_initialized) {
        g_initialized = 0;
        printf("[GEN] Core shutdown\n");
    }
}

const emu_core_t gen_real_core = {
    .name = "Genesis (gwenesis)",
    .native_w = 320,
    .native_h = 224,
    .fps = 60,
    .init = gen_init,
    .run_frame = gen_run_frame,
    .get_framebuffer = gen_get_fb,
    .get_audio = gen_get_audio,
    .set_input = gen_set_input,
    .reset = gen_reset,
    .shutdown = gen_shutdown,
};

#endif
