---
id: plan-esp32-s3-n32r16v
title: "Plan D: ESP32-S3 with 32 MB flash"
sidebar_position: 7
---

# Plan D: ESP32-S3 with 32 MB flash (WROOM-2 N32R16V)

The smallest possible step: keep the ESP32-S3 and everything built around
it, and swap only the module, from today's **ESP32-S3-WROOM-1-N16R8**
(16 MB flash, 8 MB PSRAM) to the **ESP32-S3-WROOM-2-N32R16V** (32 MB
octal flash, 16 MB octal PSRAM). Same chip, same firmware, same display,
same enclosure: twice the flash and twice the PSRAM.

Facts marked with a source were checked on 2026-09-28; costs and times are
**estimates**, and the speed effects are to be measured on a development
board.

## In short

- **It solves memory, not speed.** The CPU is the same dual-core LX7 at
  240 MHz, so every frame rate measured today stays where it is. What
  changes is where ROMs live: the flash is full today (firmware image
  15.86 of 16 MB) and PSRAM is the limit for Neo Geo, CPS1 and CPS2.
- **Drop-in footprint.** The WROOM-2 has the same 41 pads as the WROOM-1;
  only pads 28–30 (IO35–37) become NC, and on our board those three pads
  are already unconnected (checked on U1 in the `.kicad_pcb`). GPIO33–37
  are already taken by the octal PSRAM on today's module.
- **Only one variant is still made.** N16R8V and N32R8V are end-of-life;
  **N32R16V** is the one to design with
  ([datasheet](https://documentation.espressif.com/esp32-s3-wroom-2_datasheet_en.html)).
- **Octal flash is faster.** Game data kept in the flash partition (Neo Geo
  program, CPS1 tiles, sample ROMs) is read over 8 lines instead of 4.
- **It reaches none of the v4 requirements that need a new chip:** no
  PS1, no N64, no HDMI, no Bluetooth Classic. It is a **v3.2**, not a v4.

## The module, all the variants

| Module | Flash | PSRAM | Flash / PSRAM voltage | Status | Price (JLC/LCSC) |
|:---|:---|:---|:---|:---|:---|
| **ESP32-S3-WROOM-1-N16R8** (today, U1) | 16 MB quad | 8 MB octal | 3.3 V | active | ~$3.50 ([C2913202](https://jlcpcb.com/partdetail/3198300-ESP32_S3_WROOM_1N16R8/C2913202)) |
| ESP32-S3-WROOM-2-N16R8V | 16 MB octal | 8 MB octal | 1.8 V | **EOL** | — |
| ESP32-S3-WROOM-2-N32R8V | 32 MB octal | 8 MB octal | 1.8 V | **EOL** | — |
| **ESP32-S3-WROOM-2-N32R16V** | 32 MB octal | 16 MB octal | 1.8 V | **active** | ~$8.30 ([LCSC C42417293](https://www.lcsc.com/product-detail/C42417293.html), out of stock at LCSC on 2026-09-28; JLC assembly listing [C9900162944](https://jlcpcb.com/partdetail/C9900162944)) |

**Stock is the first thing to check**: a design on a module that JLC
cannot place is not a design.

### What the module change touches on the board

| Point | Today (WROOM-1 N16R8) | WROOM-2 N32R16V | Action |
|:---|:---|:---|:---|
| Footprint | 41 pads, 18 × 25.5 mm | same pads and size | none: pads 28–30 are NC on the WROOM-2 and unconnected on our PCB |
| GPIO33–37 | used by the octal PSRAM | used by octal flash + PSRAM | none: already reserved (`board_config.h`) |
| Flash voltage | 3.3 V | 1.8 V, set inside the module by eFuse (`VDD_SPI_FORCE`) | none on the carrier: nothing of ours sits on VDD_SPI |
| GPIO45 (BTN_L) | VDD_SPI strap pin, sampled at boot | ignored, because the eFuse fixes VDD_SPI | none; the eFuse even removes a boot-time dependency on the button |
| Ambient temperature | up to 85 °C | **up to 65 °C** (85 °C with PSRAM ECC, which costs 1/16 of the PSRAM: 15 MB usable) | measure the module temperature inside the closed enclosure while charging and playing |
| Firmware | `sdkconfig`: quad flash, octal PSRAM | octal flash (OPI), 32 MB, octal PSRAM 16 MB | new retro-go target variant; partition table for 32 MB |

## Every case, system by system

Speed is the same as on today's board. Only the **memory** column
changes.

| Case | Today (N16R8) | With N32R16V | Verdict |
|:---|:---|:---|:-:|
| **Adding apps** (new cores, ports) | flash full (15.86 / 16 MB): a new app needs another removed, or the SD "bootstrap" flasher | ~16 MB more flash: all current apps + room for several more, no bootstrap needed | 🟢 solved |
| **8-bit / 16-bit consoles** (NES … Genesis, SNES) | full speed; ROMs in 8 MB PSRAM | unchanged (the CPU is the limit, not memory) | ⚪ no change |
| **SNES special chips** (SuperFX, SA-1, DSP-1) | Star Fox uses the whole 6 MB ROM buffer | room for larger ROM buffers; speed unchanged | ⚪ small gain |
| **Classic MAME** (Z80 / 6502 / 8080) | 60 fps | unchanged | ⚪ no change |
| **68000 arcade** (Blood Bros., Aero Fighters) | tile cache + 4 MB `mamerom` partition | graphics fully decoded in PSRAM (no tile cache misses) | 🟢 small speed gain |
| **Capcom CPS1** | graphics streamed from the zip to flash + PSRAM (SF2 fits) | the whole set in flash + PSRAM, simpler loading | 🟢 easier |
| **Neo Geo** (up to ~50 MB) | sprites and big sample ROMs paged from the SD, caches of 0.9–2.3 MB | larger `mamerom` partition (samples + program in flash, no sample paging) and a sprite cache of ~8–10 MB: far fewer SD reads | 🟢 better; still paged |
| **Neo Geo** (over ~50 MB, KOF '98 class) | no | sprites still on the SD; possible if the CPU keeps up | 🟡 memory ok, speed limit |
| **CPS2** (19XX, SSF2, SF Alpha, ~20–25 MB) | not ported; 8 MB PSRAM too small without heavy paging | decrypted program (both copies) + QSound samples in flash, graphics in flash + PSRAM cache | 🟡 memory ok, the CPU decides |
| **Sega CD** | no | memory fine (the CD streams from SD), but a second 68000 at 12.5 MHz on top of a Genesis core already at BUSY 94% | 🔴 CPU |
| **GBA, 32X** | no | no: ARM7 / two SH-2 without a dynarec for Xtensa | 🔴 CPU |
| **PlayStation, N64** | no | no | 🔴 |
| **HDMI** | no | no: the S3 has no DSI or HDMI | 🔴 |
| **Bluetooth controllers** | BLE only | BLE only (same chip) | 🟡 unchanged |
| **Wi-Fi** | yes | yes | 🟢 |

## The one catch: a 32 MB address window

The ESP32-S3 sees external memory through a **32 MB virtual window that
flash and PSRAM share**: "the 32 MB virtual addresses are shared with
flash instructions and rodata"
([ESP-IDF, external RAM](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/external-ram.html)).

| Mapped at the same time | Today | N32R16V |
|:---|---:|---:|
| PSRAM | 8 MB | 16 MB |
| Running app (code + rodata) | ~2–3 MB | ~2–3 MB |
| `mamerom` game data, memory-mapped | 4 MB | **up to ~12 MB** |
| **Total, of 32 MB** | ~15 MB | ~31 MB |

So the 32 MB of flash **cannot all be mapped at once**. That is fine for
how the emulators work (one game at a time, mapped when it starts, as
`mame-go` already does), but the budget above is the ceiling: a 12 MB
game-data window next to 16 MB of PSRAM. First thing to confirm on the
development board.

## Speed: what could still improve

- **Octal flash.** Data read straight from the flash partition (Neo Geo
  program, CPS1 tiles, samples) moves over 8 data lines instead of 4. The
  flash and the PSRAM share the same memory bus on the S3, so the real gain
  is to be measured, not assumed.
- **Fewer cache misses.** More PSRAM means larger sprite and tile caches:
  less SD traffic on scene changes in Neo Geo, no tile cache at all on the
  68000 boards.
- **No change** for anything CPU-bound: SNES drawn frames, Neo Geo in play
  (39 emulated fps on Metal Slug 2), DOOM, Quake.

## What changes on the console

| Area | Change |
|:---|:---|
| Module | U1 → ESP32-S3-WROOM-2-N32R16V (same footprint) |
| PCB | none expected; regenerate BOM/CPL, re-run the full gate suite and `/pcba-readiness` |
| Firmware | retro-go target variant: octal flash, 32 MB partition table (larger app partitions + a larger `mamerom`), 16 MB PSRAM |
| Display, audio, power, enclosure | unchanged |

## Study plan with gates

| Gate | Measure | Continue if |
|:---|:---|:---|
| 1 | Stock: JLC assembly availability of N32R16V | placeable in quantity |
| 2 | Retro-go on an N32R16V dev board (e.g. an ESP32-S3 board with that module): boot, octal flash + 16 MB PSRAM, full image flashed | every app boots, `emu_check.py` numbers equal to today's |
| 3 | 32 MB window: 16 MB PSRAM + a 12 MB `mamerom` mapping at the same time | maps without errors |
| 4 | Neo Geo (Metal Slug 2) and CPS1 (SF2) with everything in flash + PSRAM | same or better fps, no SD paging for samples |
| 5 | Module temperature in the closed enclosure, charging and playing | below 65 °C with margin, or enable PSRAM ECC |

## Time and cost

| Item | Estimate |
|:---|:---|
| Gates 1–5 on a development board | 1–2 weeks |
| BOM change + full gate suite + JLC order | 1 week |
| Firmware target variant + partition table | a few days |
| **Total** | **~3–4 weeks** |
| BOM delta per console | **~+$5** (module ~$8.30 instead of ~$3.50) |
| Development board | ~$15–30 |
| Battery life | like today |

## When it makes sense

If the goal is **more games on the current console** (more apps, Neo Geo
and CPS1 with less paging, a chance at CPS2) and PS1, N64, HDMI and
Bluetooth Classic can wait. It is the cheapest and fastest plan by far and
throws nothing away, but it does **not** replace a v4: it is a v3.2 on the
same road as [Remediation](/docs/remediation), and a Linux board (Plans B
or C) is still needed for the v4 requirements.

## Sources

Checked on 2026-09-28.

- [ESP32-S3-WROOM-2 datasheet](https://documentation.espressif.com/esp32-s3-wroom-2_datasheet_en.html): variants, EOL status, 1.8 V VDD_SPI by eFuse, GPIO33–37, 65 °C / ECC
- [ESP-IDF: ESP32-S3 external RAM](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/external-ram.html): 32 MB virtual window shared with flash
- [LCSC C42417293](https://www.lcsc.com/product-detail/C42417293.html) and [JLCPCB C9900162944](https://jlcpcb.com/partdetail/C9900162944): N32R16V price and stock
- [JLCPCB C2913202](https://jlcpcb.com/partdetail/3198300-ESP32_S3_WROOM_1N16R8/C2913202): today's module
