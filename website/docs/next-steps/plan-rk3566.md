---
id: plan-rk3566
title: "Plan B: Rockchip RK3566"
sidebar_position: 5
---

# Plan B: Rockchip RK3566

Move to a Linux application processor: an RK3566 (4 × Cortex-A55 at
1.8 GHz, Mali-G52 GPU) on a compute module (for example the Radxa CM3), on
a carrier board of our own design. The same chip powers commercial
handhelds of the Anbernic RG353 class, which is the proof that the
requirements can be met together.

All costs and durations on this page are **estimates** for one developer
working with Claude, to be refined after the study phase.

## Requirements

| Requirement | Result | Notes |
|:---|:-:|:---|
| MAME | 🟢 | MAME 2003-Plus / FinalBurn Neo: classic boards through CPS2 and Neo Geo |
| 16-bit | 🟢 | all, full speed |
| 32-bit | 🟢 | GBA, 32X, Sega CD, Saturn partly |
| PlayStation | 🟢 | full speed (dynarec on ARM) |
| Nintendo 64 | 🟡 | much of the library playable, the heaviest games are not |
| HDMI | 🟢 | built into the SoC |
| Wireless controllers | 🟢 | Wi-Fi + Bluetooth Classic and BLE on the module: PlayStation, Switch Pro, Xbox and 8BitDo pads |

**Six of six requirements**, N64 partly.

## What changes

| Area | Change |
|:---|:---|
| Processor | ESP32-S3 → RK3566 compute module on a carrier board; no DDR routing on our PCB |
| Display | **changes**: the ILI9488 8080 panel is not supported; a MIPI-DSI panel of similar size replaces it |
| HDMI | connector routed from the module. The built-in DSI screen stays the default; Linux (DRM/KMS) sees the cable plug and unplug, and the frontend moves the picture to the TV and back, as existing handheld distributions already do |
| Audio | I2S class-D amplifier (or the module's codec output) to the speaker |
| Power | **changes**: a 3–4 A charger / boost for a 2–3 W SoC replaces the IP5306; thermal pad or small heatsink |
| Software | **changes completely**: a Linux distribution (a ROCKNIX / Buildroot port, or the module vendor's image) with RetroArch + EmulationStation. The work is a device tree for the carrier (display, buttons, audio, power), not emulator code. retro-go is retired |
| Enclosure | **redesign**: new display, thicker for the module and thermal path |
| Boot | 10–20 s instead of instant-on |

## Time

| Phase | Estimate |
|:---|:---|
| Study on an RK3566 board: N64 / PS1 measured, controllers, power draw | 3–4 weeks |
| Linux bring-up on the module: display, buttons, audio, power | 6–10 weeks |
| Carrier board schematic + PCB | 6–8 weeks |
| Fabrication and first-article bring-up | 3–4 weeks |
| New enclosure | 3–4 weeks (in parallel) |
| **Total** | **~6–8 months** |

## Cost

| Item | Estimate |
|:---|:---|
| Development kit (module + IO board), or an RG353-class handheld as a reference | ~$60–120 |
| BOM per console | ~$70–100 (module ~$30–60 by RAM size, DSI panel, PMIC, carrier PCBA) |
| Battery life | ~5–6 h on the 5000 mAh cell |

## Risks

- Carrier boards for compute modules are a harder PCB (dense connectors,
  high-speed DSI / HDMI pairs) than the current board.
- Linux board support for a custom carrier is the longest task; depending
  on a community distribution means following its release cycle.
- The module's supply and price are set by the vendor.

**When it makes sense:** the best balance for a handheld that must run PS1
and most of the N64 library, with long battery life.
