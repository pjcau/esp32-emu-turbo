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

The **ILI9488 3.95" with 8-bit 8080 parallel interface** (bare panel + 40-pin FPC) is the only viable option for SNES at 60 fps.

## GPIO Pin Assignment

Complete pin mapping for the ESP32-S3 N16R8 DevKitC-1:

### Display (8080 Parallel) — 12 GPIOs

| GPIO | Function | FPC Pin | Notes |
|---|---|---|---|
| GPIO4 | LCD_D0 | 17 | Data bus bit 0 |
| GPIO5 | LCD_D1 | 18 | Data bus bit 1 |
| GPIO6 | LCD_D2 | 19 | Data bus bit 2 |
| GPIO7 | LCD_D3 | 20 | Data bus bit 3 |
| GPIO8 | LCD_D4 | 21 | Data bus bit 4 |
| GPIO9 | LCD_D5 | 22 | Data bus bit 5 |
| GPIO10 | LCD_D6 | 23 | Data bus bit 6 |
| GPIO11 | LCD_D7 | 24 | Data bus bit 7 |
| GPIO12 | LCD_CS | 9 | Chip select (active low) |
| GPIO13 | LCD_RST | 15 | Reset |
| GPIO14 | LCD_DC | 10 | Data/Command select |
| GPIO46 | LCD_WR | 11 | Write strobe |

**Hardwired on PCB (no GPIO):**
- **LCD_RD** (FPC pin 12) → tied HIGH to +3V3 (no read-back from ILI9488 needed)
- **LCD_BL / LED-A** (FPC pin 33) → **+5V through R27 (20 Ω)** on net `LED_BLA` (always-on backlight, no PWM). Boards fabricated through v4.3.1 predate this and tie LED-A straight to +3V3 with no series element.

FPC power pins: 6=VDDI(+3V3), 7=VDDA(+3V3), 5/16/34-36/37=GND, 38=IM0(+3V3), 39=IM1(+3V3), 40=IM2(GND).
Interface mode: IM2=0, IM1=1, IM0=1 → 8080 8-bit parallel.

:::info FPC Pin Reversal on PCB
The FPC pin numbers above refer to the **display** pin numbering. On the PCB, the display is mounted in landscape (CCW rotation) with the FPC tail passing straight through a slot to the J4 connector on the bottom side. Because the cable doesn't twist, display Pin N contacts connector Pad (41−N). For example, display Pin 17 (LCD_D0) connects to J4 Pad 24. The PCB routing accounts for this reversal automatically.
:::

### SD Card (SPI) — 4 GPIOs

| GPIO | Function | Notes |
|---|---|---|
| GPIO44 | SD_MOSI | Master Out Slave In |
| GPIO43 | SD_MISO | Master In Slave Out |
| GPIO38 | SD_CLK | SPI clock |
| GPIO39 | SD_CS | Chip select |

### Audio (PDM) — 1 GPIO

| GPIO | Function | Notes |
|---|---|---|
| GPIO17 | I2S_DOUT | PDM sigma-delta data out → PAM8403 analog input (via C22) |

**Not used by audio:** GPIO15 and GPIO16 were reserved as `I2S_BCLK` / `I2S_LRCK`
until 2026-07-26 (R10-LOW-2). The path is **PDM TX**, which drives only DOUT
(`audio.c` sets `.clk = I2S_GPIO_UNUSED`), so both pins are unconnected on the
PCB and free for v2.

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
| GPIO45 | L shoulder | Internal pull-up only (GPIO45 is VDD_SPI strapping, R14 DNP) |
| GPIO3 | R shoulder | 10k pull-up + 100nF debounce |

### USB (native) — 2 GPIOs

| GPIO | Function | Notes |
|---|---|---|
| GPIO19 | USB D- | Native USB data (firmware flash + debug) |
| GPIO20 | USB D+ | Native USB data (firmware flash + debug) |

### Reserved GPIOs

| GPIOs | Reason |
|---|---|
| GPIO26–GPIO32 | Internal SPI flash bus of the WROOM-1 module — not brought out on any module pin |
| GPIO33–GPIO37 | Octal PSRAM of the N16R8 variant. GPIO33/34 are not brought out; GPIO35–37 appear on module pins 28–30 but **must stay unconnected** (explicit no-connect markers in the schematic) |

### Summary

| Category | GPIOs Used |
|---|---|
| Display (8080 parallel) | 12 |
| SD Card (SPI) | 4 |
| Audio (PDM) | 1 |
| Buttons | 12 |
| USB (native) | 2 |
| **Total** | **31** |
| Exposed on the WROOM-1 module | 36 |
| **Remaining** | **5** (GPIO15, GPIO16, and the three PSRAM pins that must stay free) |

The bring-up firmware asserts this independently — `config.gpio_unique` reports
`31 GPIO assignments, all distinct` (see [Bring-Up Protocol](/docs/manufacturing/bring-up-protocol)).

## Audio Architecture

The SNES has a sophisticated audio system (SPC700 + S-DSP) with 8 channels of BRR-compressed audio. Our implementation:

```
ESP32-S3 (PDM TX + DMA) ──> C22 (DC block) ──> PAM8403 Class-D Amp ──> 28mm 8Ω Speaker
     │                                              │
     GPIO17 (I2S_DOUT)                       R20/R21 bias to VREF (pin 8)
```

- **Sample rate:** 32 kHz (matches SNES native rate)
- **Bit depth:** 16-bit
- **Interface:** PDM sigma-delta on a single pin — the PAM8403's analog input plus
  its input RC network reconstructs the waveform, so no external DAC and no
  BCLK/LRCK are needed
- **DMA buffer:** Double-buffered for glitch-free playback
- **Amplifier:** PAM8403 2x3W Class-D (only the right channel drives the mono speaker)

## Reference Implementations

| Project | Platform | SNES Support |
|---|---|---|
| [esp-box-emu](https://github.com/esp-cpp/esp-box-emu) | ESP32-S3-BOX-3 | Yes (with snes9x core) |
| [snes9x2005](https://github.com/libretro/snes9x2005) | libretro core | Lightweight, suitable for embedded |
| [Retro-Go](https://github.com/ducalex/retro-go) | Various ESP32 | Partial (limited performance) |
