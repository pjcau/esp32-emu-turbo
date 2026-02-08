---
id: feasibility
title: Feasibility Analysis
sidebar_position: 2
---

# Feasibility Analysis

## Why ESP32-S3 Over Original ESP32

| Feature | ESP32 (LX6) | ESP32-S3 (LX7) |
|---|---|---|
| Core | Dual Xtensa LX6, 240 MHz | Dual Xtensa LX7, 240 MHz |
| SIMD / PIE | No | Yes (128-bit, 2x-10x speedup) |
| Max PSRAM | 4 MB (Quad SPI) | 16 MB (Octal SPI DDR, ~84 MB/s) |
| Native USB | No | Yes (OTG, direct USB gamepad) |
| GPIO | 34 | 45 |

The ESP32-S3 is **the mandatory choice for SNES**: SIMD instructions accelerate pixel manipulation, Octal PSRAM is 4x faster, and 8 MB is enough for SNES ROMs up to 6 MB + emulator buffers.

## Hardware Schematic

```
                         +------------------+
                         |                  |
    USB-C ──────────────>│   IP5306 Module  │──── 5V rail
                         │  (charge+boost)  │
                         +--------+---------+
                                  |
                          +-------+-------+
                          |               |
                    +-----+-----+   +-----+-----+
                    | LiPo Batt |   | AMS1117    |
                    | 3.7V      |   | 5V -> 3.3V |
                    | 5000 mAh  |   +-----+------+
                    |           |         |
                    +-----------+         | 3.3V
                                          |
                              +-----------+-----------+
                              |                       |
                              |     ESP32-S3 N16R8    |
                              |   (16MB Flash, 8MB    |
                              |    Octal PSRAM)       |
                              |                       |
                              +--+--+--+--+--+--+--+-+
                                 |  |  |  |  |  |  |
                    +------------+  |  |  |  |  |  +----------+
                    |               |  |  |  |  |             |
              +-----+-----+  +-----+--+  |  +--+-----+  +----+----+
              | Display    |  | SD Card|  |  | Audio  |  | Buttons |
              | ST7796S    |  | Module |  |  | DAC -> |  | D-pad   |
              | 3.5"-4"    |  | SPI    |  |  | PAM8403|  | A,B,X,Y |
              | 8-bit par  |  +--------+  |  | Speaker|  | Start   |
              | (8080)     |              |  +--------+  | Select  |
              +------------+              |              | L, R    |
                                          |              +---------+
                                    +-----+-----+
                                    | Joystick  |
                                    | PSP-style |
                                    | (optional)|
                                    +-----------+
```

## GPIO Connections (estimate)

| Peripheral | Interface | GPIOs Required |
|---|---|---|
| Display (8-bit parallel) | 8080 parallel | ~13 (8 data + 5 control) |
| Display (SPI alternative) | SPI | ~5 (MOSI, CLK, CS, DC, RST) |
| SD Card | SPI | ~4 (MOSI, MISO, CLK, CS) |
| Buttons (12 keys: D-pad, A, B, X, Y, Start, Select, L, R) | Direct GPIO | ~12 |
| Audio DAC (I2S) | I2S | ~3 (BCLK, LRCK, DATA) |
| Analog joystick | ADC | ~2 (X, Y) |
| **Total (8-bit display)** | | **~34** |
| **Total (SPI display)** | | **~26** |

The ESP32-S3 has **45 GPIOs**, so both configurations are feasible.

## Feasibility Assessment

### Primary target: SNES
- SNES requires 65C816 CPU emulation + complex PPU (mode 7, rotation, scaling)
- ESP32-S3 with **SIMD/PIE** instructions provides 2-10x speedup for pixel operations
- **8 MB Octal PSRAM** at ~84 MB/s handles SNES VRAM + ROM caching
- **Parallel display interface is mandatory** for 60 fps frame delivery
- Reference: [esp-box-emu](https://github.com/esp-cpp/esp-box-emu) runs SNES on ESP32-S3-BOX hardware
- Some complex SNES games (SuperFX, SA-1 co-processors) may need frame skipping

### Also supported: NES
- ESP32-S3 at 240 MHz with 8 MB PSRAM handles NES emulation with no issues
- Existing projects (Retro-Go, esp-box-emu) demonstrate NES at **60 fps**
- NES runs comfortably even with parallel display overhead

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Insufficient SNES frame rate | Medium | Parallel display + code optimization |
| Not enough GPIOs | Low | ESP32-S3 has 45 GPIOs, ample margin |
| Excessive battery drain | Low | 5000mAh battery, ~14-16h estimated life |
| IP5306 auto-shutdown in sleep | Medium | I2C configuration or periodic pulse |
| Audio crackling / latency | Low | I2S with DMA buffer |

### Conclusion

**The project is feasible with SNES as the primary target.** The ESP32-S3's SIMD/PIE instructions and Octal PSRAM provide the performance needed for SNES emulation. NES runs flawlessly as a bonus. The 8-bit 8080 parallel display is mandatory for SNES frame rates. The budget of ~$42-55 is modest, and all components are readily available on AliExpress.

## Reference Software

| Project | Platforms |
|---|---|
| [Retro-Go](https://github.com/ducalex/retro-go) | NES, GB, GBC, SMS, GG, PCE |
| [esp-box-emu](https://github.com/esp-cpp/esp-box-emu) | NES, SNES, Genesis |
| Nofrendo | NES (portable emulator for ESP32) |
