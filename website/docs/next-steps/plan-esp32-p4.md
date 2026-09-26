---
id: plan-esp32-p4
title: "Plan A: ESP32-P4 + ESP32-C6"
sidebar_position: 4
---

# Plan A: ESP32-P4 + ESP32-C6

Stay on Espressif microcontrollers: an **ESP32-P4** as the main chip and a
second, small Espressif chip next to it for Wi-Fi and Bluetooth, because
the P4 has no radio. The firmware stays ESP-IDF + retro-go.

Costs and durations are **estimates** for one developer working with
Claude. Facts marked with a source were checked on 2026-09-26; everything
else is to be confirmed on a development board.

## In short

- **HDMI: a real chance.** Espressif supports the LT8912B DSI → HDMI bridge
  with a ready driver, and P4 boards already use it. Realistic target
  720p60 (1080p60 needs more than the P4's two DSI lanes); the PPA scales
  the emulator's frame in hardware. The built-in screen stays the default:
  plugging the cable moves the picture to the TV, unplugging brings it
  back.
- **32-bit, system by system:** Sega CD and CPS1 likely; CPS2 only for ROM
  sets within the 32 MB PSRAM; GBA uncertain (gpSP has no RISC-V dynarec,
  only its interpreter runs, to measure); 32X unlikely (PicoDrive's SH-2
  dynarec targets RV64, not the P4's RV32).
- **Two chips, two firmwares.** The P4 runs our firmware (retro-go,
  emulators, network and Bluetooth host stacks) and calls Wi-Fi as if it
  were local through `esp_hosted`. The radio chip runs Espressif's
  ESP-Hosted slave firmware, built once and pinned to the same version.
  They talk over one SDIO or SPI link; the P4 also resets or powers down
  the radio chip, and can update its firmware over the same link.
- **The original ESP32 beats the C6 as radio chip.** The C6 is BLE only
  (no DualShock, DualSense or Switch Pro, and LE Secure Connections pairing
  currently fails on P4 + C6); the original ESP32 adds Bluetooth Classic,
  and Espressif ships an example of a P4 using it over SPI.
- **Chip revision:** v1.3 (360 MHz) is end-of-life; new designs go on v3.x,
  so the study board must carry that revision.
- **PS1 and N64 stay out** on this plan.

## The chip

- **ESP32-P4:** dual-core 32-bit RISC-V (RV32), up to 32 MB of PSRAM in
  the package, MIPI-DSI and a parallel (i80 / RGB) LCD interface, a 2D
  pixel accelerator (PPA) for scaling and rotation, USB 2.0 high-speed
  with host mode, SDIO host. No Wi-Fi, no Bluetooth.
- **Chip revision matters.** Revision v1.3 runs at 360 MHz by default
  (400 MHz on request) and is end-of-life; Espressif points new designs to
  revision v3.x ([datasheet v1.3](https://documentation.espressif.com/esp32-p4-chip-revision-v1.3_datasheet_en.html)).
  The development board bought for the study must carry the revision the
  console will use, or the measurements do not transfer.

## Requirements

| Requirement | Result | Why (details below) |
|:---|:-:|:---|
| Classic MAME (Z80 / 6502) | 🟢 | as on the S3, with headroom |
| 16-bit (SNES, MD, PCE) | 🟢 | SNES with frame budget to spare |
| 32-bit | 🟡 | Sega CD and CPS1 likely, CPS2 partly, GBA uncertain, 32X unlikely |
| PlayStation | 🔴 | no RISC-V dynarec for the MIPS CPU; an interpreter is far too slow |
| Nintendo 64 | 🔴 | no 3D GPU |
| HDMI | 🟢 | DSI → HDMI bridge supported by Espressif, proven on dev boards |
| Wireless controllers | 🟢 / 🟡 | 🟢 with an original ESP32 as the radio chip (Bluetooth Classic + BLE); 🟡 with the C6 (BLE only) |

**Four of six requirements**, 32-bit partly. PS1 and N64 stay out: that
part does not change with more detail.

## HDMI: a real chance

The P4 has no HDMI output, but Espressif supports one bridge chip for it:
the **Lontium LT8912B** (MIPI-DSI in, HDMI out), with a ready ESP-IDF
driver, `esp_lcd_lt8912b`, in the Espressif BSP
([component](https://components.espressif.com/components/espressif/esp_lcd_lt8912b),
[ESP-FAQ](https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/peripherals/lcd.html)).
It already works on P4 hardware: Olimex sells an LT8912B adapter for its
ESP32-P4 DevKit, and the open ESP-HDMI-Bridge board does the same
([Olimex](https://www.cnx-software.com/2025/12/04/olimex-lt8912b-based-mipi-hdmi-adapter-board-adds-hdmi-output-to-the-esp32-p4-devkit-board/),
[ESP-HDMI-Bridge](https://oshwlab.com/hawaii0707/esp-hdmi-bridge)).

| Question | Answer |
|:---|:---|
| Resolution | **720p60 is the target.** It needs ~1.8 Gbit/s of RGB888 over DSI, within the P4's two DSI lanes. 1080p60 needs more than two lanes carry, so it is out; 480p is the safe fallback |
| Frame buffer | 1280 × 720 RGB888 is 2.8 MB per frame in PSRAM. Scanout at 60 Hz reads ~165 MB/s: a real share of the PSRAM bandwidth, to measure together with the emulator's own traffic |
| Scaling | the emulator draws its native frame (e.g. 256 × 224) and the **PPA scales it in hardware** to 960 × 720 (4:3 inside 720p), no CPU cost |
| Colour format | the driver supports RGB888 only, so the output stage converts from the emulators' RGB565 (the PPA can do it) |
| Handheld screen and TV | **the built-in screen stays the default.** The LT8912B's hot-plug detect (HPD) tells the P4 when a cable is plugged: the picture moves to the TV and the internal backlight turns off; unplugging brings it back to the screen. The two outputs are independent (screen on the i80 bus, TV on DSI), so the switch is a change of target, not a hardware mux. Mirroring both at once would double the scaling work |
| Audio on HDMI | the LT8912B takes an I2S audio input, so HDMI audio is possible (to confirm in its datasheet) |
| Risks | the driver is young (v0.x); DSI and HDMI are high-speed pairs, new ground for this PCB |

### On the main board or separate?

| Option | For | Against |
|:---|:---|:---|
| **External adapter** on a cable (Olimex-style) | no PCB risk | DSI does not survive a long cable: bench study only, not a product |
| **Internal daughterboard** on a short FPC (LT8912B + HDMI connector on a small board) | simpler main board; the connector goes where the enclosure needs it; can be left unfitted; tested as a module first | one more connector and FPC |
| **On the main board** | one PCB, lowest cost in volume | controlled-impedance pairs (DSI plus four TMDS pairs), ESD protection, HPD and DDC: the riskiest part of the board, and a mistake costs a full respin |

Integration is technically possible (the board is already 4-layer and
JLCPCB offers controlled impedance). **Recommendation, in steps:**

1. **Study:** the external adapter on the development board (gate 2).
2. **First P4 prototype:** the internal daughterboard on a short FPC. DSI
   over a few centimetres of FPC is how displays are connected, so it is
   safe. The internal screen stays on the i80 bus, so the DSI port is
   free for HDMI.
3. **Later:** once it works, decide whether to move it onto the main board
   or keep the daughterboard (also handy for a different enclosure).

## 32-bit systems, one by one

The problem is always the same: the emulators that are fast on cheap
hardware translate the guest CPU into native code (dynarec), and they have
no backend for 32-bit RISC-V.

There is no single answer for "32-bit": each system has its own emulator
and its own obstacle (a missing dynarec, ROM size, a second CPU), so each
one is a small project evaluated on its own, with the same three steps:

1. **Port** the emulator to the P4 development board, in its simplest
   version that runs in C.
2. **Measure** frame rate and CPU load on 2–3 reference games, the same
   way `emu_check.py` does on the S3.
3. **Decide:** good as is; can be optimised (second core, frameskip); or
   needs a dynarec (months), in which case it is dropped or postponed.

Order, from most to least likely: Sega CD → CPS1 → CPS2 → GBA → 32X. If
the first two go badly, the others are not worth trying.

| System | Guest hardware | Existing emulator on RV32 | Verdict |
|:---|:---|:---|:-:|
| **Sega CD** | Mega Drive + a second 68000 at 12.5 MHz, CD audio and ADPCM | the Genesis core already runs here (gwenesis: 68K 5.5 + Z80 3.1 + VDP 11.3 ms per drawn frame on the S3); the second 68000 fits on the P4's second core; CD images stream from the SD easily | 🟡 likely |
| **Capcom CPS1** | one 68000 at 10 MHz + Z80, ROM sets of a few MB | C 68000 cores work (no dynarec needed); ROMs fit in PSRAM | 🟡 likely |
| **Capcom CPS2** | as CPS1 plus QSound, encrypted ROMs | same CPU load as CPS1, but several games' ROM sets are larger than the 32 MB PSRAM | 🟡 the smaller sets only |
| **Game Boy Advance** | ARM7 at 16.78 MHz | gpSP has dynarecs for ARM, ARM64, x86 and MIPS only, and an interpreter for everything else ([gpSP](https://github.com/libretro/gpsp)) | 🟡 uncertain: interpreter speed to measure first; full speed may need a RISC-V backend (months of work) |
| **Sega 32X** | two SH-2 at 23 MHz + the Mega Drive | PicoDrive's SH-2 dynarec has a RISC-V backend, but for 64-bit RV64, not the P4's RV32 ([PicoDrive](https://github.com/notaz/picodrive)) | 🔴 unlikely, unless that backend is ported to RV32 |

**First measurement of the study:** gpSP's interpreter and the Sega CD
core on the P4 dev board. Those two numbers decide whether "32-bit" on the
P4 means a handful of systems or most of them.

## Two chips, two firmwares

The console runs **two binaries** on two chips that talk to each other all
the time.

```
┌──────────────────────── ESP32-P4 (our firmware) ────────────────────────┐
│ retro-go launcher + emulators                                           │
│ lwIP network stack · Bluedroid Bluetooth host (HID host for controllers)│
│ esp_hosted + esp_wifi_remote: Wi-Fi calls look local (esp_wifi_*)       │
└───────────────┬─────────────────────────────────────────────────────────┘
                │ SDIO (4-bit, 40 MHz) or SPI  ·  RESET line  ·  UART pads
┌───────────────┴──────── radio chip (Espressif firmware) ────────────────┐
│ ESP-Hosted slave: Wi-Fi driver + Bluetooth controller (HCI over VHCI)   │
└─────────────────────────────────────────────────────────────────────────┘
```

- **The P4 binary** is the one we develop every day: retro-go and the
  emulators, as today. It includes the `esp_hosted` component, so
  `esp_wifi_connect()` and the rest of the Wi-Fi API work as on a chip with
  a radio; the call is forwarded to the radio chip. The network stack and
  the Bluetooth host stack run on the P4.
- **The radio chip binary** is Espressif's **ESP-Hosted slave** firmware
  (from `esp-hosted-mcu/slave`). It holds only the Wi-Fi driver and the
  Bluetooth controller, and it barely changes: we build it once, pinned to
  the same ESP-Hosted version as the P4 side
  ([esp-hosted-mcu](https://github.com/espressif/esp-hosted-mcu)).
- **How they talk:** Wi-Fi as remote procedure calls plus network packets,
  Bluetooth as standard HCI packets, all over one SDIO (or SPI) link. The
  P4 also drives the radio chip's reset line, so it can restart it or
  power it down while a game does not need wireless.
- **During development:** the radio chip is flashed once through its UART
  pads; after that only the P4 is flashed, over USB as today. Espressif's
  ESP32-P4 development board already carries a C6 wired this way, so the
  study starts without any board design.
- **Updates in the field:** the P4 can push a new slave firmware to the
  radio chip over the same link; the UART pads stay on the PCB as a
  fallback.

### Which radio chip

| Radio chip | Wi-Fi | Bluetooth | Link to the P4 | Controllers |
|:---|:---|:---|:---|:---|
| **ESP32-C6** | Wi-Fi 6, 2.4 GHz | BLE 5 only | SDIO | Xbox Series pads, BLE-mode pads. **Not** DualShock 4 / DualSense / Switch Pro |
| **ESP32 (original)** | Wi-Fi 4 | **Bluetooth Classic + BLE** | SPI or SDIO | also DualShock 4, DualSense, Switch Pro, most 8BitDo pads |

Espressif ships an example of a P4 using Bluetooth Classic through an
original ESP32 over SPI
([esp_hosted examples](https://components.espressif.com/components/espressif/esp_hosted)).
**Recommendation:** the original ESP32, since controller compatibility is
a requirement and Wi-Fi 6 is not. Known issue to watch on the C6 path:
BLE LE Secure Connections pairing fails on P4 + C6 over SDIO today
([issue #241](https://github.com/espressif/esp-hosted-mcu/issues/241)).

## What changes on the console

| Area | Change |
|:---|:---|
| MCU | ESP32-S3 → ESP32-P4 + radio chip (module with antenna) |
| Display | **stays**: the P4's i80 interface drives the same ILI9488 panel, so the enclosure window stays |
| HDMI | new: LT8912B + HDMI connector (Mini or Micro HDMI for the enclosure) |
| Audio | I2S class-D amplifier with DAC, as in [Remediation](/docs/remediation/audio) |
| Controllers | wireless through the radio chip, wired through the P4's USB host |
| Power | the IP5306 + SY8089 chain can stay; the radio chip is powered down when unused |
| Firmware | retro-go board layer ported to the P4 (display, input, audio, SD); ESP-IDF supports the P4, retro-go's own P4 support to check |
| Enclosure | openings for HDMI and USB host |

## Study plan with gates

Each gate is a measurement on a development board, before any PCB work.

| Gate | Measure | Continue if |
|:---|:---|:---|
| 1 | retro-go NES + SNES on the P4 dev board | SNES draws more frames than on the S3 |
| 2 | HDMI 720p through an LT8912B adapter, PPA scaling | stable picture at 60 Hz with an emulator running |
| 3 | gpSP interpreter and Sega CD frame rates | decides the 32-bit list |
| 4 | a DualShock 4 through an original ESP32 over ESP-Hosted, a BLE pad through the C6 | pairing and input latency acceptable |

## Time

| Phase | Estimate |
|:---|:---|
| Gates 1–4 on development boards | 6–8 weeks |
| Schematic + PCB (P4, radio chip, LT8912B, HDMI) | 5–7 weeks |
| Fabrication and first-article bring-up | 3–4 weeks |
| **Total** | **~4–5 months** |

## Cost

| Item | Estimate |
|:---|:---|
| Development boards (P4 dev board with C6, LT8912B adapter, an ESP32 module) | ~$80–150 |
| BOM delta per console | ~+$12–18 (P4, radio module, LT8912B, HDMI connector) on today's ~$40 PCBA |
| Battery life | close to today, the radio chip off when unused |

## Risks

- The ceiling stays below the requirements: PS1 and N64 never arrive, so a
  Linux board is still needed later.
- The 32-bit list depends on two measurements (gate 3), and the best case
  for GBA and 32X is a dynarec port that takes months.
- HDMI and DSI are high-speed pairs, new for this PCB.
- The P4 is young: chip revision, drivers and ESP-Hosted still move.

**When it makes sense:** if PS1 and N64 can wait, this plan gets HDMI and
wireless controllers while keeping the display, the enclosure and the
retro-go work.

## Sources

Checked on 2026-09-26.

- [esp_lcd_lt8912b — Espressif Component Registry](https://components.espressif.com/components/espressif/esp_lcd_lt8912b)
- [ESP-FAQ: LCD and HDMI on the ESP32-P4](https://docs.espressif.com/projects/esp-faq/en/latest/software-framework/peripherals/lcd.html)
- [Olimex LT8912B adapter for the ESP32-P4 DevKit](https://www.cnx-software.com/2025/12/04/olimex-lt8912b-based-mipi-hdmi-adapter-board-adds-hdmi-output-to-the-esp32-p4-devkit-board/)
- [ESP-HDMI-Bridge](https://oshwlab.com/hawaii0707/esp-hdmi-bridge)
- [ESP32-P4 chip revision v1.3 datasheet](https://documentation.espressif.com/esp32-p4-chip-revision-v1.3_datasheet_en.html)
- [esp-hosted-mcu](https://github.com/espressif/esp-hosted-mcu)
- [esp_hosted component and examples](https://components.espressif.com/components/espressif/esp_hosted)
- [esp-hosted-mcu issue #241: LE Secure Connections pairing on P4 + C6](https://github.com/espressif/esp-hosted-mcu/issues/241)
- [gpSP](https://github.com/libretro/gpsp)
- [PicoDrive](https://github.com/notaz/picodrive)
