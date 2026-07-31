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

**The 5 that remained, down to 1 (2026-07-26).** Four were `I2S_BCLK`/`I2S_LRCK`
on both sides — closed by retiring the reservation nets outright (R10-LOW-2):
NET_LIST ids 24/25 gap-retired, U1 pads 8/9 netless, the schematic labels the
pins plain `GPIO15`/`GPIO16` (T1_ALLOW, same class as the PSRAM trio), three
gate allowlists died with them, and the generated test firmware stopped
driving `.clk` on GPIO15 to match production `audio.c`. The one that remains
is `C28` (D5): a DNP land whose respin fix is relocation, an electrical
decision this bench does not make.

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

### Phase 1 status — **DONE**, with two holes it names itself

| Task | State | Where |
|---|---|---|
| T1.1 DC solver | **done** | `scripts/vbench/rails.py`, `sources.py` · `make bench-rails` |
| T1.2 cited models | **U3, Q1, U5, U2 complete** — U2 rewritten 2026-07-31 from the official V1.32 (theta_JA 50, boost/charge un-swapped, 92%/91%, full EC table); battery family model added | `scripts/vbench/models/` |
| T1.3 conflict detector | **done**, at 10% pin coverage (27 of 271) and it prints that | `scripts/vbench/conflicts.py` · `make bench-conflicts` |
| T1.4 transients | **done** (ngspice) | `scripts/vbench/transients.py` · `make bench-transients` |
| T1.5 thermal | **done** | `scripts/vbench/thermal.py` · `make bench-thermal` |
| T1.6 `make bench-power` | **done** — rails + conflicts + thermal + transients | Makefile |

The two holes, both named in the tools' own output rather than left to be
inferred: the **IP5306's boost efficiency and brownout threshold** are not in
the pages this repo holds, so U2's dissipation is reported NOT COMPUTABLE and
the brownout point is unresolved; and the **SY8089's control loop** is not in
them either, so every transient here is open-loop.

**The headline number: +3V3 is 3.327 V, not 3.300 V.** It is derived, not
declared. `rails.py` walks the netlist from `U3.5` (FB) to the two resistors
on that node, decides which is which by asking which one reaches GND, reads
their values from the BOM, and applies the SY8089's own formula from page 2
of its application note — `Vout = 0.6 × (1 + R1/R2)` — with V_REF's
0.588/0.600/0.612 V from page 4:

```
0.600 × (1 + 100k/22k) = 3.327 V typ,  3.261 … 3.394 V from V_REF alone
```

Resistor tolerance is **not** in that spread, because the BOM does not state
it. A ±1% assumption would have widened it to roughly 3.20–3.46 V and looked
more rigorous while resting on nothing. The worst case as stated, 3.394 V, is
inside the 3.6 V limit of the ESP32-S3 and the SD card, so no violation is
raised — but the panel's own supply limit is unknown, because the panel is
still the one part with no datasheet in the repo (R25-HIGH-1).

An independent check falls out for free: the solver knows nothing about
V_REF, it only sees two resistors between `+3V3` and `GND`, and it puts
`BUCK_FB` at 0.600 V. If the divider had been mis-identified that number
would be wrong.

**Floating is reported, never defaulted.** 30 nets have no resistive path to
any source at DC. Two of them matter:

- `EN` — pins `U1.3` and `SW_RST.1`, switch open, no pull-up. This is
  R25-CRIT-1 reached from the physics instead of from reading a comment.
- `BTN_L` — R14 is DNP, so unlike the other eleven buttons it has no
  external pull-up and depends entirely on the ESP32's internal one.

A solver that assigned 0 V to those would have produced a complete, plausible
table with two lies in it.

**A scenario found a bug in the bench itself.** With `--buttons-pressed`,
every button read 3.83 V. Cause: closing a switch by shorting *every net the
reference touches* welded `BAT+` to `BTN_SELECT`, because `SW_PWR`'s four
shell tabs carry `BTN_SELECT` — the deliberate same-net fixup at
`routing.py:6055-6085`, whose own comment says it is harmless only because
the shell is isolated inside the component body. The bench now reads the
terminal-versus-mechanical split from `datasheet_specs`, where it is
declared. `test_vbench.py` holds the regression.

**Calibration: `no`, and every report says so.** The 105080 cell has no
datasheet in this repo, so `sources.py` refuses to make it a `Model` —
a `Model` would have to carry a page locator, and inventing one is the exact
failure the schema exists to catch. The OCV curve is declared as a generic
single-cell Li-polymer shape with `calibrated = False`. T5.4 replaces it with
two measurements from prototype #1.

**What T1.3 does not cover, in its own words.** Four parts now carry a cited
pin table — U2, U3, Q1, U5 — which is 27 of 271 pin instances. The tool
prints "covers 10% of the board's pins and no more" rather than "no conflicts
found", because those two sentences are not the same claim.

**T1.3 found a bug in T1.1.** With Q1 added it flagged `Q1.3 (D, power_out)`
as a second driver on `BAT+`. Q1 is not a second driver — it is what
*delivers* BAT+ from the cell — but the finding was real all the same, just
about the model rather than the board: `rails.py` was holding `BAT+` at the
cell voltage directly, as if it were a source, instead of deriving it through
the FET. Two things changed. The exemption is now a **derived rule** — a
driver on a rail is not in conflict if the same part draws power from a
different net, which makes it a converter or pass element, and which U2, U3
and Q1 all satisfy without anyone maintaining a list of pin names. And
`rails.py` now records that BAT+ equals BAT_IN only because a DC solve with
high-impedance loads carries no current; Q1's cited on-resistance is worth
about 70 mV at the gaming current, and T1.4 has to add it.

### T1.5 — junction temperatures, and which figures are honest

`make bench-thermal` prints Tj at both 30 °C external and 40 °C
in-enclosure, for idle / gaming / charge-and-play, with **40 °C governing
pass/fail** until the enclosure rise is measured. The arithmetic is the same
`Tj = T_amb + P·θJA` the existing gate uses; what is different is that every
dissipation figure is either derived from a cited parameter or declared not
computable:

| Part | Basis | Gaming at 40 °C |
|---|---|---|
| U3 SY8089 | conduction only, from the two cited R<sub>DS(on)</sub> and the derived duty D = 3.327/5 = 0.665. Switching loss **excluded** — no gate charge or efficiency curve at this operating point on the pages read, so this is a **lower bound** | 18.5 mW → 43.1 °C, margin +56.9 |
| Q1 Si2301CDS | I²·R<sub>DS(on)</sub>, cited. Uses the **steady-state 175 °C/W** from note d, not the 120/145 pair the table qualifies as "≤ 5 s" — a handheld is steady state | 24.5 mW → 44.3 °C, margin +80.7 |
| U5 PAM8403 | cited 90 % efficiency plus cited 6.3 mA standby → power only. **No Tj**, because no θJA appears on the pages read | 53.7 mW, Tj not computed |
| U2 IP5306 | **not computable.** Pages 2–4 give θJA and the absolute maxima but no boost efficiency | — |

θJA is the datasheet's own figure and the datasheets say what board they
measured on — 2″×2″ FR-4 with 2 oz copper and thermal vias for the SY8089
(page 4 note 2), 1″×1″ for the Si2301 (page 1 note b). This board gives both
parts less copper, so the real θJA is worse and these temperatures are
optimistic. No correction factor is applied: one chosen without measuring the
board's actual copper would be a number with no source. Measuring it from the
PCB is the next refinement.

**A discrepancy in the existing gate, left standing on purpose.**
`verify_thermal_budget.py` uses θJA = 80 °C/W for the IP5306 under a header
reading "from datasheets"; page 4 of that datasheet says **40 °C/W**. The 80
is not corrected, because doubling θJA raises the computed Tj — it is the
conservative direction, and restoring 40 would halve every temperature rise
that gate reports and make it more permissive on no evidence. A plausible
reason exists (an ESOP-8's 40 °C/W assumes an exposed-pad copper area the
page does not describe) but plausible is not recorded. The file now carries
the citation, the discrepancy and what closing it requires; `thermal.py`
reports U2 as not computable rather than inheriting either number.

T1.5's other ask is done: the ambient is a parameter, not a constant.
`T_AMBIENT` defaults to 40 °C so the gate's verdict is unchanged, and
`VBENCH_AMBIENT_C` overrides it for a what-if run.

### T1.4 — transients, and the ripple that agrees with itself

`make bench-transients` builds SPICE decks from the extracted netlist, the
BOM's real L and C values and the cited model parameters, runs them on
ngspice, and emits `t_3v3_valid`, `V_min` and ripple per scenario. It exits 2
if ngspice is missing: "no transient violations found" from a run that never
simulated anything is the worst output this bench could produce.

| Scenario | Result |
|---|---|
| +3V3 ripple at 430 mA | **2.860 mV pk-pk simulated** vs **2.836 mV closed-form** — 0.8 % apart |
| USB cold start | `t_3v3_valid` = **1.218 ms**, against the cited 1.2 ms soft-start; settles at 3.285 V |
| Bulk inrush | deck peak 84 A is an **upper bound, not a prediction**; a 3 A limited supply charges the 57 µF in C·V/I = **95 µs** |
| +3V3 load step, +100 mA | droop **1.8 mV**, V_min 3.279 V |
| Battery sag | at SoC 0.00: 3.000 V OCV − 38 mV cell (**uncalibrated**) − 68 mV Q1 (**cited**) = 2.894 V |

The ripple line is the one worth keeping. The switching node is driven at the
cited 1 MHz with the derived duty 0.665, through the BOM's 2.2 µH into the
BOM's 22.3 µF — and the closed-form buck result, ΔI = (V_in−V_out)·D/(L·f_sw)
then ΔV = ΔI/(8·C·f_sw), lands within 0.8 % of it. Two independent routes to
one number, neither of which was tuned to match the other.

**C28 contributes nothing to that 22.3 µF, and that is correct.** It is DNP,
so it has no BOM value, so it is absent from the deck. A reader adding the
schematic up would get 32.3 µF — which is the same gap
`verify_decoupling_adequacy.py` still has, and the reason
`make bench-transients` prints "C28 contribute nothing (DNP: no BOM value, so
no capacitor)" on every run.

**Three bugs in the decks, all mine, all found by running them.** They are
recorded because each was a plausible-looking model that produced a confident
wrong answer:

1. The first ripple run reported **6062 mV pk-pk**. The open-loop LC rings at
   f₀ ≈ 22 kHz with Q ≈ 25, and the measurement window opened 20 µs in, long
   before it decayed. The real regulator's feedback damps that ring; the loop
   is not modelled, so the ring is an artefact of the deck. Ripple is now
   measured in a late window and the test asserts the mean sits near the
   derived rail, which is what catches the window slipping again.
2. `v_out / i_limit` = 0.95 Ω was used as a stand-in for the current limit —
   in two different decks. A current limit clamps during startup; it is not a
   resistance the circuit contains. It put a permanent 0.36–0.50 V droop on
   the rail and made cold start settle at **2.963 V**, i.e. it invented a
   brownout. Both decks now use the buck's own cited conduction resistance,
   `D·R_DS(p) + (1−D)·R_DS(n)` = 0.100 Ω, and `r_conduction()` is the only
   series resistance either is allowed to use.
3. The unlimited inrush peak was reported as a **board failure**. It is a
   property of the deck: an ideal 5 V step into a discharged capacitor
   through 50 mΩ is V/R. It is now labelled an upper bound and paired with
   the current-limited charge time, which is the number an engineer can use.

## Phase 2 — Digital fabric: every ESP32 pin, every button, the switch — **DONE**

| Task | State | Where |
|---|---|---|
| T2.1 GPIO fabric | **done** | `scripts/vbench/pins.py` · `make bench-pins` |
| T2.2 button model | **done** | `scripts/vbench/buttons.py` · `make bench-buttons` |
| T2.3 SW_PWR `switch_off` | **done** — reproduces, does not report | `scripts/vbench/buttons.py` |
| T2.4 boot-mode model | **done** | `scripts/vbench/pins.py` |

`models/u1_esp32s3.py` carries the strapping tables from the module datasheet
(技术规格书 v1.3): table 4 page 13 for the internal pulls and their defaults,
table 5 for the timing, table 6 page 14 for the boot mode, table 7 page 15 for
VDD_SPI. It deliberately does **not** duplicate the 41-pin table, which lives
in `datasheet_specs.py::U1` and is already checked by `verify_datasheet_nets`.

**The boot mode is derived, end to end.** `pins.py` joins three things that had
never been joined: the netlist says what is attached to each U1 pad, T1.1's
resistive solve says what voltage that produces at reset, and the strapping
tables say what the chip does with it.

```
GPIO0  = 1   BTN_SELECT at 3.327 V from the board      -> boot mode, with GPIO46
GPIO3  = 1   BTN_R at 3.327 V from the board           -> JTAG source
GPIO45 = 0   BTN_L floats; internal pull-down decides  -> VDD_SPI 3.3 V
GPIO46 = 0   LCD_WR floats; internal pull-down decides -> boot mode, ROM log

BOOT MODE : SPI Boot        VDD_SPI : 3.3 V
```

Two things fall out that were previously only asserted:

* **Why R14 must stay DNP now has a page behind it.** GPIO45 selects VDD_SPI
  (table 7): 0 → 3.3 V, 1 → 1.8 V. An external pull-up would select 1.8 V and
  starve the N16R8's 3.3 V PSRAM. The bench derives this rather than being
  told, and `buttons.py` uses the same derivation to report BTN_L's missing
  pull-up as **required by design** rather than as a defect — the rule being
  "a strapping pin whose datasheet default is 0 must not carry an external
  pull-up", which needs no per-part list.
* **GPIO3 has no internal pull at all** (§3.3.4, page 15: "该管脚没有内部上下拉
  电阻"). Its strapping value must come from external circuitry that is not
  high-impedance. This board's pull-up on BTN_R satisfies that — but the
  requirement was nowhere in the repo, and a hand-written pull table would
  have flattened GPIO3 into "pull-down like the others".

T2.4's done-when, verbatim: `make bench-pins --hold BTN_SELECT` reports
`FAIL — the board enters Joint Download Boot instead of SPI Boot because
BTN_SELECT is held at reset — GPIO0=0, GPIO46=0`.

**T2.2** finds each button's pull-up and debounce cap in the netlist, reads
their values from the BOM, and computes the release edge: eleven buttons at
**τ = 1.000 ms** (10 k × 100 nF), rising to 70 % of the rail in **1.204 ms**.
That is the number a firmware debounce interval has to clear — shorter, and a
release reads as a second press.

**T2.3** is the opposite kind of assertion. `switch_off` must *reproduce* the
v1 invariant, and it does, with the reason derived from the copper rather than
quoted: SW_PWR's common pad sits on BAT+ and **its throw pads carry no net at
all**, so there is nothing to switch between. BAT+ and +3V3 are unchanged with
the switch operated. The scenario fails only if a rail moves — which would
mean the copper changed under a recorded limitation — or if the invariant
stops being recorded in `docs/known-issues.md`.

### A gate that computed a margin for a network that is not there

`verify_strapping_pins.py::test_en_rc_delay` reported an "EN RC margin =
36.5 ms" and passed. Every input to that number was wrong:

* It used **R = 45 kΩ** for a "WROOM-1 internal EN pull-up". The module
  datasheet says the opposite in its own words — page 28, note to figure 7: an
  RC delay circuit **must** be added at EN, R = 10 kΩ and C = 1 µF
  recommended. There is no on-module pull-up.
* It used **C = 100 nF** for "C3 on EN". C3 is not on EN; its pads are on
  +3V3 and GND (phase -1(d)).
* Its evidence that any of this held was a **grep of the schematic for the
  string `"R3 DNP"`**. A gate whose verdict depends on a comment existing
  cannot disagree with the comment. That is
  `feedback_comment_outranked_datasheet` implemented as a pass condition.

Rewritten to read the EN net out of the copper: it reports the two pads EN
actually has (`U1.3`, `SW_RST.1`), that there is **no** resistor to +3V3 and
**no** capacitor to GND, cites the datasheet requirement, and passes only
while that deviation is recorded in `docs/known-issues.md`'s RESPIN section.
It computes a time constant only from parts that exist. If the respin fits the
RC, the check switches to verifying the parts are there.

| Task | Deliverable | Done when |
|---|---|---|
| T2.1 | GPIO fabric model: all ESP32-S3 pins — direction, internal pull, drive strength, what the netlist attaches, and the reserved set (flash/PSRAM) | `make bench-pins` prints every pin with net, role, load and boot-time level |
| T2.2 | Button model: 12 buttons, external pull-up or DNP (BTN_L / R14 needs the internal pull), RC debounce with the real time constant, press/release as timed events | a press produces a level transition with the computed RC delay |
| T2.3 | SW_PWR switch model — including the known fact that it is **not** in series. The bench must *reproduce* "switch off, board still powered" as expected behaviour, not report it as a bench bug | scenario `switch_off` asserts the board stays powered, citing the v1 invariant |
| T2.4 | Boot-mode model: sample strapping pins at reset → resulting boot mode | a button held at reset that forces download mode is a FAIL with the pin named |

## Phase 3 — Peripherals: LCD, audio, SD — **DONE 2026-07-31, residue declared per module**

The eight missing documents landed in `hardware/datasheets/` on
2026-07-31 (official IP5306 V1.32, official Diodes PAM8403, the ILITEK
controller spec, SD Physical Layer Simplified v3.01, a SanDisk card
datasheet, the DNK battery family sheet, the Uniroyal resistor key), and
the halves below that were 'unbuilt and say so' were built against them:
the ILI9488 command/MADCTL/pixel-format/timing model (`ili9488_ctrl.py`,
`make bench-display` runs a frame and every write-side AC minimum at the
firmware clock), the cited 8-ohm output power and 24 dB gain with the
rail sag computed through the boost's derived output resistance, and the
SD protocol (`sdcard_protocol.py`, `make bench-sdcard`: CMD0/CMD8/ACMD41
init and CMD17 block reads of a real host file, byte-identical). What
remains open is what the documents themselves cannot support — the SPI
bus-timing section of the simplified spec is literally blank (p.147),
the panel MODULE still has no PDF, the vendor init register values are
the panel maker's — and each module prints its own residue.

### T3.1 — the display, seen from the panel

`make bench-display` builds the view no existing gate has. Every gate checks
J4 **by pad**: `datasheet_specs` declares 42 pads, `verify_datasheet_nets`
compares their nets, `verify_dfm_v2` checks the 41−N reversal is applied.
Nothing checks what the **panel** sees — and those are not the same question,
because the ribbon reverses the numbering.

The panel is a **40-pin FPC** and `pin N contacts pad 41−N`, so the bench walks
all forty pins to the net each one actually touches and the DC level T1.1
computes for it:

```
  17 DB0   -> pad 24  LCD_D0        38 IM0  -> pad 3  +3V3  3.327 V  1
  ...                                39 IM1  -> pad 2  +3V3  3.327 V  1
  24 DB7   -> pad 17  LCD_D7        40 IM2  -> pad 1  GND   0.000 V  0
```

Two checks only that view can express:

* **The interface mode is derived from the copper**, not read off a table:
  IM2=0, IM1=1, IM0=1 → 8080 8-bit parallel, which is what the firmware
  drives. Flip IM2 and the check stops agreeing.
* **DB0..DB7 must land on LCD_D0..LCD_D7 in order.** Crossing two data lines
  is invisible to every pad-side gate — each pad still carries a valid net and
  every net still has the right pad count — but it is a dead display. The
  mutation test crosses `LCD_D0`/`LCD_D1` and requires both panel pins to be
  named.

The pinout is **parsed** from `website/docs/design/components.md` §"FPC 40-Pin
Pinout", the file the repo names as the source of truth, so there is one table
rather than two. Parsing it needed care: components.md holds a second
five-column table immediately below — the IM2:IM1:IM0 mode table — and reading
every five-column row in the file let its rows overwrite panel pin 1, which
came out named "1". The parser now anchors on the pinout table's own header.

**Correction: the panel's datasheet IS in this repo.** Two of its pages are
checked in as images — `website/static/img/ili9488-fpc40-pinout.png` and
`ili9488-datasheet-specs.png` — and `components.md` has referenced them since
it was written. This plan and three modules said otherwise, which was true of
`hardware/datasheets/` and false of the repo. The difference is not academic:
reading those pages produced **R28-HIGH-1**.

The datasheet's pin table distinguishes unused pins **one from another**, and
no summary in this repo had carried the distinction:

| Panel pin | Datasheet says | Board does | |
|---|---|---|---|
| 12 RDX | "If not used, please fix this pin at VDDI or GND" | tied to +3V3 | correct, now citable |
| 13 SPI SDI | "If not used, please fix this pin at VDDI or DGND level" | **floating** (pad 28, no net) | **R28-HIGH-1** |
| 14 SPI SDO | "If not used, let this pin open" | open | correct |
| 8 FMARK/TE | 不用时悬空 — leave floating when unused | open | correct |

An unused **input** left floating is not the same as an unused **output** left
open. SDI is an input buffer with no internal pull the datasheet mentions;
floating, it can sit near threshold and draw shoot-through current in the
panel's controller. Severity is unquantified — the panel works on prototype #1
— but it is a datasheet requirement the design does not meet, and no gate
encoded it because `datasheet_specs.py` declares pad 28 `_unconnected()`: the
expectation *describes the copper*, so it agrees with it. Same shape as
R25-HIGH-1 and as C3/EN.

Not fixable in place: pad 28 is unrouted on a fabricated board. Respin: route
it to GND. `make bench-display` exits 1 on it, and `sd_and_display` pins the
fault count at exactly 1 so that fixing it fails the scenario just as loudly
as breaking another would.

What remains true is narrower: `models/_schema.py` accepts a citation only
from `hardware/datasheets/`, so a panel `Model` still cannot validate. Putting
those two pages there is what would change that.

So T3.1's other halves stay unbuilt and say so: the ILI9488 **controller**
command set, MADCTL and rotation, pixel format, and the setup/hold windows a
20 MHz pclk must satisfy all need the controller datasheet, which this repo
does not hold. No frame is rendered and no timing verdict is given, because
either would look like proof.

### T3.2 — audio, and the current it costs

`make bench-audio` walks the chain the netlist describes and computes what the
cited model supports:

| Quantity | Value | Where it comes from |
|---|---|---|
| Input high-pass corner | **33.9 Hz** | R20‖R21 = 10 kΩ and C22 = 0.47 µF, both from the netlist and the BOM |
| Output into 8 Ω | **1.8 W** | **CITED** since 2026-07-31: Diodes EC table p.4, 10 % THD at 5 V (supersedes the halved-from-4-Ω 1.50 W) |
| Rail current at full output | **429.8 mA** | cited 87 % efficiency at 8 Ω + cited 16 mA quiescent (Diodes p.4) |
| Sag on +5V at full output | **38 mV** | I × r_out_boost, derived from the IP5306's cited FET resistances at the battery floor |

The corner frequency also settles R25-LOW-1 for good: the two 20 kΩ in
parallel are the datasheet's **own application circuit** (figure 3, page 3 —
one 20 kΩ per channel) with INL and INR bridged for mono. The topology is
right; it carries one part more than a mono design needs.

**The gain is not modelled, so the WAV is parametrised by output level.** The
PAM8403's closed-loop gain is not on the pages this repo holds, so there is no
honest mapping from a DAC code to an output amplitude. `--wav` writes what the
speaker emits at a chosen fraction of the swing the supply allows —
memoryless gain and clipping only, no frequency response and no THD, because
neither is cited. The rail **sag** that 340 mA causes is likewise not
computed: the IP5306's output impedance is still unestablished.

### T3.3 — the SD bus, and a safety analysis about the wrong window

The four SPI signals land on the pads the socket datasheet assigns them, and
DAT1 is tied to DAT0/MISO as intended. The finding is elsewhere.

**U6.9 (DAT2) sits on the BTN_R net, and BTN_R is GPIO3 — a strapping pin.**
The assignment is deliberate: `routing.py:6055-6085` gives it the same net
because the BTN_R track crosses those pads, and concludes it is *"SAFE as long
as firmware stays in SPI mode (which it does — see software/main/sd.c)"*,
since a card tri-states DAT1/DAT2 once CMD0 has arrived.

The strapping sample happens **before any of that**. GPIO3 is latched at
reset, before the boot ROM runs, let alone `sd.c` — so the argument is about
the wrong window. In the reset window the card has had no CMD0 and DAT2 is not
tri-stated.

Whether it matters is a second question, and today the answer is no, for a
reason worth writing down rather than assuming: table 8 on page 15 shows GPIO3
is **ignored** unless `EFUSE_STRAP_JTAG_SEL` is burned, and the factory default
leaves it unselected. The exposure is real but inert — and it stops being inert
the day somebody burns that eFuse.

**The card protocol is not modelled.** CMD0 / CMD8 / ACMD41, the R1/R7
responses, block addressing and 20 MHz setup/hold all need the SD Physical
Layer Simplified Specification and a card datasheet, neither of which this repo
holds — `U6_TF-01A_MicroSD_C91145.pdf` is the **socket**. So T3.3's "mounts a
host folder and reads a ROM" half stays unbuilt rather than being faked with a
filesystem shim that would prove nothing about this board.



| Task | Deliverable | Done when |
|---|---|---|
| T3.1 | ILI9488 i80 model: command/parameter state machine, MADCTL/rotation, pixel format, 320×480 framebuffer, RST/CS/DC/WR setup-hold checks against the 20 MHz pclk | writes a frame and exports it as PNG; a timing violation is reported with the datasheet figure |
| T3.2 | I2S → PAM8403 → speaker: sample stream, gain, supply-dependent clipping, output power vs the 5 V rail, and current fed **back** into Phase 1 so audio peaks sag the rail | exports a WAV of what the speaker would emit, and the rail dip it caused |
| T3.3 | SD over SPI: card model, CMD0/CMD8/ACMD41 init, block read from a host directory, 20 MHz timing, current draw | mounts a host folder and reads a ROM through the modelled bus |

## Phase 4 — Firmware in the loop and the demo app — **T4.1, T4.3, T4.4 done**

### T4.1 + T4.4 — the simulator runs on the board model, with instruments

`make bench` builds and opens the Virtual Bench window: the existing SDL
simulator (all six emulator cores), recompiled with `vbench_hal.c` in place of
the fake HAL, plus a live instrument strip under the LCD. The bridge is
`software/sim/vbench_board.h`, **generated** by `make bench-header` from the
derived model — the C contains no electrical constant of its own, and a test
enforces that.

What "running on the model" buys, concretely:

* **Pixels travel through the i80 model.** Every byte crosses the bus through
  `VB_LCD_BUS_MAP` — the DBn ← LCD_Dm mapping derived from the netlist through
  the 41−N ribbon reversal. Identity today, so the picture is untouched; cross
  two data lines in the design and the simulator's picture visibly scrambles.
  If the IM straps stop selecting 8-bit 8080, the LCD shows no picture at all.
* **Buttons pass through the RC network.** A press shorts the node (instant);
  a release rises through 10 k × 100 nF and reads HIGH only after the derived
  1.204 ms. BTN_L, whose R14 is DNP because GPIO45 is a strapping pin, has no
  external RC and releases instantly — from `VB_BTN_RC_MASK`, not a special
  case in C.
* **Reset (F5) samples the strapping pins at that instant.** SELECT held means
  GPIO0 = 0: the app stops and the screen says JOINT DOWNLOAD BOOT, exactly
  like table 6 says the chip behaves.
* **SW_PWR (P) reproduces the v1 invariant**: operating it does NOT cut power,
  and the instrument line says so instead of pretending the board turned off.
* **The instruments are the bench test**: per-rail voltmeters (with the +3V3
  band from V_REF's own tolerance), an ammeter fed by the audio RMS through
  the derived efficiency, Tj for U3 and Q1 from the cited θJA, boot mode,
  EN FLOATING (R25-CRIT-1), and `CALIBRATION: no` — which stays there until
  prototype #1 measurements land (T5.4).
* Scenario keys: F1 USB/battery, F2/F3 SoC (battery sag uses the uncalibrated
  OCV table plus Q1's cited R_DS(on)).

The header is deterministic (no timestamps) and carries the `.kicad_pcb`
fingerprint; `export_header.py --check` fails when it is stale, and the test
suite proves the check discriminates by doctoring a rail value.

### T4.3 — scenarios (done earlier)

### T4.3 — scenarios, headless, with assertions

`make bench-ci` turns everything the earlier phases compute into **named
scenarios that say yes or no**, with JUnit output for CI. Six scenarios, 26
assertions, all against *derived* quantities:

| Scenario | What it pins down |
|---|---|
| `usb_cold_boot` | +3V3 inside 3.0–3.6 V, no cited limit exceeded, SPI Boot, VDD_SPI 3.3 V — and **EN asserted floating**, so the day the RC is fitted the scenario notices |
| `battery_3v4` | a nearly-flat cell still holds the rails, VBUS floating rather than 0 V, and the battery model asserting its own `calibrated == false` |
| `press_all_buttons` | a pressed button at ground, **BAT+ unmoved** (the SW_PWR shell-tab bug), eleven RCs not twelve |
| `switch_off` | the v1 invariant reproduced, with the reason derived: no throw pad carries a net |
| `audio_max` | 1.5 W into 8 Ω, rail current inside the boost's 2.1 A rating, no part over its thermal margin |
| `sd_and_display` | the SD bus on its socket's pad roles, the DAT2/GPIO3 exposure still exactly 1, the panel strapped for 8-bit 8080, the data bus in order |

The quantity names are **not free text**. Each maps to something a Phase 1–3
module computes, and a name the bench does not produce is a hard error — an
assertion nobody evaluates is the same failure as a gate nobody runs. So is a
scenario with an empty assertion list, which the loader refuses.

The assertions are shown to discriminate: holding `BTN_SELECT` in
`usb_cold_boot`'s setup breaks its boot-mode assertion.

T4.2 (`demo_app.c`) remains: its bench half is now trivial on top of
`vbench_hal`, but the "identical binary behaviour in both builds" clause
needs ESP-IDF, and no `idf.py` is installed here.



| Task | Deliverable | Done when |
|---|---|---|
| T4.1 | `vbench_hal`: `software/sim` recompiled against the board model instead of the fake HAL, so pixels travel through the i80 model and buttons through the RC network | the existing SDL simulator renders through the modelled bus |
| T4.2 | `demo_app.c`: one source compiled both against ESP-IDF (real firmware) and against the bench — rails/temps on screen, moving sprite, button test grid, audio beep, SD file list | identical binary behaviour in both builds |
| T4.3 | Scenario runner: YAML scenarios (`usb_cold_boot`, `battery_3v4`, `press_all_buttons`, `sd_missing`, `audio_max`, `switch_off`) with assertions; headless output = PNG + log + JUnit | `make bench-ci` runs headless, non-zero on failure |
| T4.4 | Interactive mode: SDL window, keyboard as buttons, instrument panel (per-rail voltmeter, ammeter, Tj) — the actual bench test | `make bench` opens the window with live instruments |

## Phase 5 — Make it a gate that cannot lie — **T5.1 T5.2 T5.3 DONE; T5.4 T5.5 await instruments**

Status 2026-07-31: T5.1 — `make bench-retro` rediscovers 22/22 corpus
entries and the count is computed, never written. T5.2 — the five named
mutations live in `test_vbench.py` section N (D/C swap, deleted pull-up,
WR to GND, +3V3-GND short) and `test_vbench_display.py` (MADCTL
rotation); writing them exposed and closed a real hole — no check
covered the panel's CONTROL lines, only the data bus
(`display.check_control_lines`). T5.3 — `test_vbench`,
`test_vbench_display` and `test_vbench_sdcard` are all in
`VERIFY_ALL_SCRIPTS`, routed by the `vbench` keyword law, and
`test_issue_dispatch` proves the routing. T5.4/T5.5 stay open: the user
has no bench instruments, and the fabricated board is a write-off, so
calibration waits for the next prototype. `CALIBRATION: no` stays on
every report, which is the design working as intended.

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
