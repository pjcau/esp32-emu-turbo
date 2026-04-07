---
id: components
title: Bill of Materials (BOM)
sidebar_position: 4
---

# Bill of Materials (BOM) with AliExpress Links

All components selected for the prototype, with direct purchase links.

---

## MCU — ESP32-S3

| Option | Flash | PSRAM | USB | Price | Link |
|---|---|---|---|---|---|
| **ESP32-S3 DevKitC-1 N16R8 (clone)** | 16 MB | 8 MB Octal | Dual USB-C | **$5.50-$7.00** | [AliExpress](https://www.aliexpress.com/w/wholesale-ESP32-S3-N16R8-development-board.html) |
| WeAct ESP32-S3-A N16R8 | 16 MB | 8 MB Octal | Dual USB-C | $5.50-$7.50 | [AliExpress (WeAct Store)](https://weactstudio.aliexpress.com/store/1101545918) |
| Waveshare ESP32-S3-DEV-KIT N16R8 | 16 MB | 8 MB Octal | USB-C | $10.99-$12.99 | [Waveshare](https://www.waveshare.com/esp32-s3-dev-kit-n8r8.htm) |

**Recommended:** ESP32-S3 DevKitC-1 N16R8 generic (~$6.00)

---

## Display

### Chosen: ILI9488 3.95" Bare LCD Panel (for custom PCB)

| Spec | Value |
|------|-------|
| **Size** | 3.95" |
| **Resolution** | 320(RGB) × 480 |
| **Controller** | ILI9488 |
| **Touch** | Resistive (SPI) — not connected, touch not used |
| **Connector** | 40-pin FPC, 0.5mm pitch |
| **Interface** | MCU 8/16-bit parallel + SPI |
| **Backlight** | White LED, 3.3V |
| **Display colors** | 262K |
| **Price** | ~$3.95 |
| **Link** | [AliExpress](https://it.aliexpress.com/item/1005009422879126.html) |

:::tip Why bare panel instead of module?
The bare LCD panel connects directly to the PCB via a **40-pin FPC ribbon** — no breakout PCB, no pin headers. This is how commercial handheld consoles are built: compact, thin, and plug-in. The FPC ribbon slides into the J4 connector on our PCB and locks with the latch. **Zero soldering required.**
:::

:::info ILI9488 vs ST7796S — driver notes
Both controllers are equivalent for 8-bit 8080 parallel with RGB565 (~20 MB/s). Key differences:
- **ESP-IDF**: use community component [`esp_lcd_ili9488`](https://components.espressif.com/components/atanisoft/esp_lcd_ili9488) (ST7796S has official Espressif component)
- **LovyanGFX / TFT_eSPI**: both controllers fully supported
- **SPI limitation**: ILI9488 does NOT support RGB565 over SPI (only RGB666/888). This does not affect us since we use **parallel 8080**.
- **Init sequence**: slightly different command set, but handled by the driver library
:::

### Display Orientation (landscape for gaming)

```
Portrait (native)          Landscape (gaming mode)
┌──────────┐               ┌─────────────────────┐
│          │               │                     │
│  320px   │    rotate     │      480px          │
│    ×     │   -------->   │       ×             │
│  480px   │    90° CW     │      320px          │
│          │               │                     │
│  FPC ══  │               │              FPC ══ │
└──────────┘               └─────────────────────┘
```

### FPC 40-Pin Pinout (ILI9488 panel datasheet)

![ILI9488 FPC 40-pin pinout from datasheet](/img/ili9488-fpc40-pinout.png)

![ILI9488 datasheet specifications](/img/ili9488-datasheet-specs.png)

| Pin | Symbol | Direction | Description | Connection |
|-----|--------|-----------|-------------|------------|
| 1 | XL | — | Touch panel logical foot | **NC** |
| 2 | YU | — | Touch panel logical foot | **NC** |
| 3 | XR | — | Touch panel logical foot | **NC** |
| 4 | YD | — | Touch panel logical foot | **NC** |
| 5 | GND | — | Ground | GND |
| 6 | VDDI | — | I/O power supply (1.8–3.3V) | **+3V3** |
| 7 | VDDA | — | Analog/digital power (2.8–3.3V) | **+3V3** |
| 8 | TE | Output | Tearing effect (vsync) | NC |
| 9 | CS | Input | Chip select (active low) | GPIO12 |
| 10 | DC/RS | Input | Data/Command select | GPIO14 |
| 11 | WR | Input | Write strobe (8080 mode) | GPIO46 |
| 12 | RD | Input | Read strobe (8080 mode) | **+3V3** (tied HIGH) |
| 13 | SPI SDI | Input | SPI data in | NC (parallel mode) |
| 14 | SPI SDO | Output | SPI data out | NC (parallel mode) |
| 15 | RESET | Input | Reset (active low) | GPIO13 |
| 16 | GND | — | Ground | GND |
| 17-24 | DB0-DB7 | I/O | 8-bit parallel data bus | GPIO4-11 |
| 25-32 | DB8-DB15 | I/O | 16-bit extension | NC (8-bit mode) |
| 33 | LED-A | — | Backlight anode (2.9–3.3V typ 3.1V) | **+3V3** (via resistor, always-on) |
| 34-36 | LED-K | — | Backlight cathode (8 chip white LED) | **GND** |
| 37 | GND | — | Ground | GND |
| 38 | IM0 | Input | Interface mode select | **+3V3** (HIGH) |
| 39 | IM1 | Input | Interface mode select | **+3V3** (HIGH) |
| 40 | IM2 | Input | Interface mode select | **GND** (LOW) |

:::info Interface Mode Selection (IM2:IM1:IM0)
| IM2 | IM1 | IM0 | Mode | Data Pins |
|-----|-----|-----|------|-----------|
| 0 | 1 | 0 | 8080 16-bit parallel | DB15-DB0 |
| **0** | **1** | **1** | **8080 8-bit parallel** | **DB7-DB0** |
| 1 | 0 | 1 | 3-line 9-bit SPI | SDA in/out |
| 1 | 1 | 1 | 4-line 8-bit SPI | SDA in/out |

Our design uses **8080 8-bit parallel** (IM2=0, IM1=1, IM0=1): IM0 and IM1 pulled HIGH to +3V3, IM2 pulled LOW to GND.
:::

:::warning Pinout verified from actual panel datasheet
This pinout is from the actual ILI9488 4.0" panel datasheet (see images above). It differs significantly from generic/typical pinouts found online. **Do NOT use generic ILI9488 pinout tables** — always refer to this datasheet.
:::

:::info FPC Pin Reversal on PCB
When the display is mounted in landscape (CCW rotation), Pin 1 is at the south end of the FPC tail. The ribbon passes straight through the PCB slot to J4 on the bottom side without twisting, so **display Pin N contacts connector Pad (41−N)**. The PCB traces are routed accordingly — e.g., display Pin 17 (DB0/GPIO4) connects to J4 Pad 24. See [PCB FPC Slot](pcb.md#fpc-slot--pin-reversal) for details.
:::

### Alternative Display Options

| Option | Size | Resolution | Controller | Interface | Price | Notes |
|---|---|---|---|---|---|---|
| **ST7796 4.0" bare panel + GT911 touch** | 4.0" | 320x480 | ST7796S | 8/16-bit parallel | ~$8-12 | [AliExpress](https://it.aliexpress.com/item/1005010555977696.html) — larger screen, official ESP-IDF driver |
| ST7796S 4.0" module + PCB | 4.0" | 320x480 | ST7796S | 8/16-bit parallel | ~$12-19 | Prototyping only (pin headers, no FPC) |
| ST7796S 3.5" IPS SPI | 3.5" | 320x480 | ST7796S | SPI | $8-$12 | Prototyping only |

---

## Power Supply

### LiPo Battery

| Option | Capacity | Dimensions | Weight | Price | Link |
|---|---|---|---|---|---|
| **LiPo 105080 5000mAh** | 5000mAh | 50x80x10mm | ~80g | **~$5-8** | [AliExpress](https://www.aliexpress.com/w/wholesale-105080-5000mAh-lipo-battery.html) |
| LiPo 104060 3000mAh | 3000mAh | 40x60x10mm | ~50g | $6.70 | [AliExpress](https://www.aliexpress.com/item/32921120300.html) |
| LiPo 103450 2000mAh | 2000mAh | 34x50x10mm | ~35g | $3.50 | [AliExpress](https://www.aliexpress.com/item/4001034573030.html) |

### USB-C Charging Module

| Option | Features | Price | Link |
|---|---|---|---|
| **IP5306 USB-C** | Charge+boost 5V/2.4A, charge-and-play | **$1.59** | [AliExpress](https://www.aliexpress.com/item/4001053901268.html) |
| TP4056 USB-C | Charge only 1A, no boost (needs external regulator) | $0.25 | [AliExpress](https://www.aliexpress.com/item/32670803042.html) |

### Voltage Regulator

| Option | Specification | Price | Link |
|---|---|---|---|
| **AMS1117-3.3V** | LDO 5V->3.3V, 800mA | **$0.24** | [AliExpress](https://www.aliexpress.com/item/32886395040.html) |

**Recommended:** LiPo 5000mAh + IP5306 + AMS1117 (~$7-10)

:::note Estimated battery life with 5000mAh
At an average draw of ~300mA (ESP32-S3 + display + audio), the 5000mAh battery provides approximately **14-16 hours** of continuous gameplay.
:::

:::info Power architecture
```
USB-C -> [IP5306] -> 5V -> [AMS1117] -> 3.3V -> ESP32-S3
            |
       [LiPo Battery]
```
The IP5306 manages battery charge/discharge and provides stable 5V output. The AMS1117 steps it down to 3.3V for the ESP32.
:::

---

## Controls / Input

| Component | Specification | Price | Link |
|---|---|---|---|
| **Tact switch 6x6mm (20pcs)** | Momentary push button, for D-pad/A/B/X/Y/Start/Select/L/R (12 buttons) | **$1.04** | [AliExpress](https://www.aliexpress.com/item/33024158924.html) |
| Rubber pads GBA-style | Conductive silicone, better feel | $0.27 | [AliExpress](https://www.aliexpress.com/item/32800611102.html) |
| Rubber pads GBA full set | D-pad + A/B + Start/Select + L/R | $1.05 | [AliExpress](https://www.aliexpress.com/item/33007129317.html) |
| ~~PSP Joystick~~ (removed) | ~~2-axis analog, PSP 2000/3000~~ | ~~$2.11~~ | Removed in v2 — GPIOs reassigned to USB data and BTN_R |

---

## Audio

| Component | Specification | Price | Link |
|---|---|---|---|
| **Speaker 28mm 8ohm 0.5W** | Mini speaker (5pc pack $4.05) | **$0.81/pc** | [AliExpress](https://www.aliexpress.com/item/32826761277.html) |
| **PAM8403 amplifier** | 2ch 3W, with volume pot | **$0.44** | [AliExpress](https://www.aliexpress.com/item/32977330620.html) |

---

## Storage

| Component | Specification | Price | Link |
|---|---|---|---|
| **SD Card module SPI** | Micro SD reader, built-in level shifter | **$0.45** | [AliExpress](https://www.aliexpress.com/item/1865616455.html) |
| **Micro SD 32GB** | Class 10 / UHS-I (Kingston or Samsung) | **$3.50** | [AliExpress](https://www.aliexpress.com/w/wholesale-32gb-micro-sd-card-class10.html) |

---

## Prototyping Supplies

| Component | Specification | Price | Link |
|---|---|---|---|
| Breadboard 830 points | For phase 2 prototype | ~$2.00 | [AliExpress](https://www.aliexpress.com/w/wholesale-breadboard-830.html) |
| Jumper wires set | M-M, M-F, F-F | ~$2.00 | [AliExpress](https://www.aliexpress.com/w/wholesale-jumper-wire-dupont.html) |
| Resistor/capacitor kit | Assorted values | ~$2.00 | [AliExpress](https://www.aliexpress.com/w/wholesale-resistor-assortment-kit.html) |

---

## Budget Summary

### Recommended Configuration (SNES Primary)

| Category | Component | Price |
|---|---|---|
| MCU | ESP32-S3 N16R8 DevKitC-1 | $6.00 |
| Display | ILI9488 3.95" 8-bit parallel (bare panel) | $3.95 |
| Battery | LiPo 105080 5000mAh | $6.50 |
| Charging | IP5306 USB-C | $1.59 |
| Regulator | AMS1117-3.3V | $0.24 |
| Controls | Tact switch 20pcs (12 buttons: D-pad, A, B, X, Y, Start, Select, L, R) | $1.04 |
| Extra controls | Rubber pads | $1.05 |
| Audio | Speaker + PAM8403 | $1.25 |
| Storage | SD module + 32GB card | $3.95 |
| Misc | Breadboard, jumpers, resistors | $6.00 |
| **TOTAL** | | **$32.90** |

### Button Layout

```
    [L]                         [R]

                            [X]
  [D-pad]              [Y]     [A]
  up/down/                  [B]
  left/right

        [Select] [Start]
```

12 buttons total: **D-pad** (4), **A, B, X, Y**, **Start, Select**, **L, R**

:::tip Recommended budget
Plan for **~$55** to have margin for spares and unexpected needs.
:::

:::note Shipping
Most AliExpress sellers offer **free shipping**. Delivery time: **2-4 weeks** (standard).
:::

---

## JLCPCB PCB Assembly — LCSC Part Numbers

For the custom PCB version (see [PCB Design](pcb.md)), all SMT components are sourced from LCSC for JLCPCB assembly.

| Ref | Component | Package | LCSC | Class | Datasheet |
|-----|-----------|---------|------|-------|-----------|
| U1 | ESP32-S3-WROOM-1-N16R8 | Module | C2913202 | Extended | [PDF](/datasheets/U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf) |
| U2 | IP5306 charger+boost IC | eSOP-8 | C181692 | Extended | [PDF](/datasheets/U2_IP5306_C181692.pdf) |
| U3 | AMS1117-3.3 LDO | SOT-223 | C6186 | Basic | [PDF](/datasheets/U3_AMS1117-3.3_C6186.pdf) |
| U5 | PAM8403 audio amplifier | SOP-16 | C5122557 | Extended | [PDF](/datasheets/U5_PAM8403_C5122557.pdf) |
| J1 | USB-C 16-pin connector | SMT | C2765186 | Extended | [PDF](/datasheets/J1_USB-C-16pin_C2765186.pdf) |
| U6 | Micro SD slot (TF-01A) | SMT | C91145 | Extended | [PDF](/datasheets/U6_TF-01A_MicroSD_C91145.pdf) |
| J4 | FPC 40-pin 0.5mm (display) | SMT | C2856812 | Extended | [PDF](/datasheets/J4_FPC-40pin-0.5mm_C2856812.pdf) |
| J3 | JST PH 2-pin SMD (battery) | SMD | C265082 | Extended | [PDF](/datasheets/J3_JST-PH-2pin_C265082.pdf) |
| L1 | 1µH inductor 4.5A | SMD 4×4 | C280579 | Extended | [PDF](/datasheets/L1_1uH-Inductor_C280579.pdf) |
| SW1–SW13,SW_RST,SW_BOOT | SMT tact switch 5.1×5.1mm | SMT | C318884 | Extended | [PDF](/datasheets/SW1-SW13_Tact-Switch_C318884.pdf) |
| SW_PWR | Slide switch SS-12D00G3 | SMT | C431540 | Extended | [PDF](/datasheets/SW_PWR_Slide-Switch_C431540.pdf) |
| LED1 | Red LED 0805 | 0805 | C84256 | Basic | [PDF](/datasheets/LED1_Red-LED-0805_C84256.pdf) |
| LED2 | Green LED 0805 | 0805 | C19171391 | Basic | [PDF](/datasheets/LED2_Green-LED-0805_C19171391.pdf) |
| R1–R2 | 5.1kΩ 0805 | 0805 | C27834 | Basic | [PDF](/datasheets/R1-R2_5.1k-0805_C27834.pdf) |
| R3–R15,R19 | 10kΩ 0805 | 0805 | C17414 | Basic | [PDF](/datasheets/R3-R15_10k-0805_C17414.pdf) |
| R16 | 100kΩ 0805 | 0805 | C149504 | Basic | [PDF](/datasheets/R16_100k-0805_C149504.pdf) |
| R17,R18 | 1kΩ 0805 | 0805 | C17513 | Basic | [PDF](/datasheets/R17-R18_1k-0805_C17513.pdf) |
| R20,R21 | 20kΩ bias (PAM8403 INL/INR) | 0805 | C4184 | Basic | — |
| C3–C16,C20,C21,C26 | 100nF 0805 | 0805 | C49678 | Basic | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| C1,C17,C18,C27 | 10µF 0805 | 0805 | C15850 | Basic | [PDF](/datasheets/C1-C18_10uF-0805_C15850.pdf) |
| C2,C19 | 22µF 1206 | 1206 | C12891 | Basic | [PDF](/datasheets/C2-C19_22uF-1206_C12891.pdf) |
| C22 | 0.47µF DC-blocking (PAM8403 input) | 0805 | C13967 | Basic | — |
| C23,C24,C25 | 1µF decoupling (PAM8403 VDD/PVDD) | 0805 | C28323 | Basic | — |

**Estimated PCB cost:** ~$90 for 5 boards (~$18/board) including fabrication, components, and assembly.

### v2 Additional Components (Audio Coprocessor)

The v2 PCB adds an ESP32-S3-MINI-1-N8 as a dedicated audio coprocessor (see [Phase 5 — Software Architecture](software.md#phase-5--v2-hardware-audio-coprocessor)):

| Ref | Component | Package | LCSC | Class | Unit cost |
|-----|-----------|---------|------|-------|-----------|
| U7 | ESP32-S3-MINI-1-N8 | Module (15.4×20.5mm) | C2913206 | Extended | $3.25 |
| C26,C27 | 100nF 0805 (decoupling) | 0805 | C49678 | Basic | $0.01 |

**v2 BOM delta:** +$3.27 per unit. No external crystal, flash, or extra passives needed — the module integrates everything.

**v2 estimated PCB cost:** ~$106 for 5 boards (~$21/board).

---

## PCB Version — What to Buy Separately

When ordering the custom PCB from JLCPCB, the following components are **NOT included** in the assembly and must be purchased from AliExpress:

| Component | Ref | Price | Connection to PCB | Solder? |
|-----------|-----|-------|-------------------|---------|
| **ILI9488 3.95" bare LCD panel** (40P FPC 0.5mm, resistive touch NC) | U4 | ~$3.95 | FPC ribbon → J4 connector (slide + latch) | No |
| **LiPo 105080 5000mAh battery** | BT1 | ~$6-8 | JST PH plug → J3 connector | No |
| **Speaker 28mm 8Ω** | SPK1 | ~$0.80 | 2 wires → solder pads | Yes (easy) |
| ~~PSP joystick~~ (removed) | ~~J2~~ | — | Removed in v2 — GPIOs reassigned to USB data and BTN_R | — |
| | | **~$17-23** | | |

:::tip
The display and battery are **plug-in** — no soldering skills required. Only the speaker (2 wires) needs soldering.
:::

:::warning Display purchase — important
Buy the **bare LCD panel** (no PCB breakout board), specifically:
- **ILI9488** controller, 3.95", 320×480, **40-pin FPC 0.5mm pitch**
- Resistive touch (not connected — touch pins left NC on PCB)
- [AliExpress link](https://it.aliexpress.com/item/1005009422879126.html)

Do **NOT** buy display modules with PCB breakout + pin headers — those are for breadboard prototyping and won't fit the FPC connector on the PCB.
:::
