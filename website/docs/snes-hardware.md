---
id: snes-hardware
title: SNES Hardware Specification
sidebar_position: 3
---

# SNES-Focused Hardware Specification

## Why SNES as Primary Target

The ESP32-S3 makes SNES emulation achievable on a handheld device thanks to three key advantages:

- **SIMD/PIE instructions** — 128-bit vector operations provide 2-10x speedup for pixel manipulation, critical for SNES PPU rendering (mode 7, rotation, scaling)
- **Octal PSRAM at ~84 MB/s** — 4x faster than Quad SPI PSRAM on the original ESP32, enabling real-time frame buffer access without stalling the CPU
- **Dual-core LX7 at 240 MHz** — dedicated cores for CPU emulation and PPU/audio rendering in parallel

Reference implementation: [esp-box-emu](https://github.com/esp-cpp/esp-box-emu) demonstrates NES, SNES, and Genesis emulation running on ESP32-S3-BOX hardware.

## SNES Emulation Requirements vs ESP32-S3

| Requirement | Original SNES | ESP32-S3 N16R8 |
|---|---|---|
| **CPU** | 65C816 @ 3.58 MHz | Dual LX7 @ 240 MHz + SIMD (>60x headroom) |
| **PPU** (graphics) | 2 PPU chips, mode 7, 4 BG layers | SIMD pixel ops + DMA to parallel display |
| **WRAM** | 128 KB | 512 KB internal SRAM |
| **VRAM** | 64 KB | 8 MB Octal PSRAM (shared) |
| **ROM size** | Up to 6 MB (48 Mbit) | SD card streaming + PSRAM cache |
| **Audio** | SPC700 + S-DSP, 8 channels, 32 kHz | I2S DMA output at 32 kHz stereo |
| **Frame rate** | 60 fps (NTSC) / 50 fps (PAL) | Parallel display required for 60 fps |
| **Resolution** | 256×224 (most games) | Scaled to 320×480 display |

## Display: Parallel vs SPI — Why 8080 is Mandatory

For SNES emulation, the display interface is the critical bottleneck:

| Parameter | SPI | 8-bit 8080 Parallel |
|---|---|---|
| **Max clock** | ~40 MHz | ~20 MHz |
| **Bits per clock** | 1 | 8 |
| **Throughput** | ~5 MB/s | ~20 MB/s |
| **320×480 @ 16-bit, 60 fps** | 18.4 MB/s needed | 18.4 MB/s needed |
| **Feasible at 60 fps?** | No (3.6x over capacity) | Yes (1.09x margin) |

The **ST7796S 4.0" with 8-bit 8080 parallel interface** is the only viable option for SNES at 60 fps.

## GPIO Pin Assignment

Complete pin mapping for the ESP32-S3 N16R8 DevKitC-1:

### Display (8080 Parallel) — 14 GPIOs

| GPIO | Function | Notes |
|---|---|---|
| GPIO4 | LCD_D0 | Data bus bit 0 |
| GPIO5 | LCD_D1 | Data bus bit 1 |
| GPIO6 | LCD_D2 | Data bus bit 2 |
| GPIO7 | LCD_D3 | Data bus bit 3 |
| GPIO8 | LCD_D4 | Data bus bit 4 |
| GPIO9 | LCD_D5 | Data bus bit 5 |
| GPIO10 | LCD_D6 | Data bus bit 6 |
| GPIO11 | LCD_D7 | Data bus bit 7 |
| GPIO12 | LCD_CS | Chip select (active low) |
| GPIO13 | LCD_RST | Reset |
| GPIO14 | LCD_DC | Data/Command select |
| GPIO46 | LCD_WR | Write strobe |
| GPIO3 | LCD_RD | Read strobe |
| GPIO45 | LCD_BL | Backlight PWM |

### SD Card (SPI) — 4 GPIOs

| GPIO | Function | Notes |
|---|---|---|
| GPIO36 | SD_MOSI | Master Out Slave In |
| GPIO37 | SD_MISO | Master In Slave Out |
| GPIO38 | SD_CLK | SPI clock |
| GPIO39 | SD_CS | Chip select |

### Audio (I2S) — 3 GPIOs

| GPIO | Function | Notes |
|---|---|---|
| GPIO15 | I2S_BCLK | Bit clock |
| GPIO16 | I2S_LRCK | Left/Right channel clock |
| GPIO17 | I2S_DOUT | Serial data out |

### Buttons (GPIO Input, active-low) — 12 GPIOs

| GPIO | Button | Notes |
|---|---|---|
| GPIO40 | D-pad UP | 10k pull-up + 100nF debounce |
| GPIO41 | D-pad DOWN | 10k pull-up + 100nF debounce |
| GPIO42 | D-pad LEFT | 10k pull-up + 100nF debounce |
| GPIO1 | D-pad RIGHT | 10k pull-up + 100nF debounce |
| GPIO2 | A | 10k pull-up + 100nF debounce |
| GPIO48 | B | 10k pull-up + 100nF debounce |
| GPIO47 | X | 10k pull-up + 100nF debounce |
| GPIO21 | Y | 10k pull-up + 100nF debounce |
| GPIO0 | SELECT | Boot button (dual-use) |
| GPIO18 | START | 10k pull-up + 100nF debounce |
| GPIO35 | L shoulder | 10k pull-up + 100nF debounce |
| GPIO19 | R shoulder | 10k pull-up + 100nF debounce |

### Joystick (ADC, optional) — 2 GPIOs

| GPIO | Function | Notes |
|---|---|---|
| GPIO20 | JOY_X | ADC channel (0-3.3V) |
| GPIO33 | JOY_Y | ADC channel (0-3.3V) |

### Reserved GPIOs

| GPIOs | Reason |
|---|---|
| GPIO26–GPIO32 | Used by Octal PSRAM (N16R8 module) |
| GPIO43 (TX0) | UART0 TX (programming/debug) |
| GPIO44 (RX0) | UART0 RX (programming/debug) |

### Summary

| Category | GPIOs Used |
|---|---|
| Display (8080 parallel) | 14 |
| SD Card (SPI) | 4 |
| Audio (I2S) | 3 |
| Buttons | 12 |
| Joystick (optional) | 2 |
| **Total** | **35** |
| ESP32-S3 available | 45 |
| **Remaining** | **10** |

## Audio Architecture

The SNES has a sophisticated audio system (SPC700 + S-DSP) with 8 channels of BRR-compressed audio. Our implementation:

```
ESP32-S3 (I2S DMA) ──> PAM8403 Class-D Amp ──> 28mm 8Ω Speaker
     │                      │
     GPIO15 (BCLK)          Volume pot (10kΩ)
     GPIO16 (LRCK)
     GPIO17 (DOUT)
```

- **Sample rate:** 32 kHz stereo (matches SNES native rate)
- **Bit depth:** 16-bit
- **DMA buffer:** Double-buffered for glitch-free playback
- **Amplifier:** PAM8403 2x3W Class-D (only one channel used for mono speaker)

## Reference Implementations

| Project | Platform | SNES Support |
|---|---|---|
| [esp-box-emu](https://github.com/esp-cpp/esp-box-emu) | ESP32-S3-BOX-3 | Yes (with snes9x core) |
| [snes9x2005](https://github.com/libretro/snes9x2005) | libretro core | Lightweight, suitable for embedded |
| [Retro-Go](https://github.com/ducalex/retro-go) | Various ESP32 | Partial (limited performance) |
