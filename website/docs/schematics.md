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
    <p>ILI9488 8080 parallel</p>
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
  <a href="#sheet-7--usb-data" className="sheet-card">
    <h4>7. USB Data</h4>
    <p>Native USB (flash + debug)</p>
  </a>
</div>

<a className="pdf-download" href="/img/schematics/esp32-emu-turbo-schematics.pdf" target="_blank">Download all sheets (PDF, 7 pages)</a>

:::info Source files
KiCad 10 project: [`hardware/kicad/`](https://github.com/pjcau/esp32-emu-turbo/tree/main/hardware/kicad)

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
              │ Display   │  │ SD Card│  │  │ SPI    │  │ Controls│
              │ ILI9488   │  │ SPI    │  │  │(coproc)│  │ 12 btns │
              │ 8080 ‖    │  └────────┘  │  └───┬────┘  └─────────┘
              └───────────┘              │      │
                                   ┌─────┴──┐  ┌┴─────────────┐
                                   │USB Data│  │ESP32-S3-MINI │
                                   │(D-/D+) │  │  -1 (v2)     │
                                   └────────┘  │  I2S → Audio │
                                               └──────────────┘
```

---

## Sheet 1 — Power Supply

USB-C input with CC pull-downs, IP5306 charge-and-play module, AMS1117-3.3 voltage regulator.

<div className="schematic-container">

![Power Supply Schematic](/img/schematics/01-power-supply.svg)

</div>

<a className="pdf-download" href="/img/schematics/01-power-supply.pdf" target="_blank">PDF</a>

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| J1 | USB-C connector | — | 5V power input | [PDF](/datasheets/J1_USB-C-16pin_C2765186.pdf) |
| J3 | JST PH 2-pin connector | — | LiPo battery connector | [PDF](/datasheets/J3_JST-PH-2pin_C173752.pdf) |
| R1, R2 | Resistor | 5.1 kΩ | CC1/CC2 pull-down (UFP identification) | [PDF](/datasheets/R1-R2_5.1k-0805_C27834.pdf) |
| R16 | Resistor | 100 kΩ | IP5306 KEY pin pull-down | [PDF](/datasheets/R16_100k-0805_C149504.pdf) |
| R17 | Resistor | 1 kΩ | LED1 current limiting | [PDF](/datasheets/R17-R18_1k-0805_C17513.pdf) |
| R18 | Resistor | 1 kΩ | LED2 current limiting | [PDF](/datasheets/R17-R18_1k-0805_C17513.pdf) |
| U2 | IP5306 module | — | LiPo charger + 5V boost (charge-and-play) | [PDF](/datasheets/U2_IP5306_C181692.pdf) |
| BT1 | Battery | LiPo 3.7V 5000mAh | 105080 cell | — |
| U3 | LDO regulator | AMS1117-3.3 | 5V to 3.3V, 800mA max | [PDF](/datasheets/U3_AMS1117-3.3_C6186.pdf) |
| L1 | Inductor | 1 µH 4.5A | IP5306 boost inductor | [PDF](/datasheets/L1_1uH-Inductor_C280579.pdf) |
| LED1 | Red LED | 0805 | Charging indicator (IP5306) | [PDF](/datasheets/LED1_Red-LED-0805_C84256.pdf) |
| LED2 | Green LED | 0805 | Fully charged indicator (IP5306) | [PDF](/datasheets/LED2_Green-LED-0805_C19171391.pdf) |
| SW_PWR | Slide switch | SS-12D00G3 | Power on/off | [PDF](/datasheets/SW_PWR_Slide-Switch_C431540.pdf) |
| C1 | Capacitor | 10 µF | LDO input decoupling | [PDF](/datasheets/C1-C18_10uF-0805_C15850.pdf) |
| C2 | Capacitor | 22 µF | LDO output stability | [PDF](/datasheets/C2-C19_22uF-1206_C12891.pdf) |
| C17, C18 | Capacitor | 10 µF | IP5306/rail decoupling | [PDF](/datasheets/C1-C18_10uF-0805_C15850.pdf) |
| C19 | Capacitor | 22 µF | Bulk capacitor | [PDF](/datasheets/C2-C19_22uF-1206_C12891.pdf) |

### Power Budget

| Consumer | Typical | Peak |
|----------|---------|------|
| ESP32-S3 (dual-core active) | 150 mA | 350 mA |
| ILI9488 display + backlight | 80 mA | 120 mA |
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

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| U1 | MCU module | ESP32-S3-WROOM-1 N16R8 | 16MB Flash, 8MB PSRAM | [PDF](/datasheets/U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf) |
| R3 | Resistor | 10 kΩ | EN pull-up (keep-alive) | [PDF](/datasheets/R3-R15_10k-0805_C17414.pdf) |
| C3 | Capacitor | 100 nF | EN reset delay (RC = 1ms) | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| C4 | Capacitor | 100 nF | 3V3 decoupling | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| SW_RST | Tact switch | — | EN reset (pulls EN low) | [PDF](/datasheets/SW1-SW13_Tact-Switch_C318884.pdf) |
| SW_BOOT | Tact switch | — | Boot mode (pulls GPIO0 low) | [PDF](/datasheets/SW1-SW13_Tact-Switch_C318884.pdf) |

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
| **Shoulder** | 35, 43 | L, R | GPIO |
| **USB Data** | 19, 20 | USB_D-, USB_D+ | USB |

:::info Reserved GPIOs
GPIO26–32 are used internally by the PSRAM. GPIO19/20 are the native USB D-/D+ pins (firmware flash + debug console via USB CDC).
:::

---

## Sheet 3 — Display

ILI9488 4.0" 320×480 bare panel with 40-pin FPC, 8-bit 8080 parallel interface — mandatory for SNES emulation speed. FPC pin mapping per ILI9488 panel datasheet: pins 9-12=CS/DC/WR/RD, pin 15=RESET, pins 17-24=DB0-DB7, pin 33=LED-A(backlight), pins 6-7=VDDI/VDDA(+3V3), pins 38-39=IM0/IM1(+3V3), pin 40=IM2(GND). **Note:** on the PCB, display Pin N maps to connector Pad (41−N) due to the landscape FPC pass-through (see [PCB docs](pcb.md#fpc-slot--pin-reversal)).

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| J4 | FPC connector | 40-pin 0.5mm bottom contact | Display ribbon cable | [PDF](/datasheets/J4_FPC-40pin-0.5mm_C2856812.pdf) |

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

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| U5 | Amplifier | PAM8403 | Filterless Class-D, 3W/ch | [PDF](/datasheets/U5_PAM8403_C5122557.pdf) |
| C21 | Capacitor | 100 nF (C49678) | VREF bypass capacitor | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| C22 | Capacitor | 0.47 µF (C1525) | DC-blocking cap on audio input | — |
| C23, C24, C25 | Capacitor | 1 µF (C15849) | VDD and PVDD decoupling caps | — |
| R20, R21 | Resistor | 20 kΩ (C4184) | Bias resistors on INL/INR to GND | — |
| LS1 | Speaker | 28mm 8Ω 0.5W | Mono output | — |

:::note
The PAM8403 is powered from the +5V rail for maximum headroom. Only one channel is used for mono audio. ESP32-S3 I2S with DMA provides low-CPU-overhead audio streaming. The passive components (C21–C25, R20–R21) follow the PAM8403 datasheet application circuit for proper biasing, DC blocking, and power supply decoupling.
:::

---

## Sheet 5 — SD Card

Micro SD card module via SPI bus for ROM storage (SNES ROMs up to 6MB, FAT32).

<div className="schematic-container">

![SD Card Schematic](/img/schematics/05-sd-card.svg)

</div>

<a className="pdf-download" href="/img/schematics/05-sd-card.pdf" target="_blank">PDF</a>

| Ref | Component | Datasheet |
|-----|-----------|-----------|
| U6 | Micro SD slot (TF-01A) | [PDF](/datasheets/U6_TF-01A_MicroSD_C91145.pdf) |

| Signal | GPIO | Direction |
|--------|------|-----------|
| MOSI | GPIO36 | ESP32 → SD |
| MISO | GPIO37 | SD → ESP32 |
| CLK | GPIO38 | ESP32 → SD |
| CS | GPIO39 | ESP32 → SD |

SPI bus up to 40MHz. GPIO36–39 are grouped for clean routing. The SD module has a built-in level shifter (3.3V safe). On the PCB, the SD card slot VCC and GND pins are connected via vias to the inner power planes (+3V3 and GND) for clean power delivery with minimal trace length.

---

## Sheet 6 — Controls

13 tact switches (SNES layout + MENU) with individual 10kΩ pull-up + 100nF debounce per button. Plus SW_RST (reset) and SW_BOOT (boot mode) on Sheet 2. Tact switch datasheet: [PDF](/datasheets/SW1-SW13_Tact-Switch_C318884.pdf).

<div className="schematic-container">

![Controls Schematic](/img/schematics/06-controls.svg)

</div>

<a className="pdf-download" href="/img/schematics/06-controls.pdf" target="_blank">PDF</a>

### Button Circuit (repeated 13×)

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

| Ref | Component | Value | Purpose |
|-----|-----------|-------|---------|
| R4–R15, R19 | Resistor | 10 kΩ (C17414) | Button pull-ups (12 + MENU) |
| C5–C16, C20 | Capacitor | 100 nF (C49678) | Button debounce (12 + MENU) |

| Group | Buttons | Switches | GPIOs |
|-------|---------|----------|-------|
| D-pad | UP, DOWN, LEFT, RIGHT | SW1–SW4 | 40, 41, 42, 1 |
| Face | A, B, X, Y | SW5–SW8 | 2, 48, 47, 21 |
| System | START, SELECT, MENU | SW9, SW10, SW13 | 18, 0, — |
| Shoulder | L, R | SW11, SW12 | 35, 43 |

---

## Sheet 7 — USB Data

Native USB data lines for firmware flashing and debug console (replaces UART debug).

| Signal | GPIO | Function |
|--------|------|----------|
| USB_D- | GPIO19 | USB data minus (native USB) |
| USB_D+ | GPIO20 | USB data plus (native USB) |

USB-C now carries both **power** (charging via IP5306) and **data** (firmware flash + CDC debug console). This replaces the previous UART debug approach (GPIO43 TX0) with native USB, which is faster and requires no external UART adapter.

:::info Joystick removed
The optional PSP joystick (previously GPIO20/GPIO44) has been removed. The D-pad provides full SNES/NES control. GPIO43 (previously TX0 for UART debug) is now used for BTN_R.
:::

---

## v2 — Sheet 8: Audio Coprocessor (ESP32-S3-MINI-1)

:::info v2 addition
This sheet is only present on the **v2 PCB**. The v1 PCB uses direct I2S from the main ESP32-S3 to the PAM8403 (Sheet 4). In v2, the main ESP32-S3 communicates with the coprocessor via SPI, and the coprocessor drives I2S to the PAM8403.
:::

ESP32-S3-MINI-1-N8 audio coprocessor with SPI slave interface to the main ESP32-S3 and I2S output to the PAM8403 amplifier.

| Ref | Component | Value | Purpose |
|-----|-----------|-------|---------|
| U7 | ESP32-S3-MINI-1-N8 | Module | Audio coprocessor (SPC700 + I2S) |
| C26 | Capacitor | 100 nF | 3V3 decoupling |
| C27 | Capacitor | 100 nF | EN decoupling |

### SPI Bus (Main ESP32-S3 → Coprocessor)

| Signal | Main ESP32-S3 GPIO | MINI-1 GPIO | Direction |
|--------|-------------------|-------------|-----------|
| SPI_CLK | GPIO 15 (was I2S_BCLK) | GPIO 12 | Main → MINI-1 |
| SPI_MOSI | GPIO 16 (was I2S_LRCLK) | GPIO 11 | Main → MINI-1 |
| SPI_MISO | GPIO 17 (was I2S_DOUT) | GPIO 13 | MINI-1 → Main |
| SPI_CS | GPIO 20 (was USB_D+) | GPIO 10 | Main → MINI-1 |

### I2S Bus (Coprocessor → PAM8403)

| Signal | MINI-1 GPIO | Direction |
|--------|-------------|-----------|
| I2S_BCLK | GPIO 15 | MINI-1 → PAM8403 |
| I2S_LRCLK | GPIO 16 | MINI-1 → PAM8403 |
| I2S_DOUT | GPIO 17 | MINI-1 → PAM8403 |

### v2 GPIO Changes vs v1

| Main ESP32-S3 GPIO | v1 Function | v2 Function | Notes |
|---------------------|-------------|-------------|-------|
| GPIO 15 | I2S_BCLK → PAM8403 | SPI_CLK → MINI-1 | Audio path moves to coprocessor |
| GPIO 16 | I2S_LRCLK → PAM8403 | SPI_MOSI → MINI-1 | Audio path moves to coprocessor |
| GPIO 17 | I2S_DOUT → PAM8403 | SPI_MISO ← MINI-1 | Audio path moves to coprocessor |
| GPIO 20 | USB_D+ (native USB) | SPI_CS → MINI-1 | USB D+ reassigned for coprocessor |

:::tip Clean GPIO reuse
The 3 I2S pins freed by moving audio to the coprocessor are reused for SPI communication — no GPIOs wasted. GPIO 20 (USB_D+ in v1) is reassigned to SPI chip select; in v2, USB native data is no longer available (debug via SPI or UART instead).
:::
