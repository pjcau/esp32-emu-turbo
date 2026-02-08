---
id: schematics
title: Electrical Schematics
sidebar_position: 5
---

# Electrical Schematics

Complete electrical design for the ESP32 Emu Turbo handheld console.

:::info Source files
The KiCad 9.0 project files are in [`hardware/kicad/`](https://github.com/pjonny/esp32-emu-turbo/tree/main/hardware/kicad). Open with [KiCad 9.0+](https://www.kicad.org/).

To export the schematic as SVG:
```bash
make render-schematics
```
:::

## System Block Diagram

```
                         ┌──────────────────┐
                         │                  │
    USB-C ──────────────>│   IP5306 Module  │──── 5V rail
                         │  (charge+boost)  │
                         └────────┬─────────┘
                                  │
                          ┌───────┴───────┐
                          │               │
                    ┌─────┴─────┐   ┌─────┴──────┐
                    │ LiPo Batt │   │  AMS1117   │
                    │ 3.7V      │   │ 5V -> 3.3V │
                    │ 5000 mAh  │   └─────┬──────┘
                    │ (105080)  │         │
                    └───────────┘         │ 3.3V
                                          │
                              ┌───────────┴───────────┐
                              │                       │
                              │   ESP32-S3-WROOM-1    │
                              │   N16R8               │
                              │   (16MB Flash, 8MB    │
                              │    Octal PSRAM)       │
                              │                       │
                              └──┬──┬──┬──┬──┬──┬──┬──┘
                                 │  │  │  │  │  │  │
                    ┌────────────┘  │  │  │  │  │  └──────────┐
                    │               │  │  │  │  │             │
              ┌─────┴─────┐  ┌─────┴──┘  │  └──┴─────┐  ┌────┴────┐
              │ Display   │  │ SD Card│  │  │ Audio  │  │ Buttons │
              │ ST7796S   │  │ Module │  │  │ I2S -> │  │ 12x     │
              │ 4.0"      │  │ SPI    │  │  │PAM8403 │  │ tact sw │
              │ 8080 par  │  └────────┘  │  │Speaker │  │ + L/R   │
              └───────────┘              │  └────────┘  └─────────┘
                                         │
                                   ┌─────┴─────┐
                                   │ Joystick  │
                                   │ PSP-style │
                                   │ (optional)│
                                   └───────────┘
```

## Power Supply Circuit

### Design

```
USB-C ──> [5.1kΩ CC1] ──┐
          [5.1kΩ CC2] ──┤
                        ├──> IP5306 Module ──> 5V OUT
                        │         │
                        │    [LiPo 3.7V 5000mAh]
                        │
                        └──> [C1 10µF] ──> AMS1117-3.3 ──> [C2 22µF] ──> 3.3V
                                                │
                                               GND
```

| Component | Value | Purpose |
|---|---|---|
| R1, R2 | 5.1 kΩ | USB-C CC pull-down (UFP identification) |
| C1 | 10 µF | AMS1117 input decoupling |
| C2 | 22 µF | AMS1117 output stability (tantalum recommended) |
| C3, C4 | 100 nF | ESP32-S3 VDD decoupling (place near pins) |

### Power Budget

| Consumer | Typical Current | Peak Current |
|---|---|---|
| ESP32-S3 (dual-core active) | 150 mA | 350 mA |
| ST7796S display + backlight | 80 mA | 120 mA |
| PAM8403 + speaker | 20 mA | 100 mA |
| SD card (read) | 30 mA | 100 mA |
| Misc (pull-ups, LEDs) | 10 mA | 20 mA |
| **Total** | **~290 mA** | **~690 mA** |

**Battery life estimate:** 5000 mAh / 290 mA ≈ **17 hours** typical

## Display Interface

8-bit 8080 parallel connection to ST7796S module:

```
ESP32-S3                    ST7796S Module
────────                    ──────────────
GPIO4  ──────────────────── D0
GPIO5  ──────────────────── D1
GPIO6  ──────────────────── D2
GPIO7  ──────────────────── D3
GPIO8  ──────────────────── D4
GPIO9  ──────────────────── D5
GPIO10 ──────────────────── D6
GPIO11 ──────────────────── D7
GPIO12 ──────────────────── CS
GPIO13 ──────────────────── RST
GPIO14 ──────────────────── DC/RS
GPIO46 ──────────────────── WR
GPIO3  ──────────────────── RD
GPIO45 ──────────────────── BL (backlight)
3.3V   ──────────────────── VCC
GND    ──────────────────── GND
```

## Audio Circuit

```
ESP32-S3                  PAM8403 Module         Speaker
────────                  ──────────────         ───────
GPIO15 (BCLK) ──┐
GPIO16 (LRCK) ──┼──> I2S DAC ──> AUDIO_IN ──┐
GPIO17 (DOUT) ──┘                            ├──> SPK+ ──> [+] LS1 28mm
                              [Vol 10kΩ]     │           8Ω 0.5W
5V ──────────────────────────> VCC           └──> SPK- ──> [-]
GND ─────────────────────────> GND
```

:::note I2S DAC
The PAM8403 module accepts analog audio input. An external I2S DAC (MAX98357A or PCM5102 breakout) converts the digital I2S signal to analog before the amplifier. Alternatively, the ESP32-S3 internal DAC can be used for a simpler (lower quality) setup.
:::

## Input Section

All 12 buttons use the same circuit: active-low with pull-up resistor and debounce capacitor.

```
3.3V ──[10kΩ]──┬── GPIO_x
               │
              [SW] (tact switch 6x6mm)
               │
              GND
```

Each button GPIO also has a 100 nF capacitor to GND for hardware debounce.

### Button Matrix

| Group | Buttons | GPIOs |
|---|---|---|
| D-pad | UP, DOWN, LEFT, RIGHT | GPIO40, 41, 42, 1 |
| Face | A, B, X, Y | GPIO2, 48, 47, 21 |
| System | START, SELECT | GPIO18, 0 |
| Shoulder | L, R | GPIO35, 19 |

## SD Card SPI Interface

```
ESP32-S3                  SD Card Module
────────                  ──────────────
GPIO36 ──────────────────> MOSI
GPIO37 <────────────────── MISO
GPIO38 ──────────────────> CLK
GPIO39 ──────────────────> CS
3.3V   ──────────────────> VCC
GND    ──────────────────> GND
```

The SD card module has a built-in level shifter, so 3.3V logic is safe.

## Reset Circuit

```
3.3V ──[R3 10kΩ]──┬── EN (pin 3)
                  │
                [C3 100nF]
                  │
                 GND
```

The RC circuit on the EN pin ensures a clean power-on reset. The time constant (10kΩ × 100nF = 1ms) provides sufficient delay for the internal voltage regulator to stabilize.
