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

## The bench patch: a low-pass between C22 and the amplifier

The path is GPIO 17 → C22 (0.47 µF in series) → PAM8403 input, with no
low-pass anywhere. The patch goes between C22 and the PAM8403 input, where the
1 kΩ + 10 nF of article 0004 already sits. Only that first version has been
tried on a board (hiss reduced, not removed); the values below are calculated.

**A. One stage (the smallest change)**

```
C22 ──[ 1 kΩ ]──┬── PAM8403 input
                │
            [ 22 nF ]
                │
               GND
```

Cut-off about 7 kHz (16 kHz with the 10 nF fitted today). On a board that
already has the 10 nF, a second 10 nF stacked **in parallel** on the first
gives 20 nF; in series they would give 5 nF.

**B. Two stages (steeper)**

```
C22 ──[ 1 kΩ ]──┬──[ 2.2 kΩ ]──┬── PAM8403 input
                │              │
            [ 22 nF ]      [ 10 nF ]
                │              │
               GND            GND
```

Twice the slope above the cut-off, so far more attenuation of what is left of
the carrier. The overall cut-off is about 4.5 to 5 kHz: slightly dull, little
noticed on a 28 mm speaker. For more treble, 10 nF and 4.7 nF instead of
22 nF and 10 nF put it near 10 kHz. Capacitors to ground with the shortest
connection, close to the amplifier.

**What a filter cannot do.** Part of the PDM noise falls inside the audio
band, where no filter removes it without removing the sound. The buzz at the
frame rate comes in through the supply, not through the signal, and no
input filter touches it. Both need the respin.

## The respin (v3.1): three ways, and the pins they need

Audio uses one pin today (GPIO 17). **One pin is free on the module
(GPIO 16)**; every other GPIO is taken. That decides which chain fits.

| Option | Pins | What changes | For / against |
|:---|:---|:---|:---|
| **1. Class-D amplifier with a digital PDM input** (clock + data) | 2: GPIO 16 and 17 | No analog signal on the board: the PAM8403, C22 and the filter go; firmware stays PDM, with a clock pin | Removes the hiss and the supply buzz at the root, uses exactly the pins there are. The part (the MAX98358 / SSM2537 family is the kind meant), its stock at JLCPCB and its PDM clock range against what the ESP32-S3 gives are **not checked** |
| **2. I2S amplifier with integrated DAC** (the proposal in the table above) | 3: BCLK, LRCLK, DIN | Same benefit; firmware goes from PDM to standard I2S | One more pin than the board has free: a function has to give one up. The diagnostic LED on GPIO 15 is not populated in production and is the candidate |
| **3. Keep the PAM8403, add a real filter** | 1 (as today) | A two-stage low-pass in the schematic (patch B above) and a separately filtered supply for the amplifier | The smallest change, and the same family as the bench patch, which only attenuated. A fallback |

Recommended: option 1 if a part is found, else option 2. Before either goes
into the schematic: the part chosen from its datasheet, the pin budget
re-checked, and the chain tried on a development board.

Free in firmware, to try on the current boards: a higher PDM up-sampling, so
the carrier and its shaped noise sit further above the filter's cut-off.

**Proof:** the same speaker and volume before and after each change,
recorded with the bring-up tone and one game.
