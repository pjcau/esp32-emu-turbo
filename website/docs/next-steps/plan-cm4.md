---
id: plan-cm4
title: "Plan C: Raspberry Pi CM4"
sidebar_position: 6
---

# Plan C: Raspberry Pi CM4

Move to a Linux application processor with the largest software ecosystem:
a Raspberry Pi Compute Module 4 (4 × Cortex-A72 at 1.5 GHz, VideoCore VI
GPU, Wi-Fi and Bluetooth on the module) on a carrier board of our own
design. Raspberry Pi states CM4 production until at least 2034.

All costs and durations on this page are **estimates** for one developer
working with Claude, to be refined after the study phase.

## Requirements

| Requirement | Result | Notes |
|:---|:-:|:---|
| MAME | 🟢 | MAME 2003-Plus / FinalBurn Neo, through CPS2 and Neo Geo |
| 16-bit | 🟢 | all, full speed |
| 32-bit | 🟢 | GBA, 32X, Sega CD, Saturn partly |
| PlayStation | 🟢 | full speed |
| Nintendo 64 | 🟡 | much of the library playable, a bit ahead of the RK3566; the CM5 would be the upgrade for the heaviest games |
| HDMI | 🟢 | two HDMI ports on the module |
| Wireless controllers | 🟢 | Wi-Fi 5 + Bluetooth 5.0 (Classic and BLE) on the module |

**Six of six requirements**, N64 partly.

## What changes

| Area | Change |
|:---|:---|
| Processor | ESP32-S3 → CM4 (wireless variant) on a carrier board, two high-density board-to-board connectors |
| Display | **changes**: MIPI-DSI or DPI (RGB) panel; the Pi supports both through standard overlays |
| HDMI | connector routed from the module. The built-in DSI screen stays the default; Linux (DRM/KMS) sees the cable plug and unplug, and the frontend moves the picture to the TV and back, as existing handheld distributions already do |
| Audio | **needs the I2S amplifier**: the CM4 has no analog audio output |
| Power | **changes**: 5 V at up to ~3 A under load, so a larger charger / boost than the IP5306; heatsink or thermal pad |
| Software | **changes completely**: Raspberry Pi OS based distribution (RetroPie, Batocera or Lakka) with RetroArch + EmulationStation; carrier support is mostly device-tree overlays, the best-documented path of the three |
| Enclosure | **redesign**: new display, thicker and with a thermal path |
| Boot | 10–20 s instead of instant-on |

## Time

| Phase | Estimate |
|:---|:---|
| Study on a CM4 + IO board: N64 / PS1 measured, controllers, power draw | 2–3 weeks |
| Linux integration: display overlay, buttons, I2S audio, power | 4–6 weeks |
| Carrier board schematic + PCB | 6–8 weeks |
| Fabrication and first-article bring-up | 3–4 weeks |
| New enclosure | 3–4 weeks (in parallel) |
| **Total** | **~5–7 months** |

## Cost

| Item | Estimate |
|:---|:---|
| Development kit (CM4 + IO board) | ~$80–120 |
| BOM per console | ~$80–110 (CM4 with wireless ~$45–65 by RAM / eMMC, DSI panel, power stage, carrier PCBA) |
| Battery life | ~4–5 h on the 5000 mAh cell (higher draw than the RK3566) |

## Risks

- Higher power and heat than the RK3566: shorter battery life, a thermal
  path in the enclosure.
- CM4 prices and stock have swung in the past.
- Same PCB step-up as Plan B (dense connectors, DSI / HDMI pairs).

**When it makes sense:** the fastest route to a working Linux handheld, with
the most documentation, and a pin-compatible path to a faster module
later.
