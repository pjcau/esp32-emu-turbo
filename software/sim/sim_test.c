/**
 * ESP32 Emu Turbo — Simulator Test Program
 *
 * Standalone test that exercises all 4 HAL subsystems:
 *   1. Display: draws color bars and button state overlay
 *   2. Buttons: reads keyboard and shows active buttons
 *   3. Audio: generates a test tone (440Hz sine wave)
 *   4. SD Card: lists ROM files from host directory
 *
 * Build: gcc -DSIM_BUILD -o sim_test sim_test.c sim_hal.c \
 *           $(sdl2-config --cflags --libs) -lm
 * Run:   ./sim_test [rom_directory]
 */

#define SIM_BUILD
#include "sim_hal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dirent.h>
#include <unistd.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* RGB565 color helpers */
#define RGB565(r, g, b) ((((r) >> 3) << 11) | (((g) >> 2) << 5) | ((b) >> 3))

static const uint16_t COLORS[] = {
    RGB565(255, 0, 0),     /* Red */
    RGB565(0, 255, 0),     /* Green */
    RGB565(0, 0, 255),     /* Blue */
    RGB565(255, 255, 0),   /* Yellow */
    RGB565(255, 0, 255),   /* Magenta */
    RGB565(0, 255, 255),   /* Cyan */
    RGB565(255, 255, 255), /* White */
    RGB565(128, 128, 128), /* Gray */
};

/* Draw color bars on the display */
static void draw_color_bars(void) {
    uint16_t row[SIM_LCD_WIDTH];
    int bar_h = SIM_LCD_HEIGHT / 8;

    for (int bar = 0; bar < 8; bar++) {
        for (int x = 0; x < SIM_LCD_WIDTH; x++) {
            row[x] = COLORS[bar];
        }
        for (int y = bar * bar_h; y < (bar + 1) * bar_h; y++) {
            sim_display_write(row, 0, y, SIM_LCD_WIDTH, 1);
        }
    }
}

/* Draw button state overlay */
static void draw_button_state(uint16_t buttons) {
    static const struct { const char *name; uint16_t mask; int x; int y; } BTN_POS[] = {
        { "UP",     SIM_BTN_UP,     60,  20 },
        { "DOWN",   SIM_BTN_DOWN,   60,  60 },
        { "LEFT",   SIM_BTN_LEFT,   20,  40 },
        { "RIGHT",  SIM_BTN_RIGHT, 100,  40 },
        { "A",      SIM_BTN_A,     380,  40 },
        { "B",      SIM_BTN_B,     420,  60 },
        { "X",      SIM_BTN_X,     380,  20 },
        { "Y",      SIM_BTN_Y,     340,  40 },
        { "START",  SIM_BTN_START, 200,  60 },
        { "SEL",    SIM_BTN_SELECT,260,  60 },
        { "L",      SIM_BTN_L,      20,   5 },
        { "R",      SIM_BTN_R,     420,   5 },
    };
    int count = sizeof(BTN_POS) / sizeof(BTN_POS[0]);

    for (int i = 0; i < count; i++) {
        uint16_t color = (buttons & BTN_POS[i].mask)
                         ? RGB565(255, 255, 0)  /* Active: yellow */
                         : RGB565(60, 60, 60);  /* Inactive: dark */

        /* Draw 20x15 rectangle for each button */
        uint16_t block[20];
        for (int x = 0; x < 20; x++) block[x] = color;
        for (int y = 0; y < 15; y++) {
            sim_display_write(block, BTN_POS[i].x, BTN_POS[i].y + y, 20, 1);
        }
    }
}

/* Generate 440Hz test tone */
static void generate_test_tone(int16_t *buf, int samples, float *phase) {
    float freq = 440.0f;
    float dt = 1.0f / SIM_AUDIO_RATE;
    for (int i = 0; i < samples; i++) {
        buf[i] = (int16_t)(sinf(*phase) * 8000.0f);
        *phase += 2.0f * M_PI * freq * dt;
        if (*phase > 2.0f * M_PI) *phase -= 2.0f * M_PI;
    }
}

/* List ROM files */
static void list_roms(const char *dir) {
    DIR *d = opendir(dir);
    if (!d) {
        printf("[SIM] No ROM directory at %s\n", dir);
        return;
    }

    printf("[SIM] ROM files in %s:\n", dir);
    struct dirent *entry;
    int count = 0;
    while ((entry = readdir(d)) != NULL) {
        const char *name = entry->d_name;
        int len = strlen(name);
        if (len > 4 && (
            strcasecmp(name + len - 4, ".sfc") == 0 ||
            strcasecmp(name + len - 4, ".smc") == 0 ||
            strcasecmp(name + len - 4, ".nes") == 0
        )) {
            printf("  [%d] %s\n", ++count, name);
        }
    }
    closedir(d);
    if (count == 0) printf("  (no .sfc/.smc/.nes files found)\n");
}

int main(int argc, char **argv) {
    const char *rom_dir = (argc > 1) ? argv[1] : SIM_SD_MOUNT;

    printf("ESP32 Emu Turbo — Simulator Test\n");
    printf("================================\n\n");

    if (sim_init() != 0) {
        fprintf(stderr, "Failed to initialize simulator\n");
        return 1;
    }

    list_roms(rom_dir);

    float audio_phase = 0;
    int16_t audio_buf[1024];
    int frame = 0;

    printf("\n[SIM] Running... Press ESC or close window to exit.\n");

    while (!sim_quit_requested()) {
        sim_poll_events();

        /* Draw display */
        draw_color_bars();

        uint16_t buttons = sim_buttons_read();
        draw_button_state(buttons);

        sim_display_flush();

        /* Generate audio (440Hz tone when any button pressed) */
        if (buttons) {
            generate_test_tone(audio_buf, 512, &audio_phase);
            sim_audio_write(audio_buf, 512);
        }

        /* Print button state periodically */
        if (frame % 60 == 0 && buttons) {
            printf("[SIM] Buttons: 0x%03X", buttons);
            if (buttons & SIM_BTN_UP)     printf(" UP");
            if (buttons & SIM_BTN_DOWN)   printf(" DOWN");
            if (buttons & SIM_BTN_LEFT)   printf(" LEFT");
            if (buttons & SIM_BTN_RIGHT)  printf(" RIGHT");
            if (buttons & SIM_BTN_A)      printf(" A");
            if (buttons & SIM_BTN_B)      printf(" B");
            if (buttons & SIM_BTN_X)      printf(" X");
            if (buttons & SIM_BTN_Y)      printf(" Y");
            if (buttons & SIM_BTN_START)  printf(" START");
            if (buttons & SIM_BTN_SELECT) printf(" SEL");
            if (buttons & SIM_BTN_L)      printf(" L");
            if (buttons & SIM_BTN_R)      printf(" R");
            printf("\n");
        }

        frame++;
        SDL_Delay(16);  /* ~60fps */
    }

    sim_shutdown();
    printf("[SIM] Test complete — %d frames rendered\n", frame);
    return 0;
}
