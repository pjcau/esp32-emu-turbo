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
| **R38 RC filter**: 1 kΩ in series + 10 nF to GND at the PAM8403 input (C22 / `PAM_IN_AC`) | by hand, article 0004 (rework sheet from 2026-09-12) | Bench-test 22 nF (cut-off ≈ 7 kHz), since 10 nF reduced the hiss but did not remove it. Two 10 nF give 20 nF (≈ 8 kHz) only **in parallel**: stack the second one on top of the first, same two ends; in series they give 5 nF. Record the final values, then either put the RC in the schematic or drop the whole chain on the respin (next row). |
| **Replace the PDM chain** | — | Respin: an I2S class-D amplifier with integrated DAC instead of PDM → RC → PAM8403. See [why audio stays on the main chip](/docs/software/snes-optimization#audio-no-coprocessor). |
| **PDM channel off when silent** | firmware, done (`pdm.c`) | Keep: an enabled channel emits its carrier even at volume 0. |
| **Default volume 0** | firmware (`RG_AUDIO_DEFAULT_VOLUME`) | Raise it once the hiss is gone. On the bench the console command `volume N` (`board_ctl.py raw "volume 40"`) sets it without the menu. |
| **32 kHz in every app** | firmware, done (2026-09-26/27) | Keep: at other rates the PDM DAC-mode clocks (rate / 100) misbehave — mame-go ignored the volume at 22050, PC Engine and DOOM crackled. Cores whose chip runs at another rate resample (Genesis) or double a 16 kHz mix (Duke Nukem 3D, Neo Geo Pocket). |
| **Silence while an app loads** | firmware, done 2026-09-27 (`pdm.c` idle check) | The channel now starts on the first samples and switches off after 100 ms without any (an app loading, the hourglass): an enabled channel with nothing to play squealed. The DMA `auto_clear` option was tried first and dropped: it turned every slightly late frame into a click ("machine gun"). |
| **"Little tractor" buzz at the frame rate** (found 2026-09-27) | — | Heard on NES/SNES as knocks at the drawn frame rate (30 Hz; on SMS a 60 Hz hum). Measured on the bench: **the samples are clean** — captured digitally on the board (`board_ctl.py acap`): no clicks, no frame-rate artefact; **the display is not the source** — unchanged with frames no longer sent to the panel (`lcd off`); identical with the 2026-09-14 driver (A/B); it follows the per-frame CPU/PSRAM work (NES period 32 → 16 ms when it started drawing every frame). So it is analog, between the PDM pin and the speaker, driven by the supply. The firmware audio path has not changed since the SNES bench of 2026-09-13/14 when it was not noticed; today's board ran **without the battery** (IP5306 feeding the load straight from USB, CLAIM-005 in [Hardware](hardware)). Next: the same test with the cell attached, then a scope on 3.3 V and at the PAM8403 input; candidate v3 rework: 100–470 µF bulk capacitance on 3.3 V near U1 or on the PAM8403 supply. Drawing every frame on the light cores (done for NES, GB, PCE) moves it to a less audible 60 Hz. Lasting fix: the I2S amplifier with its own reference (row above). |
| **Higher PDM carrier** | — | Estimate, to try: raise the PDM up-sampling so the carrier sits further above the RC cut-off; costs nothing in hardware. |

**Proof:** the same speaker and volume before and after each change,
recorded with the bring-up tone and one game.
