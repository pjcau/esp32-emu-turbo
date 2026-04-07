/**
 * ESP32 Emu Turbo — Simulator HAL Implementation
 *
 * SDL2-based hardware abstraction for desktop testing.
 */

#ifdef SIM_BUILD

#include "sim_hal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ── Display ─────────────────────────────────────────────── */

static SDL_Window   *g_window = NULL;
static SDL_Renderer *g_renderer = NULL;
static SDL_Texture  *g_texture = NULL;
static uint16_t      g_framebuffer[SIM_LCD_WIDTH * SIM_LCD_HEIGHT];
static bool          g_quit = false;

int sim_display_init(void) {
    g_window = SDL_CreateWindow(
        "ESP32 Emu Turbo — Simulator",
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
        SIM_LCD_WIDTH * 2, SIM_LCD_HEIGHT * 2,  /* 2x scale */
        SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE
    );
    if (!g_window) {
        fprintf(stderr, "SDL_CreateWindow: %s\n", SDL_GetError());
        return -1;
    }

    g_renderer = SDL_CreateRenderer(g_window, -1,
        SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (!g_renderer) {
        fprintf(stderr, "SDL_CreateRenderer: %s\n", SDL_GetError());
        return -1;
    }

    /* RGB565 texture matching ILI9488 pixel format */
    g_texture = SDL_CreateTexture(g_renderer,
        SDL_PIXELFORMAT_RGB565,
        SDL_TEXTUREACCESS_STREAMING,
        SIM_LCD_WIDTH, SIM_LCD_HEIGHT);
    if (!g_texture) {
        fprintf(stderr, "SDL_CreateTexture: %s\n", SDL_GetError());
        return -1;
    }

    SDL_RenderSetLogicalSize(g_renderer, SIM_LCD_WIDTH, SIM_LCD_HEIGHT);
    memset(g_framebuffer, 0, sizeof(g_framebuffer));

    printf("[SIM] Display initialized: %dx%d (2x scale)\n",
           SIM_LCD_WIDTH, SIM_LCD_HEIGHT);
    return 0;
}

void sim_display_write(const uint16_t *pixels, int x, int y, int w, int h) {
    for (int row = 0; row < h && (y + row) < SIM_LCD_HEIGHT; row++) {
        int dst_offset = (y + row) * SIM_LCD_WIDTH + x;
        int src_offset = row * w;
        int copy_w = (x + w > SIM_LCD_WIDTH) ? (SIM_LCD_WIDTH - x) : w;
        memcpy(&g_framebuffer[dst_offset], &pixels[src_offset],
               copy_w * sizeof(uint16_t));
    }
}

void sim_display_flush(void) {
    SDL_UpdateTexture(g_texture, NULL, g_framebuffer,
                      SIM_LCD_WIDTH * sizeof(uint16_t));
    SDL_RenderClear(g_renderer);
    SDL_RenderCopy(g_renderer, g_texture, NULL, NULL);
    SDL_RenderPresent(g_renderer);
}

void sim_display_destroy(void) {
    if (g_texture)  SDL_DestroyTexture(g_texture);
    if (g_renderer) SDL_DestroyRenderer(g_renderer);
    if (g_window)   SDL_DestroyWindow(g_window);
}

/* ── Buttons ─────────────────────────────────────────────── */

static uint16_t g_button_state = 0;

/* Keyboard → button mapping */
static const struct { SDL_Scancode key; uint16_t mask; } KEYMAP[] = {
    { SDL_SCANCODE_W,         SIM_BTN_UP },
    { SDL_SCANCODE_S,         SIM_BTN_DOWN },
    { SDL_SCANCODE_A,         SIM_BTN_LEFT },
    { SDL_SCANCODE_D,         SIM_BTN_RIGHT },
    { SDL_SCANCODE_J,         SIM_BTN_A },
    { SDL_SCANCODE_K,         SIM_BTN_B },
    { SDL_SCANCODE_U,         SIM_BTN_X },
    { SDL_SCANCODE_I,         SIM_BTN_Y },
    { SDL_SCANCODE_RETURN,    SIM_BTN_START },
    { SDL_SCANCODE_BACKSPACE, SIM_BTN_SELECT },
    { SDL_SCANCODE_Q,         SIM_BTN_L },
    { SDL_SCANCODE_E,         SIM_BTN_R },
};
#define KEYMAP_COUNT (sizeof(KEYMAP) / sizeof(KEYMAP[0]))

uint16_t sim_buttons_read(void) {
    return g_button_state;
}

bool sim_quit_requested(void) {
    return g_quit;
}

/* ── Audio ───────────────────────────────────────────────── */

static SDL_AudioDeviceID g_audio_dev = 0;

int sim_audio_init(void) {
    SDL_AudioSpec want, have;
    SDL_zero(want);
    want.freq = SIM_AUDIO_RATE;
    want.format = AUDIO_S16SYS;
    want.channels = SIM_AUDIO_CHANNELS;
    want.samples = 1024;
    want.callback = NULL;  /* push mode */

    g_audio_dev = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
    if (g_audio_dev == 0) {
        fprintf(stderr, "SDL_OpenAudioDevice: %s\n", SDL_GetError());
        return -1;
    }

    SDL_PauseAudioDevice(g_audio_dev, 0);  /* start playback */

    printf("[SIM] Audio initialized: %dHz %d-bit mono\n",
           have.freq, SDL_AUDIO_BITSIZE(have.format));
    return 0;
}

void sim_audio_write(const int16_t *samples, int count) {
    if (g_audio_dev) {
        SDL_QueueAudio(g_audio_dev, samples, count * sizeof(int16_t));
    }
}

void sim_audio_destroy(void) {
    if (g_audio_dev) {
        SDL_CloseAudioDevice(g_audio_dev);
        g_audio_dev = 0;
    }
}

/* ── SD Card ─────────────────────────────────────────────── */

int sim_sd_init(void) {
    /* On host, ROMs are in SIM_SD_MOUNT directory */
    printf("[SIM] SD card mount: %s\n", SIM_SD_MOUNT);
    return 0;
}

/* ── Main ────────────────────────────────────────────────── */

int sim_init(void) {
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_EVENTS) != 0) {
        fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
        return -1;
    }

    if (sim_display_init() != 0) return -1;
    if (sim_audio_init() != 0) {
        printf("[SIM] WARNING: Audio not available (no ALSA in container)\n");
    }
    if (sim_sd_init() != 0) return -1;

    printf("[SIM] All subsystems initialized\n");
    printf("[SIM] Controls: WASD=D-pad, JK=AB, UI=XY, Enter=Start, Backspace=Select, QE=LR\n");
    return 0;
}

void sim_poll_events(void) {
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
        switch (e.type) {
        case SDL_QUIT:
            g_quit = true;
            break;

        case SDL_KEYDOWN:
        case SDL_KEYUP: {
            bool pressed = (e.type == SDL_KEYDOWN);

            /* ESC = quit */
            if (e.key.keysym.scancode == SDL_SCANCODE_ESCAPE) {
                g_quit = true;
                break;
            }

            /* Map keyboard to buttons */
            for (int i = 0; i < (int)KEYMAP_COUNT; i++) {
                if (e.key.keysym.scancode == KEYMAP[i].key) {
                    if (pressed)
                        g_button_state |= KEYMAP[i].mask;
                    else
                        g_button_state &= ~KEYMAP[i].mask;
                    break;
                }
            }
            break;
        }
        }
    }
}

void sim_shutdown(void) {
    sim_audio_destroy();
    sim_display_destroy();
    SDL_Quit();
    printf("[SIM] Shutdown complete\n");
}

#endif /* SIM_BUILD */
