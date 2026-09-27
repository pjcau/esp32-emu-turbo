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
| **32 kHz in every app** | firmware, done (2026-09-26/27) | Keep: at other rates the PDM DAC-mode clocks (rate / 100) misbehave — mame-go ignored the volume at 22050, PC Engine and DOOM crackled. Cores whose chip runs at another rate resample (Genesis) or double a 16 kHz mix (Duke Nukem 3D, Neo Geo Pocket). |
| **Silence while an app loads** | firmware, done 2026-09-27 (`pdm.c` idle check) | The channel now starts on the first samples and switches off after 100 ms without any (an app loading, the hourglass): an enabled channel with nothing to play squealed. The DMA `auto_clear` option was tried first and dropped: it turned every slightly late frame into a click ("machine gun"). |
| **Buzz at the drawn frame rate** (found 2026-09-27) | — | Measured with the webcam microphone: a periodic buzz at exactly the drawn frame period (NES 32 ms, SMS 16 ms, SNES ~30 Hz "little tractor"), present even with all-zero samples and identical with the 2026-09-14 driver (A/B), gone with the channel off. The display bus bursts pull the 3.3 V rail the PDM pin is powered from, and the PDM level follows it. The firmware audio path has not changed since the SNES bench of 2026-09-13/14, when it was not noticed, so the difference is likely physical: today's board ran **without the battery** (see CLAIM-005 in [Hardware](hardware)), and only article 0004 carries the R38 rework. Why SMS sounds almost clean: it draws ~55–60 frames/s, so the buzz sits at 60 Hz, a steady low hum the 28 mm speaker barely reproduces; NES and SNES draw 30, a train of separate knocks at 30 Hz that the ear picks out. Firmware mitigation: frameskip 0 on the light cores (NES, GB, PCE) moves it to 60 Hz ([Emulators](emulators)). Next: the same recording with the cell attached; the lasting fix is the I2S amplifier with its own reference (row above). |
| **Higher PDM carrier** | — | Estimate, to try: raise the PDM up-sampling so the carrier sits further above the RC cut-off; costs nothing in hardware. |

**Proof:** the same speaker and volume before and after each change,
recorded with the bring-up tone and one game.
