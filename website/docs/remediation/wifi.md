---
id: wifi
title: Wi-Fi
sidebar_position: 5
---

# Wi-Fi

The Wi-Fi works, but it is almost deaf on this board. The cause is the board
layout, not the firmware.

## What was measured (first article, 2026-09-29)

| Test | Result |
|:---|:---|
| Signal at the desk (same FRITZ!Box the PC sees at 72 %) | RSSI **−87 to −91 dBm** |
| Ping to the router | 85–2000 ms |
| Scan from the board | 0 access points found |
| Launcher file server (`webui.c`), 20 KB file | upload 19 KB/s, download 4.4 KB/s: slower than the USB console (190–490 KB/s) |
| Same, 1 MB file | times out |

## Why: the antenna is buried

U1 (ESP32-S3-WROOM-1) has a printed antenna at one end of the module.
Espressif's layout rule for it: the antenna over the board edge (or beyond
it), **no copper on any layer under it**, and about 15 mm of clearance
around it. On this board:

- U1 sits on the bottom side at (80, 27.5) mm, with the antenna end about
  **15 mm inside the board edge** (antenna at Y ≈ 14.75–20.75 mm, edge at
  Y = 0).
- The **In1.Cu GND and In2.Cu +3V3 planes cover the whole board, antenna
  included**: the antenna radiates into two copper sheets a fraction of a
  millimetre away.
- The SD card lines (SD_MOSI, SD_MISO, SD_CLK) run across the antenna end on
  the bottom layer.

**The verification gate missed it.** `verify_antenna_keepout.py` only checks a
2 mm strip beyond the module and counts "GND plane present on In1.Cu" as a
pass. It has to check every layer under the antenna itself and fail on any
copper there.

## What works today

- Wi-Fi is **off by default** (the `Enable` switch in
  `/sd/retro-go/config/wifi.json`, or the options menu). It costs internal
  RAM and power, and gives little on this board.
- The console commands `wifi on|off|scan|status` (`board_ctl.py`) are for
  bench checks.
- Small files over the web file server work with the console right next to
  the router. For ROMs and firmware, use the USB cable
  ([`sd_update.py --console`](/docs/software/firmware#firmware-update-from-the-sd-card-2026-09-28))
  or a card reader.

## Fixes

| Fix | Where | Proposal |
|:---|:---|:---|
| **Antenna free of copper** | respin, **top priority for the next hardware release** (decision 2026-09-29) | Move U1 so the antenna overhangs the board edge, or cut an all-layer keep-out under and around it (In1 GND and In2 +3V3 zones, tracks, pours). Leave the board clearance Espressif asks for. |
| **Reroute the SD lines** | respin | SD_MOSI/MISO/CLK away from the antenna end; no track under or next to it on any layer. |
| **Gate that sees it** | same respin | `verify_antenna_keepout.py` fails on any copper, on any layer, under the antenna area of the footprint, plus a mutation test that plants a plane under it. Without this, the next layout can bury it again. |
| **Enclosure and display** | respin + enclosure | No metal, screw or display panel over the antenna; check the shell wall in front of it. |
| **External antenna** (option, to evaluate) | v3.1 build | ESP32-S3-WROOM-1U-N16R8: same pads and pinout, no printed antenna, u.FL connector for an antenna on the shell. It avoids moving U1, but it is a module swap (41 pads + thermal pad), not a bench rework, and needs its stock at JLCPCB checked. |

No firmware change is needed for any of these.

**Proof:** at the same desk as the 2026-09-29 measurement, RSSI better than
−65 dBm, the scan finds the router and the neighbours' networks, and a 1 MB
upload through the web file server completes faster than the USB console.
