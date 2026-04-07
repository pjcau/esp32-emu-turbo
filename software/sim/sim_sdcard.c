/**
 * SD Card driver — Simulator implementation
 * Uses host filesystem instead of SPI SD card
 */

#ifdef SIM_BUILD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <dirent.h>
#include <sys/stat.h>

#define MAX_ROMS 256

typedef struct {
    char path[512];
    char name[256];
    long size;
    char type[8];  /* "SNES" or "NES" */
} rom_entry_t;

static rom_entry_t g_roms[MAX_ROMS];
static int g_rom_count = 0;
static const char *g_rom_dir = NULL;

int sdcard_sim_init(const char *rom_dir) {
    g_rom_dir = rom_dir;
    g_rom_count = 0;
    printf("[SD] Mounted: %s\n", rom_dir);
    return 0;
}

static void scan_dir(const char *dir) {
    DIR *d = opendir(dir);
    if (!d) return;

    struct dirent *entry;
    while ((entry = readdir(d)) != NULL && g_rom_count < MAX_ROMS) {
        if (entry->d_name[0] == '.') continue;

        char full_path[512];
        snprintf(full_path, sizeof(full_path), "%s/%s", dir, entry->d_name);

        struct stat st;
        if (stat(full_path, &st) != 0) continue;

        /* Recurse into subdirectories */
        if (S_ISDIR(st.st_mode)) {
            scan_dir(full_path);
            continue;
        }

        const char *name = entry->d_name;
        int len = strlen(name);
        if (len < 5) continue;

        const char *ext = name + len - 4;
        const char *type = NULL;
        if (strcasecmp(ext, ".sfc") == 0 || strcasecmp(ext, ".smc") == 0) {
            type = "SNES";
        } else if (strcasecmp(ext, ".nes") == 0) {
            type = "NES";
        } else if (strcasecmp(ext, ".gbc") == 0) {
            type = "GBC";
        } else if (len > 3 && strcasecmp(name + len - 3, ".gb") == 0) {
            type = "GB";
        } else if (strcasecmp(ext, ".gen") == 0 || strcasecmp(ext, ".bin") == 0 ||
                   strcasecmp(ext, ".md") == 0) {
            type = "GEN";
        } else if (strcasecmp(ext, ".sms") == 0) {
            type = "SMS";
        } else if (strcasecmp(ext, ".pce") == 0) {
            type = "PCE";
        } else if (len > 3 && strcasecmp(name + len - 3, ".gg") == 0) {
            type = "GG";
        }
        if (!type) continue;

        rom_entry_t *rom = &g_roms[g_rom_count];
        snprintf(rom->path, sizeof(rom->path), "%s", full_path);
        strncpy(rom->name, name, sizeof(rom->name) - 1);
        strncpy(rom->type, type, sizeof(rom->type) - 1);
        rom->size = st.st_size;
        g_rom_count++;
    }
    closedir(d);
}

int sdcard_sim_scan_roms(void) {
    if (!g_rom_dir) return 0;
    g_rom_count = 0;
    scan_dir(g_rom_dir);

    printf("[SD] Found %d ROM file(s)\n", g_rom_count);
    for (int i = 0; i < g_rom_count; i++) {
        printf("[SD]   [%d] %s (%s, %ldKB)\n",
               i, g_roms[i].name, g_roms[i].type, g_roms[i].size / 1024);
    }
    return g_rom_count;
}

int sdcard_sim_get_rom_count(void) {
    return g_rom_count;
}

const char *sdcard_sim_get_rom_name(int index) {
    if (index < 0 || index >= g_rom_count) return NULL;
    return g_roms[index].name;
}

const char *sdcard_sim_get_rom_path(int index) {
    if (index < 0 || index >= g_rom_count) return NULL;
    return g_roms[index].path;
}

long sdcard_sim_get_rom_size(int index) {
    if (index < 0 || index >= g_rom_count) return 0;
    return g_roms[index].size;
}

const char *sdcard_sim_get_rom_type(int index) {
    if (index < 0 || index >= g_rom_count) return NULL;
    return g_roms[index].type;
}

uint8_t *sdcard_sim_load_rom(int index) {
    if (index < 0 || index >= g_rom_count) return NULL;

    FILE *f = fopen(g_roms[index].path, "rb");
    if (!f) {
        printf("[SD] ERROR: cannot open %s\n", g_roms[index].path);
        return NULL;
    }

    uint8_t *data = malloc(g_roms[index].size);
    if (!data) {
        fclose(f);
        printf("[SD] ERROR: out of memory for %ldKB ROM\n",
               g_roms[index].size / 1024);
        return NULL;
    }

    fread(data, 1, g_roms[index].size, f);
    fclose(f);

    printf("[SD] Loaded: %s (%ldKB)\n",
           g_roms[index].name, g_roms[index].size / 1024);
    return data;
}

#endif
