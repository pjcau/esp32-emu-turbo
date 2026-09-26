---
id: v4-platform
title: Next Console (v4)
sidebar_position: 3
---

# Next Console (v4)

Target requirements for the next console, beyond what the ESP32-S3 does
today:

- MAME, 16-bit and 32-bit systems
- PlayStation and Nintendo 64
- HDMI output **in addition to** the built-in screen: without a cable the
  picture stays on the screen as today; plugging the cable moves it to the
  TV, unplugging it brings it back
- Wireless controllers over Wi-Fi / Bluetooth

## PS1 and N64 decide the platform

| Requirement | ESP32-S3 (current) | ESP32-P4 + ESP32-C6 | Linux SoC (ARM + GPU) |
|:---|:-:|:-:|:-:|
| Classic MAME (Z80 / 6502) | 🟢 | 🟢 | 🟢 |
| 16-bit (SNES, MD, PCE, Neo Geo) | 🟡 SNES at the limit, no Neo Geo | 🟢 almost all (Neo Geo only up to 32 MB of ROM) | 🟢 |
| 32-bit (GBA, 32X, Sega CD, CPS2) | 🔴 | 🟡 Sega CD / CPS1 likely, GBA uncertain, 32X unlikely | 🟢 |
| **PlayStation** | 🔴 | 🔴 no RISC-V dynarec | 🟢 |
| **Nintendo 64** | 🔴 | 🔴 | 🟢 with a real GPU |
| **HDMI** | 🔴 no peripheral, only marginal experiments | 🟢 through the LT8912B DSI → HDMI bridge Espressif supports (720p) | 🟢 built in |
| **Bluetooth controllers** | 🟡 **BLE only**: recent Xbox pads work, DualShock / DualSense / Switch Pro do not | 🟢 with an original ESP32 as radio chip (Classic + BLE); 🟡 with the C6 (BLE only) | 🟢 Bluetooth Classic + BLE: all of them |
| Wi-Fi | 🟢 | 🟢 through the C6 | 🟢 |

- **No microcontroller reaches PS1 and N64.** The emulators that run them
  on cheap hardware depend on a **dynarec** (MIPS code translated to ARM
  on the fly), and the N64 also needs a **GPU** (OpenGL ES) for its 3D
  graphics. That means an ARM application processor with a GPU, running
  Linux.
- **Bluetooth is a hidden trap.** The ESP32-S3 and C6 support only BLE
  (the P4 has no radio at all), while most controllers (PlayStation,
  Switch Pro, many 8BitDo pads) use Bluetooth Classic. Only the original
  ESP32 among Espressif chips has Bluetooth Classic, which is why
  [Plan A](/docs/next-steps/plan-esp32-p4) pairs the P4 with it.
- **It has been done.** Commercial handhelds built on the Rockchip RK3566
  (the Anbernic RG353 class) have HDMI out and Wi-Fi / Bluetooth, run the
  PS1 well and much of the N64 library, on Linux with
  EmulationStation / RetroArch (distributions such as ROCKNIX).

## One step or several

| Path | Verdict |
|:---|:---|
| **A. In stages: S3 → P4 → Linux** | Not recommended. The P4 step costs a new board but reaches neither PS1 nor N64 and does not solve Bluetooth Classic; the move to Linux still has to happen, so three boards get designed instead of two. |
| **B. One jump to a Linux module** | **Recommended.** One step covers every new requirement. A **compute module** on a carrier board of our own design avoids routing DDR memory on our PCB. |

| Module | CPU / GPU | N64 | PS1 | HDMI | Wi-Fi / BT | Power (indicative) |
|:---|:---|:-:|:-:|:-:|:-:|:---|
| **Raspberry Pi CM5** | 4 × A76 2.4 GHz / VideoCore VII | 🟢 very good | 🟢 | 🟢 | 🟢 on the module | high (3–7 W) |
| **Raspberry Pi CM4** | 4 × A72 1.5 GHz / VideoCore VI | 🟡 much of the library | 🟢 | 🟢 | 🟢 on the module | medium |
| **RK3566** (e.g. Radxa CM3) | 4 × A55 1.8 GHz / Mali-G52 | 🟡 much of the library | 🟢 | 🟢 | 🟢 | low (2–3 W) |

These ratings are estimates from how the chips behave in existing
handhelds; a development board measurement confirms them before any
design work. **Recommendation:** RK3566 or CM4 for a handheld (lower power,
a proven software base for this kind of device); CM5 for the best N64 at
the cost of battery life and heat.

## What changes against the current console

- **Display:** the ILI9488 on an 8080 parallel bus is not supported by
  these SoCs; the panel becomes MIPI-DSI or RGB, so the enclosure and the
  FPC change too.
- **Power:** the IP5306 (2.1 A max) is not enough. A 3–5 A charger / PMIC
  is needed; with the same 5000 mAh cell, battery life drops to roughly
  4–6 hours. Heat needs a thermal path.
- **Software:** retro-go is not ported; an existing Linux distribution is
  used, and the work becomes integration (device tree, display, buttons,
  audio) instead of writing emulators.
- **Boot:** 10–20 s instead of instant-on.

## The three plans in detail

| | [Plan A: ESP32-P4 + C6](/docs/next-steps/plan-esp32-p4) | [Plan B: RK3566](/docs/next-steps/plan-rk3566) | [Plan C: CM4](/docs/next-steps/plan-cm4) |
|:---|:-:|:-:|:-:|
| Requirements met | 4 of 6 (32-bit partly) | 6 of 6 (N64 partly) | 6 of 6 (N64 partly) |
| PS1 / N64 | 🔴 / 🔴 | 🟢 / 🟡 | 🟢 / 🟡 |
| Keeps display, enclosure, retro-go | yes | no | no |
| Time (estimate) | ~4–5 months | ~6–8 months | ~5–7 months |
| BOM per console (estimate) | ~$52–58 | ~$70–100 | ~$80–110 |
| Battery life | like today | ~5–6 h | ~4–5 h |

## Roadmap

1. **v3 (ESP32-S3):** the current console, as built today.
2. **v3.1 (ESP32-S3):** v3 with the fixes from
   [Remediation](/docs/remediation) (audio, emulator bugs, hardware
   backlog); it stays the low-cost, instant-on 8/16-bit console.
3. **v4 study (a few weeks):** buy an RK3566 development board and a
   CM4 / CM5, and measure N64 and PS1 frame rates, power draw and
   Bluetooth controller compatibility on a set of reference games. Same
   method as with the S3: measure first, then design.
4. **v4 carrier board:** the chosen module, DSI display, HDMI, PMIC,
   buttons and I2S audio; Wi-Fi and Bluetooth come with the module.

All the new requirements arrive together at step 4, with no intermediate
boards.
