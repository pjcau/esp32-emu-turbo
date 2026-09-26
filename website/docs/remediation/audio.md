---
id: audio
title: Audio
sidebar_position: 1
---

# Audio

The audio path today is GPIO 17 (PDM) → C22 → PAM8403 → 28 mm speaker. The
PDM carrier is audible as hiss, so the first articles are being fixed by
hand. Those fixes should end up in the design instead of staying as bench
rework.

| Fix | Applied today | Proposal |
|:---|:---|:---|
| **R38 RC filter**: 1 kΩ in series + 10 nF to GND at the PAM8403 input (C22 / `PAM_IN_AC`) | by hand, article 0004 (rework sheet from 2026-09-12) | Bench-test 22 nF (cut-off ≈ 7 kHz), since 10 nF reduced the hiss but did not remove it. Record the final values, then either put the RC in the schematic or drop the whole chain on the respin (next row). |
| **Replace the PDM chain** | — | Respin: an I2S class-D amplifier with integrated DAC instead of PDM → RC → PAM8403. See [why audio stays on the main chip](/docs/software/snes-optimization#audio-no-coprocessor). |
| **PDM channel off when silent** | firmware, done (`pdm.c`) | Keep: an enabled channel emits its carrier even at volume 0. |
| **Default volume 0** | firmware (`RG_AUDIO_DEFAULT_VOLUME`) | Raise it once the hiss is gone. On the bench the console command `volume N` (`board_ctl.py raw "volume 40"`) sets it without the menu. |
| **Higher PDM carrier** | — | Estimate, to try: raise the PDM up-sampling so the carrier sits further above the RC cut-off; costs nothing in hardware. |

**Proof:** the same speaker and volume before and after each change,
recorded with the bring-up tone and one game.
