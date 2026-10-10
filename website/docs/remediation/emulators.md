---
id: emulators
title: Emulators
sidebar_position: 2
---

# Emulators

## Cores measured on the board (2026-09-26/27)

The cores that had never run on the board have been measured; see the
[firmware table](/docs/software/emulators)
for the full list.

| Core | Result | What it took |
|:---|:---|:---|
| Atari 2600 (Stella) | ✅ 60 fps, 68% busy (Halo 2600, 2026-10-03) | brought back 2026-10-03 after the 2026-09-29 removal |
| Duke Nukem 3D | ✅ playable, 48–53 fps in E1L1, menus 73 fps | four fixes: an ODROID-GO audio conversion overwrote FatFs (crash), keypad names aliased RETURN (no menu input), the game drew into the frame being sent (broken menus), a non-volatile spin-wait hung the level start; audio moved to 32 kHz |
| ~~MSX (fMSX)~~ | removed 2026-09-29 | not needed; the partition went to GBA (`gbsp`) |
| Atari Lynx (Handy) | ✅ 56-60 fps on 5 PD demos (2026-10-03) | brought back 2026-10-03; BS93 loader and silent-frame divide by zero fixed |
| ~~Game & Watch~~ | removed 2026-09-29: not needed | core, launcher tab and art deleted |

## Known bugs

| Bug | Measured | Next step |
|:---|:---|:---|
| ~~DOOM memory leak~~ | two causes, both closed (board, 2026-10-09). During play the purgeable lump cache fills to a 2.8 MB plateau by design (the 1.5 MB reserve, fork `6f8cc892`, purges it). A real leak was per level load: `P_CheckForZDoomNodes` / `P_GetNodesVersion` locked the NODES and SSECTORS lumps to read a 4-byte magic, pinning them for the rest of the run (+71..+218 KB a map; about 3 MB over Freedoom's 36 maps, more than the 2.28 MB free). Fixed in fork `c7c79ae6`: `static` identical on every second visit of E1M1–E1M8 | none |
| ~~Super Mario Kart at 57 fps~~ | fixed 2026-09-28: 57–62, mostly 60 | the S-DSP mix moved to core 1 (the DSP-1 was only ~2% of the frame) |
| ~~Neo Geo Pocket near the limit~~ | fixed 2026-10-09 (fork `3b3cb6b0`): ~29 drawn was the app's frameskip 1, not the CPU; now 45–61 drawn in Metal Slug's fights, 60 on quiet screens. Board profile: TLCS-900H 9.0 ms, Z80 2.9, graphics 3.2 of 16.6 | the interpreter's register-file double indirection, if more is needed |

## Audio rates (2026-09-27)

Every app now feeds the speaker at 32000 Hz: the PDM
sink derives its clocks from rate / 100 and other rates crackled or
ignored the volume. Moved today: DOOM (mix at 16 kHz doubled to 32 kHz,
sfx interpolated — mixing its OPL music at 32 kHz starved the sound task),
Neo Geo Pocket (chip at 16 kHz, doubled), Genesis (26633 → 32000,
resampled per frame), Duke Nukem 3D (mix at 16 kHz, doubled). See
[Audio](audio).

## Smoother picture on the cores that already reach 60

Every tested core runs at full game speed, but most draw only every other
frame.

- **Frameskip 0 on the light cores.** NES, Game Boy, GBC and PC Engine
  draw 30 fps while the CPU is 30–55% busy, so there is room to draw all
  60. It also moves the display-synchronous audio buzz from 30 Hz knocks
  to a 60 Hz hum, as on SMS ([Audio](audio)).
- **SNES audio (S-DSP) on the second core.** Frees a slice of core 0 for
  the renderer, the same move that took the Genesis from 20 to 30 drawn
  fps.

**Proof:** `scripts/emu_check.py` and `scripts/snes_bench.py`, with the
numbers copied into the
[firmware table](/docs/software/emulators).
