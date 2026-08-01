---
id: virtual-bench
title: Virtual Bench
sidebar_position: 1
---

# Virtual Bench

A **netlist-driven bench test** for the board, run entirely in software: a
virtual PSU and a virtual LiPo feed a model of *this* board, built from the
KiCad netlist and from component models written against the datasheets in
`hardware/datasheets/`. The deliverable is what a physical bench delivers —
rails come up, strapping pins read a valid boot mode, the display and audio
chains check out — plus a log of every voltage, current and junction
temperature that produced it.

Source of truth: the full phased plan lives in
[`docs/archived/virtual-bench-plan.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/docs/archived/virtual-bench-plan.md)
in the repo; the implementation is the `scripts/vbench/` package, gated by
`scripts/test_vbench.py` inside `make verify-all`.

## What it proves — and what it does not

Guarantees are per failure class, never global:

| Failure class | Covered |
|---|---|
| Wiring/netlist: swapped pin, inverted D/C, missing pull-up, button on the wrong GPIO | ✅ |
| Strapping-pin state at reset (BTN_SELECT=GPIO0, BTN_R=GPIO3, BTN_L=GPIO45, LCD_WR=GPIO46) | ✅ |
| DC operating point: every net voltage, dividers, LED currents, 3V3-vs-5V compatibility | ✅ |
| Electrical conflicts: two drivers on one net, an output tied into a rail | ✅ |
| Thermal: junction temperature of IP5306 / SY8089 / PAM8403 at a declared ambient | ✅ |
| Firmware↔hardware contract (what firmware assumes vs what the netlist says) | ✅ |
| Geometric shorts, clearance, acid traps | ❌ — belongs to `verify_isolation` / DRC / short-circuit analysis; deliberately not duplicated |
| Signal integrity (20 MHz i80, PSRAM 80 MHz, USB eye), EMI, ESD, crystal startup | ❌ — prototype only |
| Assembly (solder, tolerances, CPL rotation) | ❌ — the CPL has its own gates |
| A component model that misreads its datasheet | ❌ — the bench would confirm the bug with confidence; this is why the honesty rules below exist |

## The honesty rules

The bench's core risk is Round 25's lesson (*a justification comment outranks
the datasheet*) relocated into new files. Three rules defend against it:

1. **Every number must be cited.** A component model validates only if each
   parameter carries a datasheet citation that resolves to a PDF actually in
   `hardware/datasheets/` — an uncited, weaselly or unlocatable number does
   not load. A part with no datasheet in the repo cannot be modelled at all.
2. **Values are derived, not quoted.** The +3V3 rail must come out at 3.327 V
   by walking the feedback divider in the netlist — not because 3.3 was typed
   anywhere. A floating node stays floating rather than defaulting to 0 V.
   The PAM8403's 8 Ω output power is the Diodes EC table's own cited point
   (1.8 W at 10 % THD) since 2026-07-31 — the earlier halved-from-4-Ω
   derivation is retired.
3. **A corpus of historical bugs must be rediscovered.** Real bugs from this
   project's history are recorded with citations; the bench must find each
   one when it is injected, and `scripts/test_vbench.py` mutation-tests the
   whole machine — a corpus entry that hand-writes its own verdict, cites a
   line that moved, or reuses an id fails to load.

## Phases

| Phase | Scope | Status |
|---|---|---|
| −1 | prerequisite: close `verify_netlist_diff` (two netlist sources agree) | done |
| 0 | foundation: netlist extraction, model schema, bug corpus | done |
| 1 | analog: rails, operating point, conflicts, thermal | done (with self-named holes) |
| 2 | digital fabric: every ESP32 pin, every button, the power switch, boot-mode derivation | done |
| 3 | peripherals: LCD (panel view **and** ILI9488 controller state machine with i80 timing), audio (cited gain/power, computed rail sag), SD (bus **and** card protocol: CMD0/CMD8/ACMD41, CMD17 block reads) | **done** 2026-07-31 — residue declared per module |
| 4 | firmware in the loop and the demo app | T4.1 / T4.3 / T4.4 done; T4.2 unlocked (ESP-IDF builds, locally and via `make firmware-build`) |
| 5 | make it a gate that cannot lie | **T5.1–T5.3 done**: corpus 22/22 rediscovered, the plan's five mutations implemented, `test_vbench` + `test_vbench_display` + `test_vbench_sdcard` all in `verify-all`. T5.4/T5.5 (prototype calibration) await instruments — every report carries `CALIBRATION: no` until then |
| 6 | optional: QEMU device | not started |

## Running it

```bash
make bench             # interactive: SDL window, live instruments
make bench-ci          # every scenario, headless, JUnit output
make bench-all         # the whole bench, every phase, exit 0 or die
make bench-display     # panel wiring + controller frame + i80 timing
make bench-sdcard      # SD protocol: init + block reads of a real file
python3 scripts/test_vbench.py   # the mutation suite (also in verify-all)
```

The package modules map to bench instruments: `rails.py` (DC operating
point), `conflicts.py` (driver conflicts), `thermal.py` (junction
temperatures), `transients.py` (SPICE decks with the BOM's real values),
`pins.py` / `buttons.py` (strapping and boot mode), `display.py` +
`ili9488_ctrl.py` (panel wiring, controller command sequence, write-side
AC timing), `audio.py`, `sdcard.py` + `sdcard_protocol.py` (bus wiring and
the card's SPI protocol), with `corpus.py` holding the historical-bug
corpus and `scenarios/` the end-to-end bench scripts.

What the bench has actually caught, its measured limits, and the
third-release checklist live in [Findings & limits](findings-and-limits.md).
