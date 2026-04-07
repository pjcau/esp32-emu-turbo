/**
 * ESP32 Emu Turbo — Simulator Main
 *
 * Full hardware simulation matching the ESP32 firmware:
 *   - Display: ILI9488 480×320 (SDL2 window)
 *   - Input: 12 SNES buttons + power switch (keyboard)
 *   - Audio: I2S 32kHz mono (SDL2 audio)
 *   - SD Card: ROM browser (host filesystem)
 *
 * Phases:
 *   1. Hardware init (display, input, audio, SD)
 *   2. ROM browser (list files, select with UP/DOWN + A)
 *   3. ROM loaded screen (info display)
 *   4. Interactive mode (button test + display)
 *
 * Build: cd software/sim && make
 * Run:   ./emu-turbo-sim ../../test-roms
 */

#define SIM_BUILD
#include "sim_hal.h"
#include "rom_check.h"
#include "emu_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* Global emulator state */
static rom_info_t g_current_info;
static const emu_core_t *g_active_core = NULL;

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ── Forward declarations (sim driver functions) ─────────── */

/* display */
int  display_sim_init(void);
void display_sim_fill(uint16_t color);
void display_sim_draw_rect(int x, int y, int w, int h, uint16_t color);
int  display_sim_draw_color_bars(void);
void display_sim_flush(void);

/* input */
int  input_sim_init(void);
uint16_t input_sim_read(void);
const char *input_sim_button_name(int bit);
void input_sim_toggle_power(void);
int  input_sim_power_switch(void);

/* audio */
int  audio_sim_init(void);
void audio_sim_play_test_tone(int duration_ms);
void audio_sim_write(const int16_t *samples, int count);
void audio_sim_stop(void);

/* sdcard */
int  sdcard_sim_init(const char *dir);
int  sdcard_sim_scan_roms(void);
int  sdcard_sim_get_rom_count(void);
const char *sdcard_sim_get_rom_name(int index);
const char *sdcard_sim_get_rom_path(int index);
long sdcard_sim_get_rom_size(int index);
const char *sdcard_sim_get_rom_type(int index);
uint8_t *sdcard_sim_load_rom(int index);

/* ── Colors (RGB565) ─────────────────────────────────────── */

#define C_BLACK   0x0000
#define C_WHITE   0xFFFF
#define C_RED     0xF800
#define C_GREEN   0x07E0
#define C_BLUE    0x001F
#define C_YELLOW  0xFFE0
#define C_CYAN    0x07FF
#define C_MAGENTA 0xF81F
#define C_GRAY    0x7BEF
#define C_DARK    0x2104

/* ── Simple 8×8 pixel font (ASCII 32-127) ──────────────── */
/* Minimal built-in font for text rendering */

#include "font8x8.h"

static void draw_char(int cx, int cy, char ch, uint16_t fg, uint16_t bg) {
    if (ch < 32 || ch > 127) ch = '?';
    const uint8_t *glyph = font8x8[(int)ch - 32];
    uint16_t row_buf[8];
    for (int y = 0; y < 8; y++) {
        uint8_t bits = glyph[y];
        for (int x = 0; x < 8; x++) {
            row_buf[x] = (bits & (1 << x)) ? fg : bg;
        }
        sim_display_write(row_buf, cx, cy + y, 8, 1);
    }
}

static void draw_text(int x, int y, const char *text, uint16_t fg, uint16_t bg) {
    while (*text) {
        draw_char(x, y, *text, fg, bg);
        x += 8;
        text++;
    }
}

/* ── Screens ─────────────────────────────────────────────── */

static void screen_boot(void) {
    display_sim_fill(C_BLACK);
    draw_text(120, 100, "ESP32 EMU TURBO", C_CYAN, C_BLACK);
    draw_text(140, 120, "Simulator v1.0", C_GRAY, C_BLACK);
    draw_text(100, 160, "Initializing hardware...", C_WHITE, C_BLACK);
    display_sim_flush();
}

static void screen_hw_test(int display_ok, int input_ok, int audio_ok, int sd_ok, int power_ok) {
    display_sim_fill(C_BLACK);
    draw_text(160, 20, "HARDWARE TEST", C_CYAN, C_BLACK);

    struct { const char *name; int ok; } tests[] = {
        {"Display (ILI9488 480x320)", display_ok},
        {"Input (12 buttons + PWR)",  input_ok},
        {"Audio (I2S 32kHz mono)",    audio_ok},
        {"SD Card (ROM browser)",     sd_ok},
        {"Power Switch",              power_ok},
    };
    for (int i = 0; i < 5; i++) {
        uint16_t color = tests[i].ok ? C_GREEN : C_RED;
        char line[64];
        snprintf(line, sizeof(line), "%s %s",
                 tests[i].ok ? "[OK]" : "[--]", tests[i].name);
        draw_text(40, 60 + i * 24, line, color, C_BLACK);
    }

    draw_text(80, 220, "Press START to continue...", C_YELLOW, C_BLACK);
    display_sim_flush();
}

static int screen_rom_browser(int selected) {
    int count = sdcard_sim_get_rom_count();
    display_sim_fill(C_BLACK);
    draw_text(140, 10, "SELECT ROM", C_CYAN, C_BLACK);

    if (count == 0) {
        draw_text(80, 120, "No ROMs found in test-roms/", C_RED, C_BLACK);
        draw_text(60, 150, "Place .sfc/.smc/.nes files there", C_GRAY, C_BLACK);
        display_sim_flush();
        return -1;
    }

    /* Show up to 10 ROMs on screen */
    int start = (selected > 5) ? selected - 5 : 0;
    int visible = (count - start > 10) ? 10 : (count - start);

    for (int i = 0; i < visible; i++) {
        int idx = start + i;
        uint16_t fg = (idx == selected) ? C_BLACK : C_WHITE;
        uint16_t bg = (idx == selected) ? C_CYAN : C_BLACK;

        char line[60];
        snprintf(line, sizeof(line), " %-40s %4s %4ldKB ",
                 sdcard_sim_get_rom_name(idx),
                 sdcard_sim_get_rom_type(idx),
                 sdcard_sim_get_rom_size(idx) / 1024);
        draw_text(20, 40 + i * 24, line, fg, bg);
    }

    draw_text(40, 290, "UP/DOWN: select  A: load  ESC: quit", C_GRAY, C_BLACK);
    display_sim_flush();
    return selected;
}

static void screen_rom_loaded(int index) {
    display_sim_fill(C_BLACK);
    draw_text(140, 40, "ROM LOADED", C_GREEN, C_BLACK);

    char line[64];
    snprintf(line, sizeof(line), "Name: %s", sdcard_sim_get_rom_name(index));
    draw_text(40, 100, line, C_WHITE, C_BLACK);

    snprintf(line, sizeof(line), "Type: %s", sdcard_sim_get_rom_type(index));
    draw_text(40, 124, line, C_WHITE, C_BLACK);

    snprintf(line, sizeof(line), "Size: %ldKB", sdcard_sim_get_rom_size(index) / 1024);
    draw_text(40, 148, line, C_WHITE, C_BLACK);

    draw_text(60, 220, "Press START for interactive mode", C_YELLOW, C_BLACK);
    draw_text(60, 244, "Press B to go back", C_GRAY, C_BLACK);
    display_sim_flush();
}

/* ── Button overlay for interactive mode ─────────────────── */

static void draw_button_overlay(uint16_t buttons) {
    /* SNES controller layout at bottom of screen */
    int by = 240;

    /* D-pad */
    display_sim_draw_rect(40, by,     20, 16, (buttons & SIM_BTN_UP)    ? C_YELLOW : C_DARK);
    display_sim_draw_rect(40, by+36,  20, 16, (buttons & SIM_BTN_DOWN)  ? C_YELLOW : C_DARK);
    display_sim_draw_rect(18, by+18,  20, 16, (buttons & SIM_BTN_LEFT)  ? C_YELLOW : C_DARK);
    display_sim_draw_rect(62, by+18,  20, 16, (buttons & SIM_BTN_RIGHT) ? C_YELLOW : C_DARK);

    /* Face buttons */
    display_sim_draw_rect(400, by+18, 20, 16, (buttons & SIM_BTN_A)     ? C_GREEN  : C_DARK);
    display_sim_draw_rect(422, by+36, 20, 16, (buttons & SIM_BTN_B)     ? C_RED    : C_DARK);
    display_sim_draw_rect(400, by,    20, 16, (buttons & SIM_BTN_X)     ? C_BLUE   : C_DARK);
    display_sim_draw_rect(378, by+18, 20, 16, (buttons & SIM_BTN_Y)     ? C_YELLOW : C_DARK);

    /* Start/Select */
    display_sim_draw_rect(200, by+30, 30, 12, (buttons & SIM_BTN_START)  ? C_WHITE  : C_DARK);
    display_sim_draw_rect(250, by+30, 30, 12, (buttons & SIM_BTN_SELECT) ? C_WHITE  : C_DARK);

    /* Shoulder */
    display_sim_draw_rect(18,  by-20, 40, 12, (buttons & SIM_BTN_L)     ? C_MAGENTA: C_DARK);
    display_sim_draw_rect(400, by-20, 40, 12, (buttons & SIM_BTN_R)     ? C_MAGENTA: C_DARK);

    /* Labels */
    draw_text(42, by+2,  "U", C_WHITE, C_BLACK);
    draw_text(42, by+38, "D", C_WHITE, C_BLACK);
    draw_text(22, by+20, "L", C_WHITE, C_BLACK);
    draw_text(66, by+20, "R", C_WHITE, C_BLACK);
    draw_text(404, by+20, "A", C_BLACK, (buttons & SIM_BTN_A) ? C_GREEN : C_DARK);
    draw_text(426, by+38, "B", C_BLACK, (buttons & SIM_BTN_B) ? C_RED : C_DARK);
    draw_text(404, by+2,  "X", C_WHITE, (buttons & SIM_BTN_X) ? C_BLUE : C_DARK);
    draw_text(382, by+20, "Y", C_BLACK, (buttons & SIM_BTN_Y) ? C_YELLOW : C_DARK);
    draw_text(204, by+32, "STA", C_WHITE, C_BLACK);
    draw_text(254, by+32, "SEL", C_WHITE, C_BLACK);
    draw_text(26, by-18, "L", C_WHITE, C_BLACK);
    draw_text(412, by-18, "R", C_WHITE, C_BLACK);
}

/* ── Main ────────────────────────────────────────────────── */

enum state { ST_BOOT, ST_HW_TEST, ST_ROM_BROWSER, ST_ROM_CHECK, ST_RUNNING };

int main(int argc, char **argv) {
    const char *rom_dir = (argc > 1) ? argv[1] : "../../test-roms";

    printf("╔══════════════════════════════════════╗\n");
    printf("║  ESP32 Emu Turbo — Simulator         ║\n");
    printf("║  Display + Input + Audio + SD Card   ║\n");
    printf("╚══════════════════════════════════════╝\n\n");

    /* Init SDL */
    if (sim_init() != 0) {
        fprintf(stderr, "Failed to init SDL2\n");
        return 1;
    }

    /* Phase 1: Hardware init */
    screen_boot();
    SDL_Delay(500);

    int display_ok = (display_sim_init() == 0);
    int input_ok   = (input_sim_init() == 0);
    int audio_ok   = (audio_sim_init() == 0);
    int sd_ok      = (sdcard_sim_init(rom_dir) == 0);
    int power_ok   = 1;  /* power switch always simulated */

    /* Scan ROMs */
    sdcard_sim_scan_roms();

    enum state state = ST_HW_TEST;
    int selected_rom = 0;
    uint16_t prev_buttons = 0;
    int rom_loaded_index = -1;
    uint8_t *rom_data = NULL;

    screen_hw_test(display_ok, input_ok, audio_ok, sd_ok, power_ok);

    /* Play test tone */
    if (audio_ok) audio_sim_play_test_tone(500);

    while (!sim_quit_requested()) {
        sim_poll_events();
        uint16_t buttons = input_sim_read();
        uint16_t pressed = buttons & ~prev_buttons;  /* rising edge */

        switch (state) {
        case ST_BOOT:
            break;

        case ST_HW_TEST:
            if (pressed & SIM_BTN_START) {
                state = ST_ROM_BROWSER;
                screen_rom_browser(selected_rom);
            }
            break;

        case ST_ROM_BROWSER: {
            int count = sdcard_sim_get_rom_count();
            if (pressed & SIM_BTN_UP) {
                if (selected_rom > 0) selected_rom--;
                screen_rom_browser(selected_rom);
            }
            if (pressed & SIM_BTN_DOWN) {
                if (selected_rom < count - 1) selected_rom++;
                screen_rom_browser(selected_rom);
            }
            if ((pressed & SIM_BTN_A) && count > 0) {
                /* Load ROM */
                if (rom_data) { free(rom_data); rom_data = NULL; }
                rom_data = sdcard_sim_load_rom(selected_rom);
                if (rom_data) {
                    rom_loaded_index = selected_rom;

                    /* ROM check */
                    rom_info_t rinfo = rom_check(rom_data,
                        sdcard_sim_get_rom_size(selected_rom),
                        sdcard_sim_get_rom_name(selected_rom));
                    rom_print_info(&rinfo);

                    /* Show ROM check screen */
                    display_sim_fill(C_BLACK);
                    draw_text(140, 10, "ROM CHECK", C_CYAN, C_BLACK);
                    char line[64];
                    snprintf(line, sizeof(line), "File: %s", rinfo.title[0] ? rinfo.title : sdcard_sim_get_rom_name(selected_rom));
                    draw_text(20, 50, line, C_WHITE, C_BLACK);
                    snprintf(line, sizeof(line), "Platform: %s", rom_platform_name(rinfo.platform));
                    draw_text(20, 74, line, C_WHITE, C_BLACK);
                    snprintf(line, sizeof(line), "Size: %uKB", rinfo.rom_size / 1024);
                    draw_text(20, 98, line, C_WHITE, C_BLACK);
                    snprintf(line, sizeof(line), "Valid: %s", rinfo.valid ? "YES" : "NO");
                    draw_text(20, 122, line, rinfo.valid ? C_GREEN : C_RED, C_BLACK);
                    if (rinfo.error[0]) {
                        draw_text(20, 146, rinfo.error, C_YELLOW, C_BLACK);
                    }
                    if (rinfo.platform == PLATFORM_NES) {
                        snprintf(line, sizeof(line), "Mapper: %d  PRG: %dKB  CHR: %dKB",
                                 rinfo.nes.mapper, rinfo.nes.prg_size/1024, rinfo.nes.chr_size/1024);
                        draw_text(20, 170, line, C_GRAY, C_BLACK);
                    }
                    if (rinfo.platform == PLATFORM_GB || rinfo.platform == PLATFORM_GBC) {
                        snprintf(line, sizeof(line), "MBC: %d  Banks: %d", rinfo.gb.mbc_type, rinfo.gb.rom_banks);
                        draw_text(20, 170, line, C_GRAY, C_BLACK);
                    }

                    /* Get emulator core */
                    const emu_core_t *core = emu_get_core(rinfo.platform);
                    if (core && rinfo.valid) {
                        snprintf(line, sizeof(line), "Core: %s (%dx%d @ %dfps)",
                                 core->name, core->native_w, core->native_h, core->fps);
                        draw_text(20, 210, line, C_CYAN, C_BLACK);
                        draw_text(60, 250, "Press START to launch emulator", C_YELLOW, C_BLACK);
                        draw_text(60, 274, "Press B to go back", C_GRAY, C_BLACK);
                    } else {
                        draw_text(60, 250, "No core available / invalid ROM", C_RED, C_BLACK);
                        draw_text(60, 274, "Press B to go back", C_GRAY, C_BLACK);
                    }
                    display_sim_flush();
                    g_current_info = rinfo;
                    state = ST_ROM_CHECK;
                }
            }
            break;
        }

        case ST_ROM_CHECK: {
            if (pressed & SIM_BTN_B) {
                state = ST_ROM_BROWSER;
                screen_rom_browser(selected_rom);
            }
            if (pressed & SIM_BTN_START) {
                const emu_core_t *core = emu_get_core(g_current_info.platform);
                if (core && g_current_info.valid) {
                    /* Launch emulator! */
                    core->init(rom_data, sdcard_sim_get_rom_size(rom_loaded_index), &g_current_info);
                    g_active_core = core;
                    state = ST_RUNNING;
                    printf("[LAUNCHER] Running %s: %s\n",
                           core->name, g_current_info.title);
                }
            }
            break;
        }

        case ST_RUNNING: {
            if (!g_active_core) { state = ST_ROM_BROWSER; break; }

            /* Feed input to emulator */
            g_active_core->set_input(buttons);

            /* Run one frame */
            g_active_core->run_frame();

            /* Display framebuffer */
            const uint16_t *fb = g_active_core->get_framebuffer();
            if (fb) {
                sim_display_write(fb, 0, 0, EMU_SCREEN_W, EMU_SCREEN_H);
                sim_display_flush();
            }

            /* Audio */
            int16_t audio_buf[EMU_AUDIO_BUF];
            int samples = g_active_core->get_audio(audio_buf, EMU_AUDIO_BUF);
            if (samples > 0) audio_sim_write(audio_buf, samples);

            /* SELECT+START = back to browser */
            if ((buttons & SIM_BTN_SELECT) && (buttons & SIM_BTN_START)) {
                g_active_core->shutdown();
                g_active_core = NULL;
                state = ST_ROM_BROWSER;
                screen_rom_browser(selected_rom);
            }
            break;
        }
        }

        prev_buttons = buttons;
        SDL_Delay(16);  /* ~60fps */
    }

    if (rom_data) free(rom_data);
    sim_shutdown();
    printf("\nSimulator closed.\n");
    return 0;
}
