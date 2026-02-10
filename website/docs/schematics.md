---
id: schematics
title: Electrical Schematics
sidebar_position: 5
---

# Electrical Schematics

Complete electrical design for the ESP32 Emu Turbo, split into 7 detailed schematic sheets with cross-sheet global labels.

<div className="sheet-grid">
  <a href="#sheet-1--power-supply" className="sheet-card">
    <h4>1. Power Supply</h4>
    <p>USB-C, IP5306, AMS1117, battery</p>
  </a>
  <a href="#sheet-2--mcu-esp32-s3" className="sheet-card">
    <h4>2. MCU</h4>
    <p>ESP32-S3 + 35 GPIO labels</p>
  </a>
  <a href="#sheet-3--display" className="sheet-card">
    <h4>3. Display</h4>
    <p>ST7796S 8080 parallel</p>
  </a>
  <a href="#sheet-4--audio" className="sheet-card">
    <h4>4. Audio</h4>
    <p>PAM8403 + speaker</p>
  </a>
  <a href="#sheet-5--sd-card" className="sheet-card">
    <h4>5. SD Card</h4>
    <p>SPI ROM storage</p>
  </a>
  <a href="#sheet-6--controls" className="sheet-card">
    <h4>6. Controls</h4>
    <p>12 buttons + debounce</p>
  </a>
  <a href="#sheet-7--joystick" className="sheet-card">
    <h4>7. Joystick</h4>
    <p>PSP analog (optional)</p>
  </a>
</div>

<a className="pdf-download" href="/img/schematics/esp32-emu-turbo-schematics.pdf" target="_blank">Download all sheets (PDF, 7 pages)</a>

:::info Source files
KiCad 9.0 project: [`hardware/kicad/`](https://github.com/pjcau/esp32-emu-turbo/tree/main/hardware/kicad)

```bash
make generate-schematic   # Generate 7 .kicad_sch files
make render-schematics    # Export SVG + PDF
```
:::

---

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
                              │   ESP32-S3-WROOM-1    │
                              │   N16R8 (240MHz ×2)   │
                              └──┬──┬──┬──┬──┬──┬──┬──┘
                                 │  │  │  │  │  │  │
                    ┌────────────┘  │  │  │  │  │  └──────────┐
                    │               │  │  │  │  │             │
              ┌─────┴─────┐  ┌─────┴──┘  │  └──┴─────┐  ┌────┴────┐
              │ Display   │  │ SD Card│  │  │ Audio  │  │ Controls│
              │ ST7796S   │  │ SPI    │  │  │PAM8403 │  │ 12 btns │
              │ 8080 ‖    │  └────────┘  │  └────────┘  └─────────┘
              └───────────┘              │
                                   ┌─────┴─────┐
                                   │ Joystick  │
                                   │ (optional)│
                                   └───────────┘
```

---

## Sheet 1 — Power Supply

USB-C input with CC pull-downs, IP5306 charge-and-play module, AMS1117-3.3 voltage regulator.

<div className="schematic-container">

![Power Supply Schematic](/img/schematics/01-power-supply.svg)

</div>

<a className="pdf-download" href="/img/schematics/01-power-supply.pdf" target="_blank">PDF</a>

| Ref | Component | Value | Purpose |
|-----|-----------|-------|---------|
| J1 | USB-C connector | — | 5V power input |
| R1, R2 | Resistor | 5.1 kΩ | CC1/CC2 pull-down (UFP identification) |
| U2 | IP5306 module | — | LiPo charger + 5V boost (charge-and-play) |
| BT1 | Battery | LiPo 3.7V 5000mAh | 105080 cell |
| U3 | LDO regulator | AMS1117-3.3 | 5V to 3.3V, 800mA max |
| C1 | Capacitor | 10 µF | LDO input decoupling |
| C2 | Capacitor | 22 µF tantalum | LDO output stability |

### Power Budget

| Consumer | Typical | Peak |
|----------|---------|------|
| ESP32-S3 (dual-core active) | 150 mA | 350 mA |
| ST7796S display + backlight | 80 mA | 120 mA |
| PAM8403 + speaker | 20 mA | 100 mA |
| SD card (SPI read) | 30 mA | 100 mA |
| Misc (pull-ups, buttons) | 10 mA | 20 mA |
| **Total** | **~290 mA** | **~690 mA** |

**Battery life:** 5000 mAh / 290 mA ≈ **17 hours** typical gameplay

---

## Sheet 2 — MCU (ESP32-S3)

ESP32-S3-WROOM-1 N16R8 with all 35 GPIO connections grouped by function, decoupling capacitors, and EN reset circuit.

<div className="schematic-container">

![MCU Schematic](/img/schematics/02-mcu.svg)

</div>

<a className="pdf-download" href="/img/schematics/02-mcu.pdf" target="_blank">PDF</a>

| Ref | Component | Value | Purpose |
|-----|-----------|-------|---------|
| U1 | MCU module | ESP32-S3-WROOM-1 N16R8 | 16MB Flash, 8MB PSRAM |
| R3 | Resistor | 10 kΩ | EN pull-up (keep-alive) |
| C3 | Capacitor | 100 nF | EN reset delay (RC = 1ms) |
| C4 | Capacitor | 100 nF | 3V3 decoupling |

### GPIO Assignment

| Function | GPIOs | Signals | Bus |
|----------|-------|---------|-----|
| **Display** | 4–11 | D0–D7 | 8080 data |
| | 12, 13, 14, 46, 3, 45 | CS, RST, DC, WR, RD, BL | 8080 control |
| **Audio** | 15, 16, 17 | BCLK, LRCK, DOUT | I2S |
| **SD Card** | 36, 37, 38, 39 | MOSI, MISO, CLK, CS | SPI |
| **D-pad** | 40, 41, 42, 1 | UP, DOWN, LEFT, RIGHT | GPIO |
| **Face** | 2, 48, 47, 21 | A, B, X, Y | GPIO |
| **System** | 18, 0 | START, SELECT | GPIO |
| **Shoulder** | 35, 19 | L, R | GPIO |
| **Joystick** | 20, 44 | JOY_X, JOY_Y | ADC |

:::info Reserved GPIOs
GPIO26–32 are used internally by the PSRAM. GPIO43 (TX0) is reserved for debug UART.
:::

---

## Sheet 3 — Display

ST7796S 4.0" 320×480 display with 8-bit 8080 parallel interface — mandatory for SNES emulation speed.

<div className="schematic-container">

![Display Schematic](/img/schematics/03-display.svg)

</div>

<a className="pdf-download" href="/img/schematics/03-display.pdf" target="_blank">PDF</a>

The 8080 parallel mode writes a full pixel (16-bit RGB565) in 2 bus cycles. SPI would need 16 clock cycles per pixel, making it too slow for 60fps full-screen SNES rendering. GPIO4–11 form a contiguous 8-bit data bus for efficient register-level DMA.

---

## Sheet 4 — Audio

I2S output from ESP32-S3 to PAM8403 Class-D amplifier driving a 28mm 8Ω speaker.

<div className="schematic-container">

![Audio Schematic](/img/schematics/04-audio.svg)

</div>

<a className="pdf-download" href="/img/schematics/04-audio.pdf" target="_blank">PDF</a>

| Ref | Component | Value | Purpose |
|-----|-----------|-------|---------|
| U5 | Amplifier | PAM8403 | Filterless Class-D, 3W/ch |
| LS1 | Speaker | 28mm 8Ω 0.5W | Mono output |

:::note
The PAM8403 is powered from the +5V rail for maximum headroom. Only one channel is used for mono audio. ESP32-S3 I2S with DMA provides low-CPU-overhead audio streaming.
:::

---

## Sheet 5 — SD Card

Micro SD card module via SPI bus for ROM storage (SNES ROMs up to 6MB, FAT32).

<div className="schematic-container">

![SD Card Schematic](/img/schematics/05-sd-card.svg)

</div>

<a className="pdf-download" href="/img/schematics/05-sd-card.pdf" target="_blank">PDF</a>

| Signal | GPIO | Direction |
|--------|------|-----------|
| MOSI | GPIO36 | ESP32 → SD |
| MISO | GPIO37 | SD → ESP32 |
| CLK | GPIO38 | ESP32 → SD |
| CS | GPIO39 | ESP32 → SD |

SPI bus up to 40MHz. GPIO36–39 are grouped for clean routing. The SD module has a built-in level shifter (3.3V safe).

---

## Sheet 6 — Controls

12 tact switches (SNES layout) with individual 10kΩ pull-up + 100nF debounce per button.

<div className="schematic-container">

![Controls Schematic](/img/schematics/06-controls.svg)

</div>

<a className="pdf-download" href="/img/schematics/06-controls.pdf" target="_blank">PDF</a>

### Button Circuit (repeated 12×)

```
+3V3 ──[10kΩ R]──┬──── GPIO_x (global label)
                  │
                [100nF C]
                  │
                 GND

     [SW tact]──┤
                └── GND
```

**Idle** = HIGH (3.3V via pull-up), **Pressed** = LOW (grounded through switch).

| Group | Buttons | GPIOs |
|-------|---------|-------|
| D-pad | UP, DOWN, LEFT, RIGHT | 40, 41, 42, 1 |
| Face | A, B, X, Y | 2, 48, 47, 21 |
| System | START, SELECT | 18, 0 |
| Shoulder | L, R | 35, 19 |

---

## Sheet 7 — Joystick

PSP-style analog joystick (optional) with 2 ADC channels.

<div className="schematic-container">

![Joystick Schematic](/img/schematics/07-joystick.svg)

</div>

<a className="pdf-download" href="/img/schematics/07-joystick.pdf" target="_blank">PDF</a>

| Signal | GPIO | ADC Channel | Range |
|--------|------|-------------|-------|
| X axis | GPIO20 | ADC2_CH9 | 0–3.3V, center ~1.65V |
| Y axis | GPIO44 (RX0) | ADC2_CH7 | 0–3.3V, center ~1.65V |

The joystick is optional — the D-pad provides full SNES control. 12-bit ADC resolution (4096 steps).

:::caution
GPIO44 shares the RX0 UART pin. When the joystick is connected, debug UART input is unavailable (TX0 on GPIO43 still works for output).
:::
