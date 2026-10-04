---
id: index
title: Next Steps
slug: /next-steps
---

# Next Steps

What was studied and done after the first emulators ran, and what could come
next. Each page starts with where it stands. What is still needed to close
the current console is under [Remediation](/docs/remediation).

## Where we are (2026-10-04)

| Topic | State |
|:---|:---|
| Console emulators | NES, GB/GBC, Master System, Game Gear, PC Engine, Mega Drive, SNES, Neo Geo Pocket, Atari 2600 and Lynx run at full speed (56–60 fps); the GBA at 56–60 in play on its dynarec. Table: [Software overview](/docs/software) |
| Arcade (`mame-go`) | 8-bit boards at full speed; Neo Geo, CPS1 and Sega System 16 near full speed with a third of the frames drawn: [Arcade (MAME)](/docs/next-steps/arcade) |
| 60 drawn frames on the 68000 arcade games | **not reached, not in sight on this hardware**; work stopped on 2026-10-04: [Arcade 60 fps plan](/docs/next-steps/arcade-60fps-plan) |
| JIT | GBA finished and in use; 68000 finished, exact and switched off (slower than the interpreter): [JIT plan](/docs/next-steps/jit-plan) |
| Native games | DOOM, Duke Nukem 3D, Wolfenstein 3D, Quake, OpenTyrian, OutRun (Cannonball), Arcade 3D Racing |
| Flash | full: 64 KB left of 16 MB. A new app means removing one, or [Plan D](/docs/next-steps/plan-esp32-s3-n32r16v) |

**What it took, in short.** Emulators were brought up one by one and measured
on the board (September); the SNES needed its own renderer work; the GBA
needed a dynarec; the arcade games needed memory work first (graphics paged
from the card, ROM regions in flash) and then the speed work of the Arcade
60 fps plan. Along the way every app got a loading percentage, save states
were fixed on the arcade boards, and SD reads became about twice as fast for
large games.

**What could come next**, none of it started: the Atari 7800 (ProSystem, a
small core) and the 5200; tuning System 16; the CPS1's renderer on the second
core; and the hardware steps below.

## Studies

Every figure on these pages comes from a measurement (`scripts/emu_check.py`,
`scripts/snes_bench.py`, the serial stats line), and new work keeps that
rule. The feasibility tiers are estimates until a port is measured.

| Page | What it covers |
|:---|:---|
| [More Systems](/docs/next-steps/more-systems) | which consoles fit the ESP32-S3, up to the PlayStation |
| [Arcade (MAME)](/docs/next-steps/arcade) | which arcade boards run, how they fit, and where MAME stops |
| [Arcade 60 fps plan](/docs/next-steps/arcade-60fps-plan) | the speed work on the 68000 arcade games: where it stands, what was done, what is left |
| [JIT plan](/docs/next-steps/jit-plan) | the dynarecs: GBA in use, 68000 on hold |
| [Next Console (v4)](/docs/next-steps/v4-platform) | PS1, N64, HDMI and wireless controllers: which platform, in one step or several |
| [Plan A: ESP32-P4 + ESP32-C6](/docs/next-steps/plan-esp32-p4) | stay on Espressif: changes, time, cost, which requirements it meets |
| [Plan B: Rockchip RK3566](/docs/next-steps/plan-rk3566) | Linux module, the chip of RG353-class handhelds |
| [Plan C: Raspberry Pi CM4](/docs/next-steps/plan-cm4) | Linux module with the largest software ecosystem |
| [Plan D: ESP32-S3 with 32 MB flash](/docs/next-steps/plan-esp32-s3-n32r16v) | same board, module swap to 32 MB flash / 16 MB PSRAM: every case, system by system |

## Suggested order

1. Close [Remediation](/docs/remediation) first: those bugs are on the board
   today and affect every game (the buried Wi-Fi antenna is the first).
2. Decide the hardware step: [Plan D](/docs/next-steps/plan-esp32-s3-n32r16v)
   (same board, 32 MB flash and 16 MB PSRAM) fits the same respin as the
   antenna fix and removes today's memory limits, not the frame rates.
3. On the current board, software in the order of what the user plays.
4. In parallel, the v4 study ([Next Console (v4)](/docs/next-steps/v4-platform)):
   it decides the platform for PS1, N64, HDMI and wireless controllers.
