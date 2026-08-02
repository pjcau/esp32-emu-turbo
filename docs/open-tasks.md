# Open tasks — the condensed to-do list for protection, testing and coverage

Condensed 2026-08-01 from the four audit documents now in `docs/archived/`
(`containment-roadmap.md`, `waiver-audit-recovery.md`,
`error-taxonomy-coverage-audit.md`, `virtual-bench-plan.md`). Everything in
those files that was DONE stays there; everything still actionable is here.

Two standing rules from those audits apply to every item below:

- A new gate goes into `VERIFY_ALL_SCRIPTS` **and** gets an owner rule in
  `scripts/issue_dispatch.py`, plus a mutation test. No soft-passes.
- `docs/known-issues.md` is the living record of what is broken on the
  board itself and is parsed by gates at that path — items here that
  overlap its section C point back to it rather than replacing it.

## High priority — real defect classes

### 1. ~~`collision.py` is default-open on pad nets~~ — DONE

Closed 2026-08-02. `routing.generate_all_traces()` now routes **twice** —
a discovery pass whose output is discarded, then the emitted pass seeded
with the pad→net map the first produced — so every routed pad is known
before the first trace is placed. Net 0 no longer means "not known yet",
it means "unconnected copper", and the skip that made net-0 pads invisible
is gone. The regenerated `.kicad_pcb` is **byte-identical**, uuids
included (the counter is rewound between passes).

Closing that default exposed a second one in the same function:
`register_pads` decided F.Cu vs B.Cu from a literal set of front-side
refs, and the set omitted the three fiducials — so F.Cu fiducials sat on
B.Cu, where the BTN_START track at x=12.20 passes through FID3, and that
reported as a 0.425 mm overlap. A modelling artefact, not a board defect
(different layers). The side is now derived from the placements via
`pad_positions.get_pads_and_layers()`.

Report goes 0 violations / 17 margin notes → **0 violations / 21 margin
notes**; the four newly visible pairs are 0.155–0.160 mm against the
0.175 mm house target and all clear JLCPCB's 0.15 mm minimum. Guarded by
`scripts/test_collision_pad_nets.py` (13 tests, registered in
`VERIFY_ALL_SCRIPTS` and given an owner rule in `issue_dispatch.py`);
reinstating the net-0 skip fails 2 of them, removing the uuid rewind
fails 3. Detail: `docs/known-issues.md` §C.

While adding the owner rule: `test_collision_via_metric` had no
`ROUTING_EXCEPTIONS` entry and was being ranked `dead-board` by
`law:via`, unlike every other mutation suite in the file. Both collision
suites are now declared `blind-spot`, matching `test_order_manifest`,
`test_enclosure_sync`, `test_test_points`, `test_esd_protection` and
`test_power_via_ampacity`.

### 2. ~~SW16 shell-isolation claim~~ — VERIFIED 2026-08-02

CLAIM-001 is now `VERIFIED-ON-DATASHEET`; the 2026-09-14 deadline is
retired. `SW16_Slide-Switch_C431540.pdf` states it twice, independently:

- Section 3.2, PDF page 4 (printed "Page 2/8"): insulation resistance
  **≥100 MΩ** measured at 100 V DC "**across terminals, and across
  terminals and cover**", for one minute. Repeated as technical note 2 on
  the outline drawing. Section 3.3 adds 250 V AC across terminals for one
  minute with no breakdown.
- The manufacturer's own circuit diagram (电路图, PDF page 1) draws
  terminals (1)(2)(3) as the slide contact strip and terminal **(4) as a
  separate node with an earth symbol, joined to nothing** — and the
  mounting reference view labels all four corner anchor pads (4).

Part identity reconciled while there: the datasheet is for **MSK12C02**
(Shenzhen Shouhan, spec A/0, 2015-03-26), so `footprints.py`'s comment is
right and `SS-12D00G3` is a legacy dict key. `schematics.md` said
SS-12D00G3 and now says MSK12C02.

One residual, recorded in the claim rather than acted on: the drawing
gives terminal (4) an **earth** symbol — the cover is meant to be
grounded, and this board ties 4b/4d to BTN_SELECT instead. Inert for the
switch, but it does leave GPIO0 reachable through exposed metal. That is
an ESD path, not a short, and no gate covers it.

### 3. ~~SD card-detect pad semantics — three sources, three stories~~ — DONE

Closed 2026-08-02. **U6 pad 9 is the socket's own `Cd` (card-detect)
contact.** The TF-01A drawing settles it directly:
`hardware/datasheets/U6_TF-01A_MicroSD_C91145.pdf` p.1, the "PCB Layout
(Pattern Side)" view, labels the pad row (1)(2)(3)(4)(5)(6)(7)(8) and then
**Cd**; the parts list is shell ×1 / spring ×1 / contact ×9 / housing ×1.
It is not DAT2 (that is pad **1**, left unconnected here) and not NC.

Root cause of the three-way split, worth keeping: SanDisk's pin tables are
the **full-size SD** tables — nine rows, every row headed "SD Card", under
"the host uses a dedicated 9-pin connector" (p.17 sec 3.1) — and they were
laid over this socket's nine *pads*. On full-size SD, contact 9 IS DAT2. A
microSD card has eight contacts, so everything past pad 8 shifted onto a
part that does not exist. The board's copper never made that mistake: pads
2/3/4/5/6/7 = CS/MOSI/VDD/CLK/VSS/MISO is correct microSD numbering.

All sources now say one thing: `verify_sd_interface.py` (was `PASS Card
detect (CD) connected to BTN_R`, now an INFO that names it as the socket's
contact and says no firmware reads it), `Makefile` `bench-sd`,
`datasheet_specs.py::U6`, `routing/_assemble.py`, `footprints.py`,
`vbench/sdcard.py`, `vbench/models/card_microsd.py`, `sdcard_protocol.py`,
`verify_dfm_v2.py`, `bringup_test/generate.py`, the hardware-audit skill
checklist, and `bring-up-protocol.md` (which was right that no card-detect
line is *read*, and now says why).

**Strapping, explicitly:** BTN_R is GPIO3, whose strap selects the JTAG
signal source and is *ignored* unless `EFUSE_STRAP_JTAG_SEL` is burned
(module datasheet table 8, p.15; factory default leaves it unselected).
A card pulling pad 9 low cannot change how this board boots.

**Resolved harder than the doc fix at the same time**: the parallel audit
round (R31-HIGH-2) reached the same Cd identification independently and
concluded the copper had to move — the TF-01A datasheet has no NO/NC
statement for the Cd blade, but *either* polarity grounds BTN_R in one
card state, so the BTN_R riser was rerouted east of the pad row and U6.9
is off-net. The residual bench reading (BTN_R empty vs loaded, verdict
table in `website/docs/manufacturing/bring-up-protocol.md`) is now a
built-from-post-R31-gerbers regression check, not an open safety question.
(The Cd claim briefly drafted as CLAIM-006 was superseded by the reroute;
CLAIM-006 in `hardware/CLAIMS.md` is the R31 Q1-orientation claim.)

## Medium priority — follow-ups from the ampacity gate (2026-08-01)

Left deliberately visible by the gate-coverage expansion (the gate prints
them as "not judged", it does not fail on them):

### 3. ~~BAT+ → L1.1 single-via feed~~ — DONE in v4.4.0 (c7a01bc)

Closed 2026-08-01. The branch was actually behind THREE serial single
barrels (the gate prints only the minimum cut — lesson recorded); the
planned IP5306_KEY re-route would have moved the bottleneck, not
removed it. Fixed by a second BAT+ stitching band (4x 0.90/0.45 at
y=47.55) + barrel-free B.Cu feed to L1.1 + dogleg deletion (5 dead
POWER_HIGH_ALLOWLIST waivers dropped). L1.1 cut: 0.527 A → 5.114 A.
Still open, smaller stakes: +3V3→U1.2 and +5V→U3.1 each sit behind one
0.527 A via, and SW16.2 (no load current by design) tops the printed
"not judged" list.

### 4. Per-load current budgets for `verify_power_via_ampacity`

Declaring per-load budgets would upgrade the gate from min-cut ampacity
to a feasibility max-flow. Until then the single-via feeds above are
printed but not judged.

### 4b. `verify_decoupling_paths` bounding-box metric weakness

Its "path length" sums every same-net segment whose midpoint falls in
the cap↔IC bounding box + 3 mm — not an actual path. C18→U2 sits at
3.8x/4.0 because the v4.4.0 stitching band lands in the box; the next
BAT+ copper near U2 trips the gate for the wrong reason. Fix the gate's
metric (real path walk), not the board.

## Small cleanups — known fix, known reason they are open

Detail for each lives in `docs/known-issues.md` §C; this is the index.

- ~~**R14 in `verify_netlist_diff.EXCLUDED_REFS`**~~ — VERIFIED
  2026-08-02 from four independent sources (BOM run has one gap at R14,
  qty 12; 0 of 94 CPL rows; the footprint is placed but pad 2 carries no
  net while R13.2/R15.2 are on +3V3; and R14 would strap GPIO45 = VDD_SPI
  HIGH, which kills the Octal PSRAM). Recorded at the exclusion site.
- ~~**`verify_bom_values.KNOWN_MAPPINGS`** maps `"fpc-16p-0.5mm" →
  40-pin`~~ — FIXED 2026-08-02. J4's schematic value is `FPC 40-pin 0.5mm
  Bottom Contact` at source now; the mapping is deleted and the gate
  passes on a real match (92/92). The symbol still draws 16 pins — that
  simplification is fine, naming a 16-pin part was not.
- ~~**`verify_copper_clearance`** reports `loc = (0,0,0,0)`~~ — FIXED
  2026-08-02. `_locate()` degrades through nearest-points →
  representative-point → bbox centre and marks approximations with `~`;
  no path returns zeros, which mattered because (0,0) is a real board
  coordinate.
- **`verify_bom_values.KNOWN_MAPPINGS` still maps `"ili94883.95in8080"`
  onto the same 40-pin BOM comment** — left alone deliberately. That is
  DS1, the schematic-only logical panel symbol whose physical part IS J4
  (already `T3_ALLOW`'d in `verify_netlist_diff`), so the two names
  describe different things on purpose. Not the same defect as the
  `fpc-16p` entry, which named the wrong part.
- **J4's schematic symbol is emitted with `(dnp no)` like every other
  part, and so is R14** — `generate_schematics/kicad_primitives.py` hard-
  codes `dnp no`, so the schematic cannot express DNP at all. Cosmetic
  today (the BOM and CPL are what the fab obeys, and R14 is absent from
  both), but it means a reader of the schematic alone would fit R14 and
  kill the PSRAM.
- **`verify_easyeda_footprint._GEOMETRIC_MISMATCH_ALLOWLIST`** still holds
  U2 (90°) and LED2 (180°). Both angles are now *explained* (H4/H6 closed)
  but the allowlist is a tolerance, not a proof — replace with a derived
  check if it ever grows.

## Blocked — waiting on bench instruments

- **vbench T5.4 / T5.5** (calibrate models against a live board; close the
  loop with measured rails). The user has no bench instruments — photos
  only. Unblocks if instruments ever arrive; until then the bring-up
  firmware (`software/bringup_test/`) is the measuring device.

## Already closed — do not redo

- Waiver audit Part 2: O1 (CPL rotation law, incl. D1/Q1/LED2), O2 (VBUS
  widths), O3 (R20/R21 → PAM_VREF, `ee0ec02`), O4 (phantom nets).
- The containment roadmap's six layers all landed.
- **Error-taxonomy gaps 15–18 all landed 2026-08-01** via the
  gate-coverage expansion merge: `verify_enclosure_sync` (`7b51eda`, also
  fixed a battery pocket that could not hold the 105080 cell),
  `verify_test_points` promoted to blocking (`e68347a`),
  `verify_esd_protection` net-verified via the claims ledger (`21716ec`),
  `verify_power_via_ampacity` (`0d456be`, 5 starved transitions fixed).

See `docs/archived/` and memory `HISTORY.md` for the full records.
