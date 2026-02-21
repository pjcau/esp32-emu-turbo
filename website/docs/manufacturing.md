---
id: manufacturing
title: PCBA Manufacturing & Ordering
sidebar_position: 9
---

# PCBA Manufacturing & Ordering

Production-ready PCB Assembly (PCBA) ordered from [JLCPCB](https://jlcpcb.com/) — minimum order of 5 units with full SMT assembly.

:::tip Release v1.6 (2026-02-21)
All production files in `release_jlcpcb/` are verified and ready for ordering:
- **JLCPCB DFM footprint fix** — all 8 flagged components (J4, U1, U6, SW_PWR, U5, J1, SW11, SW12) corrected with pad geometries from KiCad 10 standard library and JLCPCB/EasyEDA official component library
- **R17/R18 BOM fix** — LCSC part C11702 (0402) replaced with C17513 (correct 0805 package)
- **ESP32-S3 pin layout** — corrected from 2-side (wrong) to 3-side layout (L:1-14, B:15-26, R:27-40)
- **MSK12C02 slide switch** — replaced THT footprint with correct 7-pad SMD (matching C431540)
- **64 components** in BOM/CPL matched against schematic and PCB
- **0 DRC errors**, all pre-production checks passed
:::

## Assembled PCB Preview

### Top Side — Controls & LEDs

<div style={{textAlign: 'center'}}>

![PCBA Top Side](/img/manufacturing/pcba-top.png)

</div>

The top side carries all user-facing components:

| Designator | Component                                        | JLCPCB Part # | Footprint |
| :--------- | :----------------------------------------------- | :------------ | :-------- |
| LED1       | Red LED (power indicator)                        | C84256        | LED_0805  |
| LED2       | Green LED (charge indicator)                     | C19171391     | LED_0805  |
| SW1–SW10   | SMT tactile buttons (D-pad, ABXY, Start, Select) | C318884       | SW-SMD    |

All 12 gaming buttons are surface-mounted on the top face for direct user interaction.

---

### Bottom Side — Core Electronics

<div style={{textAlign: 'center'}}>

![PCBA Bottom Side](/img/manufacturing/pcba-bottom.png)

</div>

The bottom side hosts the main circuitry:

| Designator     | Component                   | JLCPCB Part # | Footprint |
| :------------- | :-------------------------- | :------------ | :-------- |
| **U1**         | ESP32-S3-WROOM-1 (N16R8)    | C2913202      | Module    |
| **U2**         | IP5306 (charge management)  | C181692       | ESOP-8    |
| **U3**         | AMS1117-3.3 (LDO regulator) | C6186         | SOT-223   |
| **U5**         | PAM8403 (audio amplifier)   | C5122557      | SOP-16    |
| **J1**         | USB-C connector (16-pin)    | C2765186      | USB-C-SMD |
| **J3**         | JST-PH 2-pin (battery)      | C173752       | JST-PH-2  |
| **J4**         | FPC 40-pin 0.5mm (display)  | C2856812      | FPC-40P   |
| **L1**         | 1uH 5A inductor             | C280579       | SMD-4x    |
| **SW_PWR**     | Slide switch (power)        | C431540       | SS-12D0   |
| **SW11, SW12** | SMT tactile (L, R shoulder) | C318884       | SW-SMD    |
| R1, R2         | 5.1k (USB-C CC)             | C27834        | R_0805    |
| R3–R15         | 10k (pull-ups)              | C17414        | R_0805    |
| R16            | 100k                        | C149504       | R_0805    |
| R17, R18       | 1k                          | C17513        | R_0805    |
| C1, C17, C18   | 10uF                        | C15850        | C_0805    |
| C2, C19        | 22uF                        | C12891        | C_1206    |
| C3–C16         | 100nF                       | C49678        | C_0805    |

**Total SMT components:** 20 unique part types, ~55 individual placements.

---

## JLCPCB Quote Breakdown (5 units)

<div style={{textAlign: 'center'}}>

![JLCPCB Quote](/img/manufacturing/jlcpcb-quote.png)

</div>

### PCB Fabrication

| Item             |       Cost |
| :--------------- | ---------: |
| Engineering fee  |     $24.00 |
| Board (5 pcs)    |      $7.50 |
| Via Covering     |      $0.00 |
| **PCB Subtotal** | **$31.50** |

### PCBA Assembly

| Item                     |        Cost |
| :----------------------- | ----------: |
| Setup Fee                |      $50.37 |
| Stencil                  |      $16.18 |
| Components (20 items)    |      $39.87 |
| Feeders Loading fee      |      $28.69 |
| SMT Assembly             |       $2.79 |
| Hand-soldering labor fee |       $3.53 |
| Manual Assembly          |       $0.16 |
| PCB assembly fixture     |      $16.18 |
| X-Ray Inspection         |       $8.10 |
| Packaging fee            |       $0.49 |
| **PCBA Subtotal**        | **$166.36** |

### Total

|                     |             |
| :------------------ | ----------: |
| **Total (5 PCBAs)** | **$197.86** |
| **Per unit cost**   |  **$39.57** |
| Weight              |     1.12 kg |

:::tip Per-unit cost
At **$39.57/board**, each fully assembled PCBA falls well within the project's $33–45 prototype budget target. The per-unit cost drops significantly with larger orders since most fees (setup, stencil, fixture, engineering) are one-time.
:::

### Build Time Options

| Assembly speed      | Extra cost | Total lead time |
| :------------------ | ---------: | :-------------- |
| 7–8 days (standard) |      $0.00 | ~12–13 days     |
| 6–7 days            |     $48.53 | ~11–12 days     |
| 5–6 days            |     $97.06 | ~10–11 days     |

PCB fabrication takes 5 days in all cases. Standard assembly (7–8 days) is included at no extra charge.

---

## Cost Analysis

### What's included in the $39.57/unit

Each assembled board arrives with **all SMT components soldered**:
- ESP32-S3 module, IP5306 charger, AMS1117 regulator, PAM8403 amplifier
- USB-C, JST battery, and FPC display connectors
- All passive components (resistors, capacitors, inductor)
- Power slide switch, 12 tactile buttons, and status LEDs

### What still needs manual assembly

These components are **not included** in the JLCPCB order and must be connected separately:
- **Display** — ILI9488 3.95" via 40-pin FPC cable
- **Battery** — LiPo 3.7V 5000mAh via JST-PH connector
- **Speaker** — 28mm 8 ohm via solder pads
- **SD card module** — via SPI wiring
- **3D-printed enclosure** — see [Enclosure Design](/docs/enclosure)

### Complete prototype cost estimate

| Item                    |        Cost |
| :---------------------- | ----------: |
| PCBA (1 of 5)           |      $39.57 |
| Shipping (estimated)    |      ~$8–15 |
| ILI9488 display         |         ~$6 |
| LiPo battery 5000mAh    |         ~$5 |
| Speaker 28mm            |         ~$1 |
| SD card module          |         ~$1 |
| 3D printed enclosure    |       ~$3–5 |
| **Total per prototype** | **~$64–73** |

:::info Economies of scale
The one-time fees (engineering $24, stencil $16.18, setup $50.37, fixture $16.18) total **$106.73** — this is amortized across all 5 units. If ordering 10+ units, the per-unit cost drops below $25.
:::

---

## v2 PCB — Audio Coprocessor Addition

The v2 PCB adds an **ESP32-S3-MINI-1-N8** audio coprocessor module (see [Phase 5 — Software Architecture](software.md#phase-5--v2-hardware-audio-coprocessor)). This offloads 100% of audio processing from the main ESP32-S3.

### v2 Additional Assembly Components

| Ref     | Component               | JLCPCB Part # | Footprint            |  Qty |
| :------ | :---------------------- | :------------ | :------------------- | ---: |
| **U7**  | ESP32-S3-MINI-1-N8      | C2913206      | Module (15.4×20.5mm) |    1 |
| C21,C22 | 100nF 0805 (decoupling) | C49678        | C_0805               |    2 |

### v2 Cost Impact

| Item                     |      v1 |      v2 |   Delta |
| :----------------------- | ------: | ------: | ------: |
| JLCPCB components        |    ~$40 |    ~$43 |  +$3.27 |
| Per-unit cost (5 boards) | ~$39.57 |    ~$43 | +~$3.43 |
| Complete prototype       | ~$64–73 | ~$67–76 |    +~$3 |

The v2 addition is minor in cost ($3.27 per unit) but eliminates 48% of SNES frame time at the hardware level. The module's integrated flash and crystal mean **no additional external components** are needed — simpler routing than the RP2040 alternative (which required 7 components).

### v2 Power Budget Update

| Consumer                    | v1 Typical  | v2 Typical  | Notes                       |
| --------------------------- | ----------- | ----------- | --------------------------- |
| ESP32-S3 (dual-core active) | 150 mA      | 150 mA      | Same                        |
| ESP32-S3-MINI-1 (audio)     | —           | 50 mA       | Single-core audio task      |
| ILI9488 display + backlight | 80 mA       | 80 mA       | Same                        |
| PAM8403 + speaker           | 20 mA       | 20 mA       | Same (driven by MINI-1 now) |
| SD card (SPI read)          | 30 mA       | 30 mA       | Same                        |
| Misc (pull-ups, buttons)    | 10 mA       | 10 mA       | Same                        |
| **Total**                   | **~290 mA** | **~340 mA** | +50 mA                      |

**v2 battery life:** 5000 mAh / 340 mA ~ **14.7 hours** typical gameplay (vs 17h on v1). The 50 mA increase from the coprocessor is modest — the AMS1117 regulator (800 mA max) still has ample headroom at 340 mA typical / 740 mA peak.
