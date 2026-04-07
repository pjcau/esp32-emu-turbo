/* Benchmark shared declarations */
#pragma once
#include <stdint.h>
#include <stddef.h>

#define WARMUP_FRAMES   60
#define BENCH_FRAMES   300

uint8_t *bench_load_file(const char *path, size_t *out_size);
uint8_t *bench_load_embedded(const uint8_t *start, const uint8_t *end, size_t *out_size);
void bench_print_result(const char *label, int frames, int64_t elapsed_us);

/* ROM-in-memory variants */
void bench_nes_rom(uint8_t *rom, size_t sz);
void bench_gb_rom(uint8_t *rom, size_t sz, const char *label);
void bench_sms_rom(uint8_t *rom, size_t sz, const char *label);
void bench_pce_rom(uint8_t *rom, size_t sz);

/* File-path variants (for SPIFFS) */
void bench_nes(const char *path);
void bench_gb(const char *path, const char *label);
void bench_sms(const char *path, const char *label);
void bench_pce(const char *path);
void bench_snes(const char *path);
void bench_snes_rom(uint8_t *rom, size_t sz);

/* QEMU display + input */
int qemu_display_init(void);
void qemu_display_write(const uint16_t *fb);
uint16_t qemu_input_read(void);
