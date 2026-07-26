# Virtual Bench — phased plan

A netlist-driven bench test for the ESP32 Emu Turbo board: a virtual PSU and a
virtual LiPo feed a model of *this* board, built from the KiCad netlist and from
component models written against the datasheets. The firmware runs on top of it,
so the deliverable is the same thing a bench test delivers — rails come up, the
LCD shows a picture, the buttons respond, the speaker makes a sound — plus a log
of every voltage, current and junction temperature that produced it.

## What this proves, and what it does not

The bench is only worth building if it is honest about its boundary. Guarantees
are per failure class, never global.

| Failure class | Covered | By what |
|---|---|---|
| Wiring / netlist: swapped pin, inverted D/C, missing pull-up, button on the wrong GPIO | yes | Phase 2 |
| Strapping-pin state at reset (BTN_SELECT=GPIO0, BTN_R=GPIO3, BTN_L=GPIO45, LCD_WR=GPIO46) | yes | Phase 2 |
| DC operating point: every net voltage, divider, LED current, 3V3-vs-5V level compatibility | yes | Phase 1 |
| Electrical shorts: two drivers on one net, an output tied into a rail | yes | Phase 1 |
| Geometric shorts, clearance, acid traps | **no** | already `verify_isolation`, `drc_native`, `short_circuit_analysis` — the bench must not duplicate them |
| Thermal: Tj of IP5306 / SY8089 / PAM8403 at a declared ambient | yes | Phase 1 |
| Firmware↔hardware contract: what the firmware assumes vs what the netlist says | yes | Phase 4 |
| Signal integrity at 20 MHz i80, PSRAM at 80 MHz, USB HS eye | **no** | nothing covers this today; mitigation is design rules + prototype |
| EMI, ESD, crystal startup, PSRAM training | **no** | prototype only |
| Assembly: solder, tolerances, part substitution, CPL rotation | **no** | CPL has its own gate; the rest is physical |
| **A component model that misreads its datasheet** | **no** | the bench would confirm the bug with confidence — see below |

That last row is the reason Phase 0 exists. It is the Round 25 failure mode
(*a justification comment outranks the datasheet*) relocated into a new file.
The countermeasures are structural, not aspirational:

1. Every model field carries a datasheet citation (document, revision, page,
   table). A model with an empty citation fails its own schema check.
2. The bench must rediscover known historical bugs from a retro corpus
   (Phase 0), so coverage is measured rather than claimed.
3. Mutation tests break the netlist on purpose and require the bench to notice
   (Phase 5). An assertion that never fires is not evidence.
4. A handful of measurements from prototype #1 calibrate the models
   (Phase 5). Until that step, the bench is self-consistent but uncalibrated,
   and must say so in its own output.

## Source of truth

The **PCB netlist is the truth**, because the PCB is what gets fabricated. The
schematic is cross-checked against it and any disagreement is a bench-blocking
error, not a warning.

The bench runs against **two netlists and reports the delta**: the tag of the
fabricated revision (so results are comparable to prototype #1 measurements) and
generator HEAD (so the revision being designed is the one under test). A
behaviour that differs between the two is the headline output — "this changed
since the board you are holding".

## Phase -1 — prerequisite: close `verify_netlist_diff` — **DONE**

The bench may not be built on a netlist that is in dispute. When this plan was
written `verify_netlist_diff` reported 7 pin-level disagreements, which were
**three distinct problems, not one**. Items (a)–(c) below were closed by
`397c854`, item (d) by `74c196e`. `verify_netlist_diff` is now 4/4 PASS and the
bench has an undisputed netlist to stand on.

Item (d) was closed differently from what an earlier draft of this file said,
and the difference matters for anyone reading this plan later. It was NOT fixed
by moving copper: see "(d)" below.

**(a) `U1.3` — EN wired straight to +3V3 in the schematic. Real bug, schematic side.**
`sheets/mcu.py` dropped R3 from the BOM and replaced it with a *plain wire* from
EN to +3V3, which is not the same thing. On that drawing, `SW_RST` — wired from
the same node to GND — shorts the 3.3 V rail every time it is pressed. The PCB
does not do this: it keeps `EN` as its own net. **Fixed: the EN→+3V3 wire is
gone and the node carries a global `EN` label.**

An earlier draft of this section said the removal of R3 was "correct: the
ESP32-S3-WROOM-1 integrates a 10 kΩ EN pull-up". **That is false**, and it is
worth leaving the correction visible here rather than quietly deleting it,
because this file is *about* that failure mode. The module datasheet says the
opposite in its own words, page 28, under the peripheral reference schematic:
an RC delay circuit **must** be added at the EN pin, R = 10 kΩ and C = 1 µF
typical — and figure 7 draws R7 from VDD33 to EN with C8 from EN to GND. There
is no on-module pull-up to rely on.

So the Round 25 pattern here is worse than a comment justifying a removal: the
justification was repeated, believed, and then used to justify the *next*
removal. Four files, four stories about R3 — `mcu.py` said the module has the
pull-up, `hardware-audit-bugs.md` said the RC network was "intact",
`simulate_circuit.py` budgets `"EN pull-up (R3 10k)"` at 0.33 mA as if R3 were
fitted, and the copper has none of them. The bench must treat a datasheet
citation as the only admissible evidence for a model field, precisely because
this is how convincingly the alternative propagates.

**(b) `J3.1` and `Q1.2` — schematic drawing wired to GND instead of BAT_IN.**
`sheets/power_supply.py:383` states the intent explicitly: *"Q1 Source (pin 2) →
BAT_IN → J3.1"*, which is what the PCB implements. The exported schematic
netlist says both pins land on `GND`, so the drawing does not match its own
stated intent. **Fix: schematic side.**

**(c) `LED1.1/1.2` and `LED2.1/2.2` — symmetric pin swap.**
Both pins of both LEDs are exchanged, which is the signature of a
symbol-vs-footprint pin-numbering convention rather than a wiring error. Must
still be resolved to a single convention and proven against the physical
polarity record in `hardware/datasheets/POLARITY_AUDIT.md` — the fitted
prototype settles it — but it is a different class from (a) and (b) and must not
be fixed by the same reflex.

**(d) `C3.1` — the EN reset cap was wired to the +3V3 rail. Real bug, board side.**
The last surviving mismatch. C3 is the RC that holds EN low while +3V3 settles;
the schematic has always drawn it from EN to GND, but the board placed it at
(69.55, 42.0) with pad 1 on +3V3, 25 mm from any EN copper — so the reset delay
did not physically exist. `verify_polarity` did not catch it because its
expectation table said `C3.1 = +3V3`: the gate had been written to describe the
copper, so it agreed with the defect, and T4 was the only check that disagreed.

Fixed on the SCHEMATIC side, not by moving copper. C3 was rerouted onto EN in
an earlier attempt (`backup/discarded-c3-pcb-fix`); that attempt was discarded
because v1 is not being re-fabricated, so changing the board's copper buys
nothing and the release package would have had to be re-cut to match.

What the board actually has is two decoupling caps and no RC on EN at all —
R3 is DNP as well. The module datasheet requires that RC (page 28), so the
absence is recorded as an as-built limitation with a fix specified for the
next respin, and the schematic now draws C3 where the copper puts it: the
third cap in the decoupling row, pad 1 on +3V3. T4 is 4/4 PASS because the
two files finally agree, not because the circuit changed.

`verify_polarity` did not catch any of this: its expectation table said
`C3.1 = +3V3`, i.e. the gate had been written to describe the copper, so it
agreed with whatever the copper said. That is the lesson to carry into the
bench — a gate that restates the artefact it checks cannot disagree with it.

Two more things worth keeping in mind for the bench, from the discarded
attempt, because both are mistakes the bench itself could repeat:

- A stub landing mid-span on another trace is a **T, and a T is not a node**.
  Both `verify_dangling_copper` and the union-find in `verify_net_connectivity`
  judge by shared endpoints, so the EN vertical had to be split at the tap.
- Occupancy must be measured against segment **bodies**, not endpoints. The
  first via site was chosen from a search that filtered tracks by endpoint, and
  it landed exactly on an LCD_D3 trace passing through on F.Cu — 0.0 µm, a
  short through the barrel. `verify_copper_clearance` caught it.

Still open, and not blocking: the R3 story is inconsistent across the repo.
`mcu.py` says R3 is DNP (correct — the module has the pull-up), the BOM/CPL
agree, but `simulate_circuit.py` still budgets `"EN pull-up (R3 10k)"` at
0.33 mA on +3V3. Phase 1 must not inherit that number.

## Phase 0 — Foundation and honesty baseline

Nothing electrical is modelled yet. This phase decides whether the rest can be
trusted.

| Task | Deliverable | Done when |
|---|---|---|
| T0.1 | `scripts/vbench/netlist.py` — build `{net: [(ref, pin, pad, layer)]}` from `.kicad_pcb` via `pcb_cache.load_cache()`; cross-check against the schematic netlist | every net in the board resolves to a pin list; disagreements are reported and block |
| T0.2 | Model schema: `scripts/vbench/models/_schema.py` — pins, electrical parameters, `datasheet_ref` (doc + rev + page/table) mandatory and non-empty | a model missing a citation fails schema validation |
| T0.3 | Retro corpus: `scripts/vbench/retro/*.yaml` — known past bugs from `hardware-audit-bugs.md` expressed as netlist/model mutations the bench must catch | corpus written and failing (no bench yet), each entry naming the round it came from |
| T0.4 | `make bench-netlist` — prints the extracted netlist summary and the dispute list | target exists, exits non-zero while disputes remain |

## Phase 1 — Analog: rails, operating point, shorts, thermal

The physics layer. Answers "what voltage sits on every net, how much current
flows, how hot does each part get".

| Task | Deliverable | Done when |
|---|---|---|
| T1.1 | Nodal DC solver over the extracted netlist. Sources: virtual PSU (5 V, programmable current limit) and virtual LiPo (OCV-vs-SoC curve + internal resistance) | solves the board and prints a per-net voltage table |
| T1.2 | Regulator/source models with citations: IP5306 (boost, charge, KEY, LED bar), SY8089 buck (3.3 V, 2 A, efficiency curve), Q1 reverse-polarity path, AMS1117 where present | each model reproduces its datasheet's own worked example |
| T1.3 | Electrical conflict detector: two drivers on one net, output into a rail, a GPIO fighting a pull-up network. Explicitly **not** geometric — the geometric side stays in `verify_isolation` | detects an injected conflict, and says which gate owns geometry |
| T1.4 | Transient runs via the ngspice MCP: USB insertion cold start, bulk-cap inrush, backlight step, battery sag to 3.2 V, brownout threshold | emits `t_3v3_valid`, `V_min`, ripple per scenario |
| T1.5 | Thermal: parametrize the hardcoded ambient in `verify_thermal_budget.py` (today 40 °C) and run **30 °C external** plus the 40 °C in-enclosure worst case; θJA from datasheet, corrected for copper area; scenarios idle / gaming / charge-and-play | per-part Tj table with margin, fails below the declared margin |
| T1.6 | `make bench-power` | rail table + thermal table printed, non-zero exit on any out-of-spec value |

Note on ambient: 30 °C is the external air temperature. Inside a closed
handheld enclosure the air around U2/U3 is warmer, which is why the existing
gate assumed 40 °C. Both are reported; the 40 °C figure is the one that governs
pass/fail until the enclosure rise is measured on the prototype.

## Phase 2 — Digital fabric: every ESP32 pin, every button, the switch

| Task | Deliverable | Done when |
|---|---|---|
| T2.1 | GPIO fabric model: all ESP32-S3 pins — direction, internal pull, drive strength, what the netlist attaches, and the reserved set (flash/PSRAM) | `make bench-pins` prints every pin with net, role, load and boot-time level |
| T2.2 | Button model: 12 buttons, external pull-up or DNP (BTN_L / R14 needs the internal pull), RC debounce with the real time constant, press/release as timed events | a press produces a level transition with the computed RC delay |
| T2.3 | SW_PWR switch model — including the known fact that it is **not** in series. The bench must *reproduce* "switch off, board still powered" as expected behaviour, not report it as a bench bug | scenario `switch_off` asserts the board stays powered, citing the v1 invariant |
| T2.4 | Boot-mode model: sample strapping pins at reset → resulting boot mode | a button held at reset that forces download mode is a FAIL with the pin named |

## Phase 3 — Peripherals: LCD, audio, SD

| Task | Deliverable | Done when |
|---|---|---|
| T3.1 | ILI9488 i80 model: command/parameter state machine, MADCTL/rotation, pixel format, 320×480 framebuffer, RST/CS/DC/WR setup-hold checks against the 20 MHz pclk | writes a frame and exports it as PNG; a timing violation is reported with the datasheet figure |
| T3.2 | I2S → PAM8403 → speaker: sample stream, gain, supply-dependent clipping, output power vs the 5 V rail, and current fed **back** into Phase 1 so audio peaks sag the rail | exports a WAV of what the speaker would emit, and the rail dip it caused |
| T3.3 | SD over SPI: card model, CMD0/CMD8/ACMD41 init, block read from a host directory, 20 MHz timing, current draw | mounts a host folder and reads a ROM through the modelled bus |

## Phase 4 — Firmware in the loop and the demo app

| Task | Deliverable | Done when |
|---|---|---|
| T4.1 | `vbench_hal`: `software/sim` recompiled against the board model instead of the fake HAL, so pixels travel through the i80 model and buttons through the RC network | the existing SDL simulator renders through the modelled bus |
| T4.2 | `demo_app.c`: one source compiled both against ESP-IDF (real firmware) and against the bench — rails/temps on screen, moving sprite, button test grid, audio beep, SD file list | identical binary behaviour in both builds |
| T4.3 | Scenario runner: YAML scenarios (`usb_cold_boot`, `battery_3v4`, `press_all_buttons`, `sd_missing`, `audio_max`, `switch_off`) with assertions; headless output = PNG + log + JUnit | `make bench-ci` runs headless, non-zero on failure |
| T4.4 | Interactive mode: SDL window, keyboard as buttons, instrument panel (per-rail voltmeter, ammeter, Tj) — the actual bench test | `make bench` opens the window with live instruments |

## Phase 5 — Make it a gate that cannot lie

| Task | Deliverable | Done when |
|---|---|---|
| T5.1 | The Phase 0 retro corpus passes: the bench rediscovers the known historical bugs | every corpus entry is caught, and the report says how many |
| T5.2 | Mutation tests: swap D/C, delete a pull-up, tie WR to GND, short +3V3 to GND, rotate the LCD model — each must fail the bench | `scripts/test_vbench.py` in the style of `test_issue_dispatch.py` |
| T5.3 | Register in `VERIFY_ALL_SCRIPTS` **and** give the gate an owner in `issue_dispatch.py` routing — an unowned gate is a hard error (exit 2) in this repo | `make verify-all` includes it, `make dispatch` routes it |
| T5.4 | Prototype #1 correlation, **DC**: 3V3, 5V, LED currents, U3 case temperature under load | bench predicts each within a declared tolerance |
| T5.5 | Prototype #1 correlation, **transient** (scope available): 3V3 rise time at cold start, rail ripple under audio load, i80 WR timing at 20 MHz | the Phase 1.4 transient outputs are checked against captured waveforms; bench output carries a `calibrated: dc / dc+transient / no` flag, honest either way |

## Phase 6 — optional, later: QEMU device

Write a QEMU device for LCD_CAM/i80 + a GPIO backend that speaks to the board
model, so the real ESP-IDF binary runs against the modelled hardware. Highest
fidelity, highest cost (C device + maintaining a QEMU fork). Only worth starting
once Phases 0–5 have proven the board model itself.

## Ordering rationale

Phase 0 before everything because an uncalibrated model is a confident liar.
Phase 1 before 2 because a digital model that assumes 3.3 V is meaningless until
something proves 3.3 V is there. Phase 3 after 2 because the LCD is driven by
pins whose boot state Phase 2 establishes. Phase 4 last among the build phases
because firmware-in-the-loop is only interesting once the thing it loops with is
trustworthy. Phase 5 is what turns the result from a demo into a gate.
