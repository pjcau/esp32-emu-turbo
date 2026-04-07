/**
 * ROM Validation — header parsing for NES, SNES, GB/GBC, Genesis, SMS, GG, PCE
 */

#ifdef SIM_BUILD

#include "rom_check.h"
#include <stdio.h>
#include <string.h>
#include <strings.h>

platform_t rom_detect_platform(const char *filename) {
    int len = strlen(filename);
    if (len < 3) return PLATFORM_UNKNOWN;

    const char *ext = filename + len - 4;
    if (len > 4) {
        if (strcasecmp(ext, ".sfc") == 0 || strcasecmp(ext, ".smc") == 0) return PLATFORM_SNES;
        if (strcasecmp(ext, ".nes") == 0) return PLATFORM_NES;
        if (strcasecmp(ext, ".gbc") == 0) return PLATFORM_GBC;
        if (strcasecmp(ext, ".gen") == 0 || strcasecmp(ext, ".bin") == 0) return PLATFORM_GEN;
        if (strcasecmp(ext, ".sms") == 0) return PLATFORM_SMS;
        if (strcasecmp(ext, ".pce") == 0) return PLATFORM_PCE;
    }
    ext = filename + len - 3;
    if (strcasecmp(ext, ".gb") == 0) return PLATFORM_GB;
    if (strcasecmp(ext, ".gg") == 0) return PLATFORM_GG;
    if (strcasecmp(ext, ".md") == 0) return PLATFORM_GEN;

    return PLATFORM_UNKNOWN;
}

const char *rom_platform_name(platform_t p) {
    switch (p) {
    case PLATFORM_NES:  return "NES";
    case PLATFORM_SNES: return "SNES";
    case PLATFORM_GB:   return "Game Boy";
    case PLATFORM_GBC:  return "Game Boy Color";
    case PLATFORM_GEN:  return "Genesis/Mega Drive";
    case PLATFORM_SMS:  return "Master System";
    case PLATFORM_GG:   return "Game Gear";
    case PLATFORM_PCE:  return "PC Engine";
    default:            return "Unknown";
    }
}

/* ── NES (iNES header) ──────────────────────────────────── */

static rom_info_t check_nes(const uint8_t *data, size_t size) {
    rom_info_t info = {.platform = PLATFORM_NES};

    if (size < 16 || memcmp(data, "NES\x1a", 4) != 0) {
        info.valid = 0;
        snprintf(info.error, sizeof(info.error), "Missing iNES header (NES\\x1A)");
        return info;
    }

    info.nes.prg_size = data[4] * 16384;
    info.nes.chr_size = data[5] * 8192;
    info.nes.mapper = ((data[6] >> 4) & 0x0F) | (data[7] & 0xF0);
    info.nes.mirroring = (data[6] & 1) ? 1 : 0;  /* 0=H, 1=V */

    snprintf(info.title, sizeof(info.title), "NES ROM (mapper %d)", info.nes.mapper);
    snprintf(info.region, sizeof(info.region), "NTSC");
    info.rom_size = size;
    info.valid = 1;

    /* Basic size check */
    uint32_t expected = 16 + info.nes.prg_size + info.nes.chr_size;
    if (size < expected) {
        info.valid = 0;
        snprintf(info.error, sizeof(info.error),
                 "Size mismatch: file %zu, expected >= %u", size, expected);
    }
    return info;
}

/* ── SNES ───────────────────────────────────────────────── */

static int snes_check_header(const uint8_t *data, size_t size, int offset) {
    if ((size_t)(offset + 0x30) > size) return 0;
    const uint8_t *hdr = data + offset;

    /* Checksum complement check: bytes 0x1C-0x1F */
    uint16_t checksum = hdr[0x1E] | (hdr[0x1F] << 8);
    uint16_t complement = hdr[0x1C] | (hdr[0x1D] << 8);
    return (checksum + complement) == 0xFFFF;
}

static rom_info_t check_snes(const uint8_t *data, size_t size) {
    rom_info_t info = {.platform = PLATFORM_SNES, .rom_size = size};

    /* Try LoROM (0x7FC0) and HiROM (0xFFC0) header locations */
    int header_offset = -1;
    int has_copier = (size & 0x3FF) == 0x200;  /* 512-byte copier header */
    int base = has_copier ? 0x200 : 0;

    if (snes_check_header(data, size, base + 0xFFC0)) {
        header_offset = base + 0xFFC0;
        info.snes.rom_type = 1;  /* HiROM */
    } else if (snes_check_header(data, size, base + 0x7FC0)) {
        header_offset = base + 0x7FC0;
        info.snes.rom_type = 0;  /* LoROM */
    }

    if (header_offset < 0) {
        /* No valid checksum — try to accept anyway if reasonable size */
        if (size >= 0x8000) {
            header_offset = base + 0x7FC0;
            info.snes.rom_type = 0;
            info.valid = 1;
            snprintf(info.error, sizeof(info.error), "Warning: checksum mismatch");
        } else {
            info.valid = 0;
            snprintf(info.error, sizeof(info.error), "No valid SNES header found");
            return info;
        }
    } else {
        info.valid = 1;
    }

    /* Extract title (21 bytes at header offset) */
    if ((size_t)(header_offset + 21) <= size) {
        memcpy(info.title, data + header_offset, 21);
        info.title[21] = '\0';
        /* Clean non-printable */
        for (int i = 0; i < 21; i++) {
            if (info.title[i] < 32 || info.title[i] > 126) info.title[i] = ' ';
        }
    }

    snprintf(info.region, sizeof(info.region), "%s",
             info.snes.rom_type ? "HiROM" : "LoROM");
    return info;
}

/* ── Game Boy / Game Boy Color ──────────────────────────── */

static rom_info_t check_gb(const uint8_t *data, size_t size, int is_gbc) {
    rom_info_t info = {.platform = is_gbc ? PLATFORM_GBC : PLATFORM_GB, .rom_size = size};

    if (size < 0x150) {
        info.valid = 0;
        snprintf(info.error, sizeof(info.error), "File too small for GB header");
        return info;
    }

    /* Nintendo logo check at 0x104-0x133 */
    static const uint8_t logo[] = {
        0xCE,0xED,0x66,0x66,0xCC,0x0D,0x00,0x0B,
        0x03,0x73,0x00,0x83,0x00,0x0C,0x00,0x0D,
    };
    if (memcmp(data + 0x104, logo, sizeof(logo)) != 0) {
        info.valid = 0;
        snprintf(info.error, sizeof(info.error), "Invalid Nintendo logo");
        return info;
    }

    /* Title at 0x134-0x143 */
    memcpy(info.title, data + 0x134, 16);
    info.title[16] = '\0';
    for (int i = 0; i < 16; i++) {
        if (info.title[i] < 32 || info.title[i] > 126) info.title[i] = '\0';
    }

    info.gb.cgb_flag = data[0x143];
    info.gb.sgb_flag = data[0x146];
    info.gb.mbc_type = data[0x147];
    info.gb.rom_banks = 2 << data[0x148];

    /* Header checksum */
    uint8_t sum = 0;
    for (int i = 0x134; i <= 0x14C; i++) sum = sum - data[i] - 1;
    info.valid = (sum == data[0x14D]);
    if (!info.valid) {
        snprintf(info.error, sizeof(info.error), "Header checksum mismatch");
    }

    snprintf(info.region, sizeof(info.region), "MBC%d", info.gb.mbc_type);
    return info;
}

/* ── Genesis / Mega Drive ───────────────────────────────── */

static rom_info_t check_gen(const uint8_t *data, size_t size) {
    rom_info_t info = {.platform = PLATFORM_GEN, .rom_size = size};

    if (size < 0x200) {
        info.valid = 0;
        snprintf(info.error, sizeof(info.error), "File too small for Genesis header");
        return info;
    }

    /* Check for "SEGA" at 0x100 or 0x101 */
    if (memcmp(data + 0x100, "SEGA", 4) == 0 ||
        memcmp(data + 0x101, "SEGA", 4) == 0) {
        info.valid = 1;
    } else {
        info.valid = 1;  /* Accept anyway — some homebrew lacks SEGA header */
        snprintf(info.error, sizeof(info.error), "Warning: no SEGA signature");
    }

    /* Title at 0x120 (domestic) or 0x150 (overseas) */
    memcpy(info.title, data + 0x120, 48);
    info.title[48] = '\0';
    for (int i = 47; i >= 0 && info.title[i] == ' '; i--) info.title[i] = '\0';

    /* Region at 0x1F0 */
    char region_byte = data[0x1F0];
    snprintf(info.region, sizeof(info.region), "%c", region_byte);
    return info;
}

/* ── Master System / Game Gear ──────────────────────────── */

static rom_info_t check_sms(const uint8_t *data, size_t size, int is_gg) {
    rom_info_t info = {.platform = is_gg ? PLATFORM_GG : PLATFORM_SMS, .rom_size = size};

    /* SMS/GG header at 0x7FF0 */
    if (size >= 0x8000 && memcmp(data + 0x7FF0, "TMR SEGA", 8) == 0) {
        info.valid = 1;
        snprintf(info.title, sizeof(info.title), "%s ROM", is_gg ? "Game Gear" : "SMS");
        int region_code = (data[0x7FFF] >> 4) & 0x0F;
        snprintf(info.region, sizeof(info.region), "Region %d", region_code);
    } else {
        info.valid = 1;  /* Accept without header */
        snprintf(info.title, sizeof(info.title), "%s ROM (no header)", is_gg ? "GG" : "SMS");
        snprintf(info.error, sizeof(info.error), "Warning: no TMR SEGA signature");
    }
    return info;
}

/* ── PC Engine ──────────────────────────────────────────── */

static rom_info_t check_pce(const uint8_t *data, size_t size) {
    rom_info_t info = {.platform = PLATFORM_PCE, .rom_size = size};

    /* PCE ROMs don't have a standard header — accept if size is reasonable */
    if (size < 8192) {
        info.valid = 0;
        snprintf(info.error, sizeof(info.error), "File too small for PCE ROM");
        return info;
    }

    info.valid = 1;
    snprintf(info.title, sizeof(info.title), "PC Engine ROM");

    /* Check for 512-byte copier header */
    if ((size & 0x1FFF) == 0x200) {
        snprintf(info.region, sizeof(info.region), "HuCard+hdr");
    } else {
        snprintf(info.region, sizeof(info.region), "HuCard");
    }
    return info;
}

/* ── Public API ─────────────────────────────────────────── */

rom_info_t rom_check(const uint8_t *data, size_t size, const char *filename) {
    platform_t p = rom_detect_platform(filename);

    switch (p) {
    case PLATFORM_NES:  return check_nes(data, size);
    case PLATFORM_SNES: return check_snes(data, size);
    case PLATFORM_GB:   return check_gb(data, size, 0);
    case PLATFORM_GBC:  return check_gb(data, size, 1);
    case PLATFORM_GEN:  return check_gen(data, size);
    case PLATFORM_SMS:  return check_sms(data, size, 0);
    case PLATFORM_GG:   return check_sms(data, size, 1);
    case PLATFORM_PCE:  return check_pce(data, size);
    default: {
        rom_info_t info = {.platform = PLATFORM_UNKNOWN, .valid = 0};
        snprintf(info.error, sizeof(info.error), "Unknown platform");
        return info;
    }
    }
}

void rom_print_info(const rom_info_t *info) {
    printf("[ROM] Platform: %s\n", rom_platform_name(info->platform));
    printf("[ROM] Title:    %s\n", info->title[0] ? info->title : "(unknown)");
    printf("[ROM] Region:   %s\n", info->region[0] ? info->region : "(unknown)");
    printf("[ROM] Size:     %uKB\n", info->rom_size / 1024);
    printf("[ROM] Valid:    %s\n", info->valid ? "YES" : "NO");
    if (info->error[0]) printf("[ROM] Note:     %s\n", info->error);

    if (info->platform == PLATFORM_NES) {
        printf("[ROM] Mapper:   %d\n", info->nes.mapper);
        printf("[ROM] PRG:      %dKB  CHR: %dKB\n",
               info->nes.prg_size / 1024, info->nes.chr_size / 1024);
    }
    if (info->platform == PLATFORM_GB || info->platform == PLATFORM_GBC) {
        printf("[ROM] MBC:      %d  Banks: %d\n",
               info->gb.mbc_type, info->gb.rom_banks);
    }
}

#endif
