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

Still open, and not blocking — but read the correction below before
believing this paragraph's earlier version. It used to say:

> `mcu.py` says R3 is DNP (correct — the module has the pull-up), the
> BOM/CPL agree, but `simulate_circuit.py` still budgets
> `"EN pull-up (R3 10k)"` at 0.33 mA on +3V3.

Both halves were wrong, in the two different ways this file is about.
The parenthesis repeated the false premise that section (a) above spends a
paragraph demolishing — **the module has no EN pull-up**, the datasheet
requires an external RC — so the plan for the bench was itself carrying the
bug it was written to prevent. And the 0.33 mA figure had already been
zeroed by `68bb20e`; the sentence outlived its subject.

What is actually still inconsistent is the *timing*, not the current.
`simulate_circuit.py:412-420` computes `en_tau = EN_PULLUP_R * EN_RESET_C`
from R3 = 10 kΩ and C3 = 100 nF, prints an EN reset delay, and passes a
check that the delay is long enough for stable boot. Neither part is
fitted: R3 is DNP and C3 sits across +3V3/GND. So the one gate that speaks
about power-on reset timing is describing a network that exists in no
board, and reporting PASS. Phase 1 (T1.4) must derive that time constant
from the extracted netlist, where it is undefined, and say so.

`make bench-retro` carries this as corpus entry `R10-LOW-7`.

## Phase 0 — Foundation and honesty baseline — **DONE**

Nothing electrical is modelled yet. This phase decides whether the rest can be
trusted.

| Task | Deliverable | Done when |
|---|---|---|
| T0.1 | `scripts/vbench/netlist.py` — build `{net: [(ref, pin, pad, layer)]}` from `.kicad_pcb` via `pcb_cache.load_cache()`; cross-check against the schematic netlist | every net in the board resolves to a pin list; disagreements are reported and block |
| T0.2 | Model schema: `scripts/vbench/models/_schema.py` — pins, electrical parameters, `datasheet_ref` (doc + rev + page/table) mandatory and non-empty | a model missing a citation fails schema validation |
| T0.3 | Retro corpus: `scripts/vbench/retro/*.json` — known past bugs from `hardware-audit-bugs.md` expressed as netlist/model mutations the bench must catch | corpus written and failing (no bench yet), each entry naming the round it came from |
| T0.4 | `make bench-netlist` — prints the extracted netlist summary and the dispute list | target exists, exits non-zero while disputes remain |

Targets: `make bench-netlist`, `make bench-delta`, `make bench-retro`,
`make bench-test`, `make bench-phase0`. None is in `VERIFY_ALL_SCRIPTS`:
two of them are *designed* to exit non-zero at this phase, and parking
permanent reds in that suite is how the suite stops being read.
Registration is T5.3, which also has to give the gate an owner in
`issue_dispatch.py`.

**Corpus format: JSON, not YAML.** PyYAML is not importable on the
development machine (PEP 668 externally-managed interpreter) and all 95
scripts in this repo are stdlib-only. A YAML corpus would make the gate
un-runnable, and an un-runnable gate is a gate nobody reads. The same
applies to the Phase 4 scenario files (T4.3).

### Triage — 29 disputes down to 5

The plan forbids building the bench on a netlist in dispute, so the classes
Phase 0 exposed were worked through before Phase 1 opened. Two of them
turned out to be a fault in the *detector*, which is recorded here because
that is the more useful half of the lesson.

**D3 was a false-alarm class (17 → 0).** The first version reported every
pad the schematic translation table does not list and called them "compared
by nothing". All seventeen are declared in `hardware/datasheet_specs.py`,
where `verify_datasheet_nets` compares each one against an expected net —
267 checks, all passing. The four most suspicious readings dissolved on
inspection: `U6.8`/`U6.9` on the SD data lines and `SW_PWR.4b`/`4d` on
`BTN_SELECT` are deliberate same-net assignments with a written safety
analysis at `routing.py:6055-6085`, protecting against real
trace-through-pad shorts and guarded by a hard gate. A check that fires on
all seventeen discriminates nothing, so D3 now fires only for a pad in
*neither* source — empty today, and `test_vbench.py` injects one to prove
the class still works.

**Two D3 entries were a real defect, in the table rather than the board.**
`_J1_MAP` in `verify_netlist_diff` claimed "3,5,8 = SBU / unused, no net"
and mapped D+ to pad 6 and D- to pad 7 alone. The SBU pins are 3 and 9;
pads 5 and 8 are the flipped-orientation half of the differential pair and
carry `USB_D-`/`USB_D+`, which `datasheet_specs.py::J1` states pad by pad
citing USB-C r2.1 §4.2. Two of the four data pads were therefore compared
by nothing. Fixed; T4 now compares all four.

**The two supply-rail stubs were the serious find.** `BAT+` had one node on
the schematic (`SW_PWR.1`) and `VBUS` had one (`U4.5`), because three local
labels in the Power Supply sheet sat 1.5–2 mm off the wires they name:
`VBUS` at `vbus_y - 2`, `BAT+` at `bat_y - 2`, `BAT_IN` at
`jst_plus_y - 1.5`. A label that misses its wire leaves the wire unnamed,
and KiCad drops unnamed nets from the export — so the pins on them do not
appear with a wrong net, they do not appear at all. Nine pins of the
battery and USB-input path were absent from the exported netlist:
`C17.1`, `C18.1`, `J1.2`, `J1.11`, `J3.1`, `L1.x`, `Q1.2`, `Q1.3`, `U2.1`,
`U2.6`.

That has a consequence for this plan's own record. **Phase -1 item (b) was
not closed the way it says.** `J3.1`/`Q1.2` stopped being reported by T4
because both pins left the netlist, not because the drawing was corrected;
`verify_netlist_diff` iterates schematic pins, so a pin that is not there is
compared against nothing and the gate goes green. With the labels on their
wires the rails carry their pins (`BAT+` 5 nodes, `BAT_IN` 3, `VBUS` 4) and
(b) is genuinely closed.

Attaching the labels immediately exposed what had been hiding underneath:
**L1 was drawn the wrong way round**, `sch='BAT+'` on pin 2 against the
board's pin 1, contradicting `datasheet_specs.py::L1` ("pin 1 = Battery
side"). An inductor is symmetric so nothing was electrically wrong, but the
netlist said something false about which pad is which, and it could not be
seen for as long as the rail had no name. Fixed by rotating the symbol
180°, which is what `symbol()`'s own docstring prescribes for a symmetric
two-terminal part whose pad 1 is at the other end — a facility that existed
and had never been used.

**A new gate, because this class has now recurred four times.**
`scripts/verify_schematic_label_attach.py` checks geometrically that every
label lies on a wire or junction; no expectations table, a label is
attached or it is not. It found a fourth instance on its first run: three
`glabel` calls in the audio sheet used as a *caption* for the I2S bus,
declaring net names that connect nothing. Captions are now `text()`.
Registered in `VERIFY_ALL_SCRIPTS` (`make verify-sch-labels`); the routing
law in `issue_dispatch.py` gives it an owner via `law:schematic`.

**The phantom nets are gone from both sources — twice over.** A parallel
session reached the identical conclusion on the same day and landed it on
`main` as R26-LOW-1: net ids 18/19 retired with a documented gap, the DS1
stubs relabelled `+3V3`, `datasheet_specs.py::J4` pads 8 and 29 tightened
from `_any_of` to `_exact`. Same three files, same reasoning, arrived at
independently. `main`'s wording is the one that survives the merge; this
branch keeps the finding as corpus entry `R26-LOW-1`, because a detector
with nothing to rediscover cannot be measured. What follows is the
reasoning, which both sessions share:

`LCD_BL` and `LCD_RD` had
zero pads and zero copper: the DFM v3 fix of 2026-04-10 put panel pins 12
(RD) and 33 (LED-A) directly on `+3V3` but left the names declared in
`primitives.py::NET_LIST`, and `display.py` kept using them as global
labels "as documentation of which panel pin is involved". A net name is not
a comment. The DS1 stubs now carry `+3V3` with the panel pin in the
annotation text, the two `NET_LIST` slots are removed leaving a documented
gap (the `BTN_MENU` precedent), and `datasheet_specs.py::J4` pads 8 and 29
are tightened from `_any_of("LCD_BL", "+3V3")` to `_exact("+3V3")` — an
expectation that accepts two answers cannot disagree with either. Drawing
LED-A straight onto the rail also puts R25-HIGH-1, the backlight with no
ballast, into the drawing instead of behind a signal-sounding name.

**The 5 that remain, and why they are not being closed here.** Four are
`I2S_BCLK`/`I2S_LRCK` reported on both sides — R10-LOW-2, GPIO15/16
reserved as net names while the firmware uses PDM TX, which needs only
DOUT. Closing them means deciding whether the reservation should exist as a
net at all, and it touches the firmware's GPIO documentation. The fifth is
`C28`, below, which needs an electrical decision, not a bookkeeping one.

Copper is untouched by all of this: the board file's segment list is
identical, verified segment by segment.

**`verify-all` is 69/69 after merging `main`.** The one red this branch
carried, `verify_cpl_rotation_law` on U2 and J4, was closed on `main` by the
Round 26 work — and note R26-MED-1 there, "the session-start report hid half
of a failure", which is the same observation this branch made from the other
end: the hook printed U2 only, so J4 had to be found by running the gate
directly. Two release-package problems this branch reported and did not
touch are also closed on `main`: the stale U4 rotation in
`release_jlcpcb/cpl.csv` (R26-HIGH-3) and the three GND stitching segments
its board file was missing.

Deliberately NOT carried into the corpus: R26-CRIT-1, R26-CRIT-2 and
R26-HIGH-1/2 are all CPL rotation findings, and the boundary table at the
top of this file puts CPL rotation outside the bench. It has its own gate.
A corpus entry for a failure class the bench cannot detect would be a
coverage claim with nothing behind it.

### What Phase 0 measured

`make bench-netlist` reports **29 disputes at HEAD, none of them D4** — the
two sources no longer disagree about any pin they both describe, which is
what `verify_netlist_diff` going 4/4 already told us. The value is in the
classes that gate structurally cannot see:

| Class | Count | What it is |
|---|---|---|
| D1 | 2 | `LCD_BL`, `LCD_RD` — net names in the board with no pad on them. Both files declare the name, so T1/T2 match; T4 iterates schematic pins, of which these have none. A net with no pin is a label. |
| D2 | 9 | nets with a single pin. The board's `I2S_BCLK`/`I2S_LRCK` (R10-LOW-2), and on the schematic side `BAT+` (one node: `SW_PWR.1`) and `VBUS` (one node: `U4.5`) — the two supply rails of the design, drawn as stubs. |
| D3 | 17 | pads carrying a net that no schematic pin maps to, so nothing compares them. Six are signal nets: `J1.5`/`J1.8` (the USB pair's second orientation, which `_J1_MAP` calls "SBU / unused, no net"), `U5.8` (`PAM_VREF` — the exact node R24-HIGH-1 was about), `U6.9` (card-detect, sitting on `BTN_R` = GPIO3, a strapping pin), and `SW_PWR` tabs 4b/4d on `BTN_SELECT`. |
| D5 | 1 | `C28` — see below. |

`make bench-delta` answers "what changed since the board you are holding":
**30 electrical differences between `v4.3.1` and HEAD**, dominated by the
regulator swap (`U3` pins 1-4 all move, `L2`/`R25`/`R26`/`C29`/`C30`
appear, `BUCK_FB`/`BUCK_LX` are new) and by the R24-HIGH-1 fix
(`R20.1`/`R21.1` move `GND` → `PAM_VREF`). Prototype #1 therefore has a
linear regulator and the audio bias bug; no bench result on HEAD's netlist
describes it. Run at `--rev v4.3.1` the netlist is far more in dispute — 67,
including 38 D4 — which is R24's schematic↔PCB drift, since closed.

**One new finding, same shape as the R3 story.** `C28` has pads on `+3V3`
and `GND` and is DNP: absent from the BOM, the CPL and the schematic,
removed from assembly because it sits under the module body
(`jlcpcb_export.py:420`). But `verify_decoupling_adequacy.py:59` lists
`"C28": 10.0` as the ESP32's `+3V3` bulk capacitance, under a comment
saying its values come from the BOM — where C28 has never been. A gate is
crediting the supply with 10 µF that exists on no physical board.
`verify_bom_cpl_pcb` cannot see it, because "footprint on the board, not in
the BOM" is its definition of DNP; `verify_netlist_diff` T3 only checks the
other direction. Corpus entry `VB-C28-DNP`. Not fixed here: whether the
missing 10 µF matters is a Phase 1 question, and the buck's own output
capacitor is on the same rail.

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
