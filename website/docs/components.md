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

### FPC 40-Pin Pinout (typical ILI9488 + resistive touch)

| Pin | Signal | Direction | Description |
|-----|--------|-----------|-------------|
| 1 | GND | — | Ground |
| 2 | LEDK | — | Backlight cathode (GND) |
| 3 | LEDA | — | Backlight anode (3.3V) |
| 4-5 | GND | — | Ground |
| 6 | RESET | Input | LCD reset (active low) |
| 7 | CS | Input | Chip select (active low) |
| 8 | RS/DC | Input | Register select / Data-Command |
| 9 | WR | Input | Write strobe (8080 mode) |
| 10 | RD | Input | Read strobe (8080 mode) |
| 11-18 | DB0-DB7 | I/O | 8-bit data bus |
| 19-26 | DB8-DB15 | I/O | 16-bit extension (NC in 8-bit mode) |
| 27-28 | GND | — | Ground |
| 29 | TE | Output | Tearing effect (optional, for vsync) |
| 30-31 | IM0-IM1 | Input | Interface mode select |
| 32-33 | GND | — | Ground |
| 34-35 | VCC | — | Logic power (3.3V) |
| 36 | T_CLK | — | Touch SPI clock — **NC (not connected)** |
| 37 | T_CS | — | Touch SPI chip select — **NC** |
| 38 | T_DIN | — | Touch SPI MOSI — **NC** |
| 39 | T_DO | — | Touch SPI MISO — **NC** |
| 40 | GND | — | Ground |

:::warning Pinout may vary
The exact pinout depends on the specific panel manufacturer. **Always verify the FPC pinout** from the seller's datasheet before ordering the PCB. The table above is a typical reference for ILI9488 40-pin panels. Touch pins (36-39) are left unconnected.
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
| **PSP Joystick** (optional) | 2-axis analog, PSP 2000/3000 | **$2.11** | [AliExpress](https://www.aliexpress.com/item/32830760575.html) |

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
| Extra controls | Rubber pads + PSP joystick | $2.38 |
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

| Ref | Component | Package | LCSC | Class |
|-----|-----------|---------|------|-------|
| U1 | ESP32-S3-WROOM-1-N16R8 | Module | C2913202 | Extended |
| U2 | IP5306 charger+boost IC | eSOP-8 | C181692 | Extended |
| U3 | AMS1117-3.3 LDO | SOT-223 | C6186 | Basic |
| U5 | PAM8403 audio amplifier | SOP-16 | C5122557 | Extended |
| J1 | USB-C 16-pin connector | SMT | C2765186 | Extended |
| U6 | Micro SD slot (TF-01A) | SMT | C91145 | Extended |
| J4 | FPC 40-pin 0.5mm (display) | SMT | TBD | Extended |
| J3 | JST PH 2-pin (battery) | THT | C173752 | Extended |
| L1 | 1µH inductor 4.5A | SMD 4×4 | C280579 | Extended |
| SW1–SW12 | SMT tact switch 5.1×5.1mm | SMT | C318884 | Extended |
| R1–R2 | 5.1kΩ 0805 | 0805 | C27834 | Basic |
| R3–R15 | 10kΩ 0805 | 0805 | C17414 | Basic |
| R16 | 100kΩ 0805 | 0805 | C149504 | Basic |
| C3–C16 | 100nF 0805 | 0805 | C49678 | Basic |
| C1,C17,C18 | 10µF 0805 | 0805 | C15850 | Basic |
| C2,C19 | 22µF 1206 | 1206 | C29632 | Basic |

**Estimated PCB cost:** ~$90 for 5 boards (~$18/board) including fabrication, components, and assembly.

---

## PCB Version — What to Buy Separately

When ordering the custom PCB from JLCPCB, the following components are **NOT included** in the assembly and must be purchased from AliExpress:

| Component | Ref | Price | Connection to PCB | Solder? |
|-----------|-----|-------|-------------------|---------|
| **ILI9488 3.95" bare LCD panel** (40P FPC 0.5mm, resistive touch NC) | U4 | ~$3.95 | FPC ribbon → J4 connector (slide + latch) | No |
| **LiPo 105080 5000mAh battery** | BT1 | ~$6-8 | JST PH plug → J3 connector | No |
| **Speaker 28mm 8Ω** | SPK1 | ~$0.80 | 2 wires → solder pads | Yes (easy) |
| **PSP joystick** (optional) | J2 | ~$2 | 4 pins → pin header | Yes (easy) |
| | | **~$17-23** | | |

:::tip
The display and battery are **plug-in** — no soldering skills required. Only the speaker (2 wires) and optional joystick need soldering.
:::

:::warning Display purchase — important
Buy the **bare LCD panel** (no PCB breakout board), specifically:
- **ILI9488** controller, 3.95", 320×480, **40-pin FPC 0.5mm pitch**
- Resistive touch (not connected — touch pins left NC on PCB)
- [AliExpress link](https://it.aliexpress.com/item/1005009422879126.html)

Do **NOT** buy display modules with PCB breakout + pin headers — those are for breadboard prototyping and won't fit the FPC connector on the PCB.
:::
