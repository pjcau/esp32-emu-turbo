---
id: findings-and-limits
title: Findings & limits
sidebar_position: 2
---

# Virtual Bench — findings, limits, and the third release

Status snapshot, 2026-07-31: every phase that can be closed without money
or instruments is closed. This page records what the bench has actually
caught, what it measurably cannot do, and how it changes the risk of the
third JLCPCB release.

## What it has caught (the evidence it works)

**Historical corpus: 22/22.** Every known past bug of this project,
re-expressed as a netlist or model mutation, is rediscovered by the bench —
and the count is computed by running it, never written down
(`make bench-retro`).

**New findings no existing gate had seen**, in the order they surfaced:

| Finding | Class | Outcome |
|---|---|---|
| Panel pin 13 (SPI SDI) floating where the datasheet requires it tied (R28-HIGH-1) | board | Fixed on main: J4 pad 28 stubs to +3V3; preserved as a corpus mutation |
| No check covered the panel's **control** lines (CS/DC/WR/RESET) — only the data bus | bench blind spot | `display.check_control_lines` added; exposed by writing the T5.2 mutations |
| U2 model had **boost and charge maxima swapped** (2.1/2.4 instead of 2.4/2.1) | model | Corrected against the official Injoinic V1.32; brief's 96 %/97 % efficiency also superseded by the official 92 %/91 % |
| DAT2/BTN_R safety argument cited a **mechanism no document states** ("card tri-states after CMD0") | justification comment | Corrected in two places: the citable reason is "DAT1–DAT3 are input on power up" (SanDisk p.17, table 3-1 note b), which covers the reset window the GPIO3 strap actually samples. **Superseded 2026-08-02**: the pad on BTN_R is not DAT2 at all — U6 pad 9 is the socket's `Cd` contact, so no card citation applies to it. The corrected argument stands for U6.8 (DAT1); pad 9 was then taken off-net entirely (R31-HIGH-2: the Cd blade is a switch to the grounded shell, so the BTN_R riser was rerouted east of the pad row) |
| `display.c` claimed 8-bit parallel supports only RGB666 — the **SPI** limitation misapplied to the parallel bus | justification comment | Comment corrected (spec p.123 §4.7.3 permits RGB565); verified against the driver source that the wire already carried 2 bytes/pixel, so the cost was latent, not paid |
| `idf_component.yml` required `espressif/esp_lcd_ili9488`, a component that **does not exist** (the driver is `atanisoft/`) — the firmware had never been buildable | firmware | Caught by the first real `idf.py build` in the repo's history; fixed together with a wrong 3-of-4-argument driver call |
| Two internal contradictions in the ILI9488 specification itself (reset defaults p.175/p.177 vs table 37; MV landscape raster) | spec | Implemented literally and flagged, never quietly "corrected" to what drivers do |

The general lesson repeats: **a verification that never runs verifies
nothing** — the firmware bugs survived because no build had ever exercised
the manifest, exactly as the R24 bugs survived while their gates went unread.

## What it measurably cannot do

| Limit | Why | Mitigation |
|---|---|---|
| **Uncalibrated** (`CALIBRATION: no` on every report) | No prototype measurement has ever been fed back; a systematic model error would agree with itself | Two independent derivations where possible (simulated vs closed-form ripple agree to 0.8 %); T5.4 closes it with ~€25 of instruments on the next prototype |
| Conflict detection covers 27 of 271 pins | Only U2, U3, Q1, U5 carry cited pin tables | The tool prints its own coverage instead of "no conflicts found" |
| Transients are open-loop | Silergy does not publish the SY8089 control loop | Declared; the LC ring is windowed out and the mean is asserted |
| U2 dissipation while charging is NOT COMPUTABLE | The V1.32 cites no power-path efficiency | Declared per scenario |
| SD bus setup/hold cannot be checked | Section 7.5 of the Simplified Spec is literally "a blank" | Needs the full (paid) spec; declared in the model |
| Assembly, solder, EMI, mechanical | Out of domain — the bench checks the design against datasheets, not physics | CPL rotation law gates + the pre-payment checklist below |

## Does it de-risk the third JLCPCB release?

Partly — and the uncovered part is known and has owners:

1. **What killed release 2** (CPL rotations) is covered by the **CPL
   gates**, not by the bench: `test_cpl_rotation_law`, pin→pad alignment
   per rotation, position corrections — all in `verify-all`.
2. **What the bench adds**: design-level deaths (floating nets, wrong
   straps, crossed lines, shorts), boot-mode regressions, out-of-tolerance
   rails, thermal margins — all asserted with cited numbers, and the bench
   is *inside* `verify-all`, so a red bench blocks the release pipeline.
3. **What no automation covers** — the manual pre-payment checklist:
   - Cut a **new release tag** first: the rotation fixes are on main but no
     tag exists after v4.3.1. Never fab from an untagged state.
   - Verify the **uploaded CPL is `release_jlcpcb/cpl.csv` at the tag**,
     not a stale download.
   - Review JLCPCB's **3D assembly preview part by part** against
     `hardware/datasheets/POLARITY_AUDIT.md` — U2, D1, Q1, LED2, L1 first,
     plus U3 (SY8089 SOT-23-5, never yet assembled on a prototype).
     This is the only moment release 2's failure mode is visible *before*
     paying; JLC applied the wrong rotations verbatim and vision-corrected
     nothing.

## What the next steps cost

| Step | Cost | Unlocks |
|---|---|---|
| ~~Fix the RGB565 comment + first firmware build~~ | done | `display.c` correct and pinned by test; firmware builds locally and via `make firmware-build` (Docker) |
| ~~ESP-IDF environment~~ | done | T4.2 (demo app dual-build) is now implementable |
| New release tag + refab | ~€35–60 | The only path to a working board — v4.3.1 is a write-off by assembly |
| USB tester + multimeter | ~€25 | T5.4: DC calibration; the `CALIBRATION` flag moves to `dc` |
| Oscilloscope | ~€300+ | T5.5: transient calibration — may stay open forever, the flag is honest either way |

Full history and per-task detail:
[`docs/archived/virtual-bench-plan.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/docs/archived/virtual-bench-plan.md).
