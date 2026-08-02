---
id: schematics
title: Electrical Schematics
sidebar_position: 2
---

import useBaseUrl from '@docusaurus/useBaseUrl';

# Electrical Schematics

Complete electrical design for the ESP32 Emu Turbo, split into 6 detailed schematic sheets with cross-sheet global labels.

<div className="sheet-grid">
  <a href="#sheet-1--power-supply" className="sheet-card">
    <h4>1. Power Supply</h4>
    <p>USB-C, IP5306, SY8089 buck, battery</p>
  </a>
  <a href="#sheet-2--mcu-esp32-s3" className="sheet-card">
    <h4>2. MCU</h4>
    <p>ESP32-S3 + 31 GPIO labels</p>
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
  <a href="#usb-data-flash--debug" className="sheet-card">
    <h4>USB Data</h4>
    <p>Native USB — on Sheets 1–2</p>
  </a>
</div>

<a className="pdf-download" href={useBaseUrl('/img/schematics/esp32-emu-turbo-schematics.pdf')} target="_blank">Download all sheets (PDF, 6 pages)</a>

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
                    │ LiPo Batt │   │  SY8089    │
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

USB-C input with CC pull-downs, F1 resettable PTC fuse on the VBUS input, IP5306 charge-and-play module, SY8089AAAC synchronous buck regulator (L2 + C30 + R25/R26 feedback divider), Q1 battery reverse-polarity protection, and USBLC6 ESD protection + series resistors on the USB data lines.

<div className="schematic-container">

![Power Supply Schematic](/img/schematics/01-power-supply.svg)

</div>

<a className="pdf-download" href={useBaseUrl('/img/schematics/01-power-supply.pdf')} target="_blank">PDF</a>

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| J1 | USB-C connector | — | 5V power input | [PDF](/datasheets/J1_USB-C-16pin_C2765186.pdf) |
| J3 | JST PH 2-pin SMD connector | C295747 | LiPo battery connector (surface-mount, no through-holes) | [PDF](/datasheets/J3_JST-PH-2pin_C173752.pdf) — *THT sibling C173752; only the mating dimensions apply* |
| F1 | PTC resettable fuse | 2 A hold, 1812 (C960026) | VBUS input overcurrent protection: J1 delivers on **VBUS_IN**, the board's VBUS is reached through F1 (R3-HIGH-4 fix, in design since `1c3ded4`) | — |
| R1, R2 | Resistor | 5.1 kΩ | CC1/CC2 pull-down (UFP identification) | [PDF](/datasheets/R1-R2_5.1k-0805_C27834.pdf) |
| R16 | Resistor | 100 kΩ | IP5306 KEY pin pull-down | [PDF](/datasheets/R16_100k-0805_C149504.pdf) |
| R17 | Resistor | 1 kΩ | LED1 current limiting | [PDF](/datasheets/R17-R18_1k-0805_C17513.pdf) |
| R18 | Resistor | 1 kΩ | LED2 current limiting | [PDF](/datasheets/R17-R18_1k-0805_C17513.pdf) |
| U2 | IP5306 module | — | LiPo charger + 5V boost (charge-and-play) | [PDF](/datasheets/U2_IP5306_C181692.pdf) |
| BT1 | Battery | LiPo 3.7V 5000mAh | 105080 cell | — |
| U3 | Buck regulator | SY8089AAAC | 5V to 3.3V, 2A max, ~93% | [PDF](/datasheets/U3_SY8089AAAC_C78988.pdf) |
| U4 | USB ESD TVS | USBLC6-2SC6 SOT-23-6 (C7519) | USB D+/D− ESD protection | — |
| R22, R23 | Resistor | 22 Ω 0402 (C25092) | USB D+/D− series resistors | — |
| Q1 | P-MOSFET | SI2301CDS SOT-23 (C10487) | Battery reverse-polarity protection (BAT_IN → BAT+) | — |
| R24 | Resistor | 100 kΩ | Q1 gate pull-down (MOSFET ON for correct polarity) | [PDF](/datasheets/R16_100k-0805_C149504.pdf) |
| L1 | Inductor | 1 µH 4.5A | IP5306 boost inductor | [PDF](/datasheets/L1_1uH-Inductor_C280579.pdf) |
| LED1 | Red LED | 0805 | Power indicator (+3V3, always on — U2's LED pins are NC on this board) | [PDF](/datasheets/LED1_Red-LED-0805_C84256.pdf) |
| LED2 | Red LED | 0805 | Second power indicator (+3V3, always on). **C19171391 is red** (YLED0805R, 615–630 nm) — it was mislabelled "green" in BOM and docs | [PDF](/datasheets/LED2_Red-LED-0805_C19171391.pdf) |
| SW16 | Slide switch | SS-12D00G3 (C431540) | Power on/off — **⚠ not in series in ANY revision to date (v4.4.0 included), see warning below** | [PDF](/datasheets/SW16_Slide-Switch_C431540.pdf) |
| L2 | Inductor | 2.2 µH 2.95 A (C36409) | SY8089 buck output inductor | — |
| R25 | Resistor | 100 kΩ | Buck feedback divider, upper leg — Vout = 0.6 × (1 + R25/R26) = 3.327 V | [PDF](/datasheets/R16_100k-0805_C149504.pdf) |
| R26 | Resistor | 22 kΩ (C17560) | Buck feedback divider, lower leg | — |
| C29 | Capacitor | 22 pF C0G (C1804) | Feed-forward across R25 (loop phase boost) | — |
| C1 | Capacitor | 22 µF 1206 MLCC | SY8089 buck **input** decoupling — tight hot loop to VIN/GND | [PDF](/datasheets/C2-C19_22uF-1206_C12891.pdf) |
| C30 | Capacitor | 22 µF 1206 MLCC | SY8089 buck **output** — ceramic. (The tantalum C2 that lived here for the AMS1117's ESR window is deleted; it is what destroyed prototype #1, see [the incident](/docs/rework/incident-c2-reversed).) | [PDF](/datasheets/C2-C19_22uF-1206_C12891.pdf) |
| C17, C18 | Capacitor | 10 µF | IP5306/rail decoupling | [PDF](/datasheets/C1-C18_10uF-0805_C15850.pdf) |
| C19 | Capacitor | 22 µF | Bulk capacitor on IP5306 VOUT | [PDF](/datasheets/C2-C19_22uF-1206_C12891.pdf) |
| C27 | Capacitor | 10 µF | IP5306 VOUT HF decoupling | [PDF](/datasheets/C1-C18_10uF-0805_C15850.pdf) |

### Power Budget

| Consumer | Rail | Typical | Peak |
|----------|------|---------|------|
| ESP32-S3 (dual-core active) | +3V3 | 150 mA | 350 mA |
| ILI9488 logic + panel drive | +3V3 | 20 mA | 30 mA |
| Backlight (LED-A via R27, always on) | **+5V** | 90 mA | 95 mA |
| PAM8403 + speaker | +5V | 20 mA | 100 mA |
| SD card (SPI read) | +3V3 | 30 mA | 100 mA |
| Misc (pull-ups, buttons) | +3V3 | 10 mA | 20 mA |
| **Total** | | **~320 mA** | **~695 mA** |

**Battery life:** ~**12.9 hours** typical gameplay.

Not `5000 / 320`. That division ignores both conversion stages. The +3V3 rail
(210 mA typical) passes through the SY8089 buck at ~93% (a buck converts
*power*, so its input current scales by the voltage ratio); the backlight and
PAM8403 draw straight from +5V; and the whole 5V rail is produced by the
IP5306 boosting 3.7V at ~90%:

```
I_5V  = 210 x 3.3 / (5 x 0.93) + 90 + 20 = 259 mA
I_bat = 259 x 5 / (3.7 x 0.90) = 389 mA   ->  5000 / 389 = 12.9 h
```

Two design notes baked into these figures: the backlight moved from a
hardwired +3V3 tie to **+5V through R27 (20 Ω, net LED_BLA, ~90 mA)** in the
R25 respin — brighter and current-limited, at a real runtime cost — and the
SY8089 buck replaced the AMS1117 LDO (a linear regulator draws the full +3V3
current from the 5V rail regardless of output voltage, costing ~25% runtime
and ~7x more heat). Fabricated boards through v4.3.1 predate the R27 change
and tie LED-A to +3V3.

### Power Path Architecture

```
                          ┌─────────────┐
  USB-C ─VBUS_IN─► F1 ────┤ pin 1 (VIN) │
  (5V)            (PTC)   │             │
                          │   IP5306    │──pin 8 (VOUT)──► +5V ──► SY8089 ──► +3V3
                          │             │                          (U3)       (ESP32, LCD, SD)
  Battery ─BAT_IN─► Q1 ───┤ pin 6 (BAT) │
  (3.7V)   (J3)   (RPP)   │             │──pin 7 (LX)──── L1 ────► BAT+
                   BAT+   │   pin EP    │
                          └──────┬──────┘
                                GND

  SW16 (slide switch): common pin tapped on BAT+ as a stub — throw pins unrouted (see warning)
```

**Key design points:**
- **Q1 (SI2301 P-MOSFET)** sits in series between J3 (net **BAT_IN**) and the **BAT+** rail: for a correctly-inserted battery the gate (pulled low by R24) keeps it ON; a reversed battery is blocked by the body diode.
- **SW16** was intended between battery and IP5306 pin 6 (BAT) — but is **not functional in any revision to date** (see warning below). It does NOT control USB VBUS.
- **VBUS** reaches IP5306 pin 1 (VIN) through the F1 PTC fuse (J1 → VBUS_IN → F1 → VBUS) — always available when USB is plugged in.
- **IP5306 passthrough:** when USB is connected, VBUS (5V) passes to VOUT regardless of battery/switch state.
- **No backfeed diode needed:** IP5306 charger is internally regulated (CC/CV), boost is unidirectional.

:::caution SW16 does not switch anything — a standing design limitation, not a build defect
Still true in the current design (v4.4.0): PCB routing connects only the switch
**common pin (2)** to BAT+ as a stub; throw pins 1/3 are unrouted
(`hardware/datasheet_specs.py` declares them unconnected). The battery path
**J3 → Q1 → BAT+ → IP5306 pin 6** is continuous copper that never passes through the
switch, so sliding it changes nothing. Consequences:

- Power-state rows with *SW16 = OFF* describe **design intent**, not actual behavior
  on any board built from this design.
- To truly isolate the battery (e.g. for flashing), **unplug the J3 battery connector**.
- System on/off relies on the IP5306 KEY logic (SW13/MENU via R16) and its automatic
  light-load standby.
- **Planned respin fix** (tracked in the RESPIN section of
  [`docs/known-issues.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/docs/known-issues.md)):
  route the battery through switch pins 1–2 in series (BAT_IN side).
:::

### Power States & Debug

| # | USB | SW16 | Reset | Boot | +3V3 | ESP32 | Charging | Serial | Flash |
|---|-----|--------|-------|------|------|-------|----------|--------|-------|
| 1 | No | OFF | — | — | OFF | OFF | No | No | No |
| 2 | No | ON | — | — | ON | Run | No | No | No |
| 3 | No | ON | Press | — | ON→OFF→ON | Reset | No | No | No |
| 4 | **Yes** | OFF | — | — | **ON** | Run | **No** | **Yes** | No |
| 5 | **Yes** | OFF | Press | Hold | ON→OFF→ON | **DL mode** | No | No | **Yes** |
| 6 | **Yes** | ON | — | — | ON | Run | **Yes** | **Yes** | No |
| 7 | **Yes** | ON | Press | Hold | ON→OFF→ON | **DL mode** | Yes | No | **Yes** |

**State legend:**
- **#4–5:** USB debug/flash with battery isolated (switch OFF) — zero backfeed risk, ideal for development
- **#6–7:** Charge-and-play — IP5306 charges battery AND powers system simultaneously
- **DL mode:** ESP32 download mode (hold BOOT, press+release RST, release BOOT)

### Flash & Debug Procedures

**Flash firmware (recommended: switch OFF):**
1. Connect USB-C cable
2. Set SW16 to OFF (⚠ ineffective on every board to date — unplug J3 for true battery isolation)
3. Hold **SW14**, press+release **SW15**, release **SW14**
4. Run `idf.py flash` — ESP32 enters download mode
5. Press **SW15** to reboot into normal mode

**Serial debug monitor:**
1. Connect USB-C cable (SW16 ON or OFF — both work)
2. Run `idf.py monitor` (115200 baud via USB CDC on GPIO19/20)
3. Press **SW15** to restart — monitor auto-reconnects

**Charge-and-play:**
1. Connect USB-C with SW16 ON
2. System runs normally while battery charges
3. LED1 and LED2: both red, both plain +3V3 power indicators. The old "LED1 = charging, LED2 (green) = fully charged" description was aspirational — the IP5306's LED pins (2–4) are NC on the fabricated board, and C19171391 is a red part despite its BOM label. Respin: route U2 pins 2/4 to the LEDs if charge indication is wanted

### Backfeed Protection Analysis

| Path | Protection | Mechanism |
|------|-----------|-----------|
| VBUS → BAT+ | IP5306 internal charger | CC/CV regulated, max 1A |
| BAT+ → VBUS | Boost unidirectional | IP5306 boost only drives BAT→VOUT |
| USB + switch OFF | Physical isolation *(design intent — see SW16 warning; today: unplug J3)* | SW16 would disconnect battery from IP5306 pin 6 |
| USB + switch ON | Charge-and-play | IP5306 manages both paths internally |
| Reversed battery | Q1 P-MOSFET RPP | Body diode blocks; gate pull-down R24 keeps Q1 ON only with correct polarity |

---

## Sheet 2 — MCU (ESP32-S3)

ESP32-S3-WROOM-1 N16R8 with all 31 GPIO connections grouped by function, decoupling capacitors, and the EN reset RC network (R3 + C31, added in the R25 respin). LCD_RD is hardwired to +3V3 on the PCB and the backlight is fed from +5V via R27 (neither is GPIO-controlled).

<div className="schematic-container">

![MCU Schematic](/img/schematics/02-mcu.svg)

</div>

<a className="pdf-download" href={useBaseUrl('/img/schematics/02-mcu.pdf')} target="_blank">PDF</a>

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| U1 | MCU module | ESP32-S3-WROOM-1 N16R8 | 16MB Flash, 8MB PSRAM | [PDF](/datasheets/U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf) |
| R3 | Resistor | 10 kΩ | EN pull-up to +3V3 (R25 respin, `1c3ded4` — the earlier "WROOM-1 integrates an EN pull-up" claim was **falsified**: the module has none, and boards through v4.3.1 shipped without any RC) | [PDF](/datasheets/R3-R15_10k-0805_C17414.pdf) |
| C31 | Capacitor | 100 nF | EN → GND reset delay (RC ≈ 1 ms with R3, module datasheet p.28 power-up timing) | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| C3 | Capacitor | 100 nF | 3V3 decoupling (twin of C4) — NOT the EN cap; that is C31 | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| C4 | Capacitor | 100 nF | 3V3 decoupling | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| C26 | Capacitor | 100 nF | 3V3 VDD bypass (within 3.6 mm of module pin 2) | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| SW15 | Tact switch | — | EN reset (pulls EN low) | [PDF](/datasheets/SW1-SW13_Tact-Switch_C318884.pdf) |
| SW14 | Tact switch | — | Boot mode (pulls GPIO0 low) | [PDF](/datasheets/SW1-SW13_Tact-Switch_C318884.pdf) |

### GPIO Assignment

| Function | GPIOs | Signals | Bus |
|----------|-------|---------|-----|
| **Display** | 4–11 | D0–D7 | 8080 data |
| | 12, 13, 14, 46 | CS, RST, DC, WR | 8080 control |
| | — | RD | Tied to +3V3 (hardwired) |
| | — | BL | +5V via R27 20 Ω (net LED_BLA, always on) |
| **Audio** | 17 | I2S_DOUT | PDM TX (single pin — no BCLK/LRCK) |
| | 15, 16 | — | Unconnected: the I2S clock reservation was retired with the move to PDM |
| **SD Card** | 44, 43, 38, 39 | MOSI, MISO, CLK, CS | SPI |
| **D-pad** | 40, 41, 42, 1 | UP, DOWN, LEFT, RIGHT | GPIO |
| **Face** | 2, 48, 47, 21 | A, B, X, Y | GPIO |
| **System** | 18, 0 | START, SELECT | GPIO |
| **Shoulder** | 45, 3 | L, R | GPIO |
| **USB Data** | 19, 20 | USB_D-, USB_D+ | USB |

:::info Reserved GPIOs
GPIO26–32 are the WROOM-1's internal SPI flash bus and are not brought out on any
module pin. GPIO33–37 belong to the N16R8's Octal PSRAM — GPIO35–37 *do* appear on
module pins 28–30 but carry explicit no-connect markers in the schematic and must
stay unconnected. GPIO19/20 are the native USB D-/D+ pins (firmware flash + debug
console via USB CDC).
:::

---

## Sheet 3 — Display

ILI9488 3.95" 320×480 bare panel with 40-pin FPC, 8-bit 8080 parallel interface — mandatory for SNES emulation speed. *(The generated sheet title and the DS1 symbol value still read "4.0in" — a label-only mismatch in `scripts/generate_schematics/sheets/display.py`; the panel, the enclosure cutout and the BOM are all the 3.95" part.)* FPC pin mapping per ILI9488 panel datasheet: pins 9-12=CS/DC/WR/RD, pin 15=RESET, pins 17-24=DB0-DB7, pin 33=LED-A (backlight — fed from +5V through R27 on net LED_BLA, ~90 mA, always on), pins 6-7=VDDI/VDDA(+3V3), pins 38-39=IM0/IM1(+3V3), pin 40=IM2(GND). **Note:** on the PCB, display Pin N maps to connector Pad (41−N) due to the landscape FPC pass-through (see [PCB docs](pcb.md#fpc-slot--pin-reversal)).

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| J4 | FPC connector | 40-pin 0.5mm bottom contact | Display ribbon cable | [PDF](/datasheets/J4_FPC-40pin-0.5mm_C2856812.pdf) |
| R27 | Resistor | 20 Ω 1206 | Backlight series resistor: +5V → R27 → LED_BLA → FPC pad 8 (panel pin 33, LED-A). R25-HIGH-1 fix, in design since `1c3ded4`; boards through v4.3.1 tie LED-A to +3V3 instead | — |

<div className="schematic-container">

![Display Schematic](/img/schematics/03-display.svg)

</div>

<a className="pdf-download" href={useBaseUrl('/img/schematics/03-display.pdf')} target="_blank">PDF</a>

The 8080 parallel mode writes a full pixel (16-bit RGB565) in 2 bus cycles. SPI would need 16 clock cycles per pixel, making it too slow for 60fps full-screen SNES rendering. GPIO4–11 form a contiguous 8-bit data bus for efficient register-level DMA.

---

## Sheet 4 — Audio

I2S output from ESP32-S3 to PAM8403 Class-D amplifier driving a 28mm 8Ω speaker.

<div className="schematic-container">

![Audio Schematic](/img/schematics/04-audio.svg)

</div>

<a className="pdf-download" href={useBaseUrl('/img/schematics/04-audio.pdf')} target="_blank">PDF</a>

| Ref | Component | Value | Purpose | Datasheet |
|-----|-----------|-------|---------|-----------|
| U5 | Amplifier | PAM8403 | Filterless Class-D, 3W/ch | [PDF](/datasheets/U5_PAM8403_C5122557.pdf) |
| C21 | Capacitor | 100 nF (C49678) | VREF bypass capacitor | [PDF](/datasheets/C3-C16_100nF-0805_C49678.pdf) |
| C22 | Capacitor | 0.47 µF (C13967) | DC-blocking cap on audio input | — |
| C23, C24, C25 | Capacitor | 1 µF (C28323) | VDD and PVDD decoupling caps | — |
| R20, R21 | Resistor | 20 kΩ (C4328) | Bias resistors on INL/INR to **VREF** (pin 8), not GND | — |
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

<a className="pdf-download" href={useBaseUrl('/img/schematics/05-sd-card.pdf')} target="_blank">PDF</a>

| Ref | Component | Datasheet |
|-----|-----------|-----------|
| U6 | Micro SD slot (TF-01A) | [PDF](/datasheets/U6_TF-01A_MicroSD_C91145.pdf) |

| Signal | GPIO | Direction |
|--------|------|-----------|
| MOSI | GPIO44 | ESP32 → SD |
| MISO | GPIO43 | SD → ESP32 |
| CLK | GPIO38 | ESP32 → SD |
| CS | GPIO39 | ESP32 → SD |

SPI bus up to 20MHz. The SD module has a built-in level shifter (3.3V safe). On the PCB, the SD card slot VCC and GND pins are connected via vias to the inner power planes (+3V3 and GND) for clean power delivery with minimal trace length.

---

## Sheet 6 — Controls

13 tact switches (SNES layout + MENU) with individual 10kΩ pull-up + 100nF debounce per button. Plus SW15 (reset) and SW14 (boot mode) on Sheet 2. Tact switch datasheet: [PDF](/datasheets/SW1-SW13_Tact-Switch_C318884.pdf).

<div className="schematic-container">

![Controls Schematic](/img/schematics/06-controls.svg)

</div>

<a className="pdf-download" href={useBaseUrl('/img/schematics/06-controls.pdf')} target="_blank">PDF</a>

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
| R4–R13, R15 | Resistor | 10 kΩ (C17414) | Button pull-ups — 11 of the 12 buttons |
| R14 | Resistor | **DNP** | BTN_L (GPIO45) gets no external pull-up: GPIO45 is the VDD_SPI strapping pin, and a pull-up would force VDD_SPI to 1.8 V and break the Octal PSRAM. Firmware enables the internal pull-up after boot |
| C5–C16 | Capacitor | 100 nF (C49678) | Button debounce (12 buttons) |

| Group | Buttons | Switches | GPIOs |
|-------|---------|----------|-------|
| D-pad | UP, DOWN, LEFT, RIGHT | SW1–SW4 | 40, 41, 42, 1 |
| Face | A, B, X, Y | SW5–SW8 | 2, 48, 47, 21 |
| System | START, SELECT, MENU | SW9, SW10, SW13 | 18, 0, — |
| Shoulder | L, R | SW11, SW12 | 45, 3 |

---

## USB Data (flash & debug)

Native USB data lines for firmware flashing and debug console (replaces UART debug).
There is no dedicated sheet: the USB data path is drawn on **Sheet 1** (J1 → U4 USBLC6
ESD protection → R22/R23 22 Ω series resistors) and lands on **Sheet 2** at ESP32
GPIO19/20 via the `USB_D-`/`USB_D+` global labels.

| Signal | GPIO | Function |
|--------|------|----------|
| USB_D- | GPIO19 | USB data minus (native USB) |
| USB_D+ | GPIO20 | USB data plus (native USB) |

USB-C now carries both **power** (charging via IP5306) and **data** (firmware flash + CDC debug console). This replaces the previous UART debug approach (GPIO43 TX0) with native USB, which is faster and requires no external UART adapter. See [Power States & Debug](#power-states--debug) for the full operating modes table and flash/debug procedures.

:::info Joystick removed
The optional PSP joystick (previously GPIO20/GPIO44) has been removed. The D-pad provides full SNES/NES control. GPIO43 (previously TX0 for UART debug) is now used for SD_MISO. BTN_R is on GPIO3.
:::

---

## v2 — additional sheet: Audio Coprocessor (ESP32-S3-MINI-1)

:::info Future revision — naming note
"v2" on this page means the **planned audio-coprocessor respin**, which no fabricated
or tagged revision implements yet: every release tag so far (v4.0 → v4.4.0) is a
revision of the single-MCU board this document calls "v1". The current board uses
direct I2S from the main ESP32-S3 to the PAM8403 (Sheet 4). In the coprocessor
revision, the main ESP32-S3 communicates with the coprocessor via SPI, and the
coprocessor drives I2S to the PAM8403.
:::

ESP32-S3-MINI-1-N8 audio coprocessor with SPI slave interface to the main ESP32-S3 and I2S output to the PAM8403 amplifier.

| Ref | Component | Value | Purpose |
|-----|-----------|-------|---------|
| U7 | ESP32-S3-MINI-1-N8 | Module | Audio coprocessor (SPC700 + I2S) |
| C32 | Capacitor | 100 nF | 3V3 decoupling |
| C33 | Capacitor | 100 nF | EN decoupling |

*(References C1–C31 are all taken on the v1 board — C28 is a DNP placeholder, C29 is the buck feed-forward, C30 the buck output and C31 the EN reset cap — so the coprocessor starts at **C32**.)*

### SPI Bus (Main ESP32-S3 → Coprocessor)

| Signal | Main ESP32-S3 GPIO | MINI-1 GPIO | Direction |
|--------|-------------------|-------------|-----------|
| SPI_CLK | GPIO 15 (unused in v1) | GPIO 12 | Main → MINI-1 |
| SPI_MOSI | GPIO 16 (unused in v1) | GPIO 11 | Main → MINI-1 |
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
| GPIO 15 | unconnected (PDM needs no BCLK) | SPI_CLK → MINI-1 | Spare pin put to work |
| GPIO 16 | unconnected (PDM needs no LRCK) | SPI_MOSI → MINI-1 | Spare pin put to work |
| GPIO 17 | I2S_DOUT → PAM8403 | SPI_MISO ← MINI-1 | Audio path moves to coprocessor |
| GPIO 20 | USB_D+ (native USB) | SPI_CS → MINI-1 | USB D+ reassigned for coprocessor |

:::tip Clean GPIO reuse
GPIO 15/16 (already spare in v1) plus the single PDM pin GPIO 17 freed by moving audio to the coprocessor become the SPI link — no GPIOs wasted. GPIO 20 (USB_D+ in v1) is reassigned to SPI chip select; in v2, USB native data is no longer available (debug via SPI or UART instead).
:::
