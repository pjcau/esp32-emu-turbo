# Waiver audit — recovery roadmap

Audit of every deroga (waiver, allowlist, suppression, soft-pass) across the
100 scripts in `scripts/`, run 2026-07-25 on branch `worktree-isolation-gate`.

The question that drove it: **are these waivers still valid, are they still
needed, and do any of them hide a defect of the same class as the missing
+3V3 inner-layer link that produced the v1 dead board?**

Answer: three of them did. They are fixed. Six items remain open and are
listed in Part 2 with the exact next step for each.

---

## Baseline — verify before resuming

```
make verify-all          # 59 checks — expect 56 pass / 3 fail (see Part 2)
make verify-isolation    # 13/13
make verify-power-nets   # 5/5, +3V3 = 1 group, 98 items, 29 pads
python3 scripts/verify_dfa.py     # 9/9
python3 scripts/verify_dfm_v2.py  # 122/122
python3 scripts/drc_native.py --run --no-zone-fill   # 0 violations
```

The three expected failures are `verify_cpl_rotation_law`,
`verify_net_class_widths`, `verify_netlist_diff`. They are **real open
problems, not waivers** — see Part 2. Everything else is green.

`hardware/` was not modified by this audit. The regenerated CPL is
byte-identical to `release_jlcpcb/cpl.csv`, so **nothing needs re-uploading
to JLCPCB** as a result of Part 1.

---

## Part 1 — DONE (do not redo)

### 1.1 CPL rotation overrides became additive deltas

`_JLCPCB_ROT_OVERRIDES` → `_JLCPCB_ROT_DELTAS` in
`scripts/generate_pcb/jlcpcb_export.py`.

The old table returned an **absolute** CPL angle and discarded `rot` and
`layer` entirely. Rotating an overridden part in the layout changed the
copper but not the CPL, so the part would be assembled at the stale
orientation with no gate able to notice. That is the mechanism that let D1
carry a frozen 270° that was 180° out for months.

Deltas are added on top of the placement formula, so a layout rotation now
propagates automatically.

| ref | package | KiCad rot | formula | emitted | delta |
|---|---|---|---|---|---|
| U5 | SOP-16 | 90° bottom | 180° | 180° | **0 — entry deleted** |
| J4 | FPC-40P | 90° bottom | 90° | 270° | 180 |
| LED2 | LED_0805 | 0° top | 0° | 180° | 180 |

The identifier was renamed deliberately: the semantics changed, so every
consumer had to be revisited rather than silently inheriting the new
meaning. Consumers updated: `verify_dfa.py`, `verify_dfm_v2.py`,
`verify_easyeda_footprint.py`, `test_cpl_rotation_law.py`,
`analyze_pin1_marker.py`, `footprints.py`, `verify_cpl_rotation_law.py`.

**Verified:** all 81 components emit the same angle as before; `export_cpl()`
output diffs clean against `release_jlcpcb/cpl.csv`.

### 1.2 A tautological test in `verify_dfm_v2.py`

Removing the dead U5 entry exposed it. `test_batch_pin_alignment` transformed
every pad twice — once with `kicad_rot`, once with `cpl_rot` — and required
the two clouds to coincide within 0.1 mm. That is `cpl_rot == kicad_rot`
written geometrically, which for a bottom-side part is false by construction:
the difference *is* the purpose of `_JLCPCB_ROT_CORRECTIONS`. It passed
U1/U2/U3/J1/U6 by tautology (their correction nets out to 0°) and needed the
override table as an excuse list for U5 and J4, the only two where it bit.

Replaced with the assertion that actually holds — the CPL file on disk
carries the angle the generator computes today, i.e. the stale-upload check —
applied uniformly to all 7 refs with no exception branch. Geometric
correctness is proven positively by `verify_cpl_rotation_law.py` instead.

A layer-vocabulary bug was found and fixed while doing this:
`_component_placeholders()` reports KiCad layer names (`B.Cu`) while
`_jlcpcb_rotation()` expects `bottom`, and passing the raw name silently
takes the top-side branch, skipping the mirror and the package correction.

### 1.3 `drc_native.py` — 7 suppressions promoted to real issues

DRC reports 0 violations of every type, so this is a no-op on the current
board and purely a change to what a future regression may do quietly.

Removed from `KNOWN_ACCEPTABLE`, now in `REAL_ISSUES`:

- `isolated_copper` (CRITICAL) — "small fills removed during manufacturing"
  is the **exact signature of the v1 dead board**. An isolated fill is not
  swarf, it is an open circuit.
- `via_dangling`, `track_dangling` (CRITICAL) — justified as "before zone
  fill", but `--run` fills zones *then* runs DRC. Post-fill dangling = open.
- `clearance_zone` (HIGH) — "JLCPCB adds thermal relief automatically" is an
  assumption about the fab, not a property of the design.
- `clearance_borderline` (HIGH) — blessed 0.075–0.09 mm, below the 4-layer
  minimum this repo enforces everywhere else.
- `hole_clearance` (HIGH) — "intentional via-in-pad" is stale;
  `verify_via_in_pad`'s `KNOWN_INTENTIONAL` is empty and the gate passes.
- `courtyardOverlap` (MEDIUM) — courtyard overlap is how parts collide at
  assembly.

Kept: `solder_mask_bridge`, `lib_footprint_mismatch`, `text_height`.

Also fixed: `analyze_drc()` returned `real_count`, so **uncategorized
violation types exited 0**. Now returns `real_count + unknown_count` — an
unclassified DRC type arriving in a KiCad upgrade can no longer report CLEAN.

### 1.4 `verify_copper_clearance.py` — three silent swallows removed

The one at the net-union site dropped an **entire net** from the comparison
when its geometry failed to union, and the gate still printed PASS. A
clearance gate that silently stops looking at +3V3 is worse than no gate.
Instrumented before removal: 192 unions, 0 failures — it was latent, not
live.

### 1.5 `verify_decoupling_paths.py` — stale table entry was a soft pass

`("C2", "U3", "+3V3", "bulk")` referenced a part deleted in the
AMS1117 → SY8089 swap. A missing pad produced `SKIP`, which the summary did
not count as a failure, so **the buck converter's output bulk capacitor path
was unverified**. Corrected to `C30` (the 22 µF MLCC next to L2.1); a missing
pad is now `FAIL`. Result: `C30→U3 (+3V3)` path 6.15 mm, ratio 0.8×.

### 1.6 `verify_design_intent.py` — `KNOWN_SINGLE` pruned and made self-cleaning

`LCD_BL`, `LCD_RD`, `BTN_MENU` had zero pads on the board. A waiver for a net
that no longer exists is not harmless: it stands ready to greet a regression
that recreates a floating `LCD_BL` with "single-component (by design)".

Kept `I2S_BCLK` / `I2S_LRCK`, verified genuinely correct: `software/main/audio.c`
uses `I2S_PDM_TX` with `.clk = I2S_GPIO_UNUSED` and drives only `I2S_DOUT`
(GPIO17) into C22 → PAM8403, an analog amplifier. Neither clock net carries
any segment or via, so there is no dangling copper either.

Added a stale-entry check, and split the severity: 1-component nets FAIL
(real orphan), 0-component nets WARN and are named (generator leftover, no
copper, cannot fault).

### 1.7 `routing.py` — a wrong rationale corrected

The "orphan +3V3 fill island" note on the LCD_RD via is empirically stale
(+3V3 is one connected group and J4.29 is in it). It is kept because its
**reasoning** must not be copied: it argued that losing pad 29 is "redundancy
only" because the display has five other +3V3 pads. Pad 29 is not a supply
pad — it is the panel's RD strobe, hard-tied HIGH because the display is
write-only. On an orphan island it is a **floating CMOS input**, not lost
redundancy.

### 1.8 Gate coverage — the waiver by omission

The four newest gates existed only as standalone Makefile targets and were
absent from `VERIFY_ALL_SCRIPTS`, so `make verify-all` did not run the
isolation gate that HEAD's own commit message requires on every change.

Added: `verify_isolation`, `verify_cpl_rotation_law`,
`verify_jlcpcb_via_rules`, `verify_schematic_crossings`,
`test_cpl_rotation_law`, `test_power_net_integrity`. 53 → 59 checks. Every
`verify_*.py` and `test_*.py` in `scripts/` is now gated.

### 1.9 Mutation tests repaired

`test_cpl_rotation_law.py`'s injector wrote the planted angle straight into
the table, which under delta semantics **replaces** a part's real delta. For
J4 and LED2 a planted 180° would cancel against their configured 180° and
emit the correct angle — the test would then report the gate as asleep when
it was the injector that never moved the part. Now adds to the existing
delta, and asserts the table actually changed. 5/5.

---

## Part 2 — OPEN

### O1. CPL rotation law: U2, U4, J4 disagree — J1 unevaluable

`make verify-cpl-law --verbose`. **Highest stakes item here**: each is a
claim about the physical orientation of a part on a board that has been
fabricated.

| ref | LCSC | law wants | emitted | gap |
|---|---|---|---|---|
| U2 | C181692 ESOP-8 | 90° | 0° | 90° |
| U4 | C7519 SOT-23-6 | 0° | 90° | 90° |
| J4 | C2856812 FPC-40P | 90° | 270° | 180° |
| J1 | C2765186 USB-C | — | 0° | UNEVALUABLE |

- **U2** — evidence runs *against* the law. Boards R4–R8 charge over USB-C
  and boost to 5 V through the IP5306, and an ESOP-8 rotated 90° could not
  seat on its pads at all. Most likely a law false positive. Next step:
  record `_LAW_EXCEPTIONS["U2"] = (90.0, <reason>)` stating the physical
  claim — the entry must name the residual so drift re-fails.
- **U4** — the credible bug. `^SOT-23` in `_JLCPCB_ROT_CORRECTIONS` applies
  −90° to both SOT-23-3 and SOT-23-6, but EasyEDA draws the two families in
  frames 90° apart (`jlcpcb_export.py` says so in its own comment: SOT-23-3
  has pads 1/2 in a column, SOT-23-6 has 1/2/3 in a row). Q1 (SOT-23-3)
  satisfies the law; U4 does not. **If the law is right the fix is to split
  the regex, NOT to add a per-part delta.** Deciding test: JLCPCB 3D preview
  for C7519.
- **J4** — 180° delta with no geometric derivation, only "JLCPCB 3D: 90° puts
  pins on wrong side". Same shape as the D1 bug that was 180° out.
  Deciding test: JLCPCB 3D preview for C2856812, plus whether the display
  works on proto #1. Note this is a *different axis* from the documented
  `connector_pad = 41 − panel_pin` netlist reversal — do not conflate them.
- **J1** — `_row_bearing()` returns `None` because the USB-C footprint has
  duplicate/unnumbered shield pads. Needs a pad-pair selection that skips
  shield tabs, otherwise this connector is permanently outside the law.
- **LED2 reports OK — that does NOT settle the open question.** The law
  derives its reference from the bearing of EasyEDA's **pad 1 → pad 2**
  vector, i.e. it assumes the machine aligns by pad numbers. That is one of
  the two competing readings, so the gate cannot arbitrate between them. The
  visual check on proto #1 is still the deciding test. See the memory note
  `project_led2_override_suspect.md`.

### O2. VBUS traces below the Power High minimum

`verify_net_class_widths` — 4 segments at 0.273 mm against the 0.50 mm class
minimum, on B.Cu near the USB-C escape:

```
(77.6, 68.8)   (82.4, 68.8)   (77.5, 69.0)   (81.8, 70.2)
```

Not covered by `POWER_HIGH_ALLOWLIST`, which contains only the BAT+ corridor.
Two honest resolutions: widen them, or add coordinate-pinned entries with an
IPC-2221 current-carrying argument, the way the BAT+ entries are written.
VBUS carries USB charging current, so the calculation has to be done, not
assumed.

### O3. Schematic ↔ PCB netlist mismatches

`verify_netlist_diff` — 8 mismatches in three groups.

**R20 / R21 — a real electrical defect, the most important open item.**
Two 20 kΩ resistors sit between the amplifier-side input node and GND instead
of `PAM_VREF`. That puts a 10 kΩ DC load on the PAM8403's internal bias
(datasheet pin 8: "internal reference source, connect a bypass capacitor from
VREF to GND"), pulling the input operating point below mid-supply →
asymmetric clipping. On the source side of C22 they would be harmless; they
are not on the source side.

Fix: reroute `R20.1` and `R21.1` from their GND vias to the `PAM_VREF` node
at `C21.2`, through a region `routing.py` has already tuned for clearance
against SPK+, C23 and the U5 pad row. Needs its own DFM/DRC pass.

Note `_T4_STRUCTURAL_EXCEPTIONS` no longer matches these — the schematic net
was renamed `I2S_DOUT` → `PAM_IN_AC`, so the exact 4-tuples went stale and
the mismatch resurfaced. **That is the mechanism working as designed** (an
exact-tuple exception rots loudly), not a new bug.

**C4.2 / C26.2** `sch='+3V3' pcb='GND'` — pin-numbering orientation flip on
two non-polarized 100 nF caps. Electrically harmless. Fix in
`scripts/generate_schematics/sheets/mcu.py` around lines 110–132.

**R16.2 / U2.5** `'/Power Supply/KEY'` vs `'IP5306_KEY'` — hierarchical local
label vs global name. `T2_ALLOW` covers one direction, `T1_ALLOW` does not.
Fix: emit a global label named `IP5306_KEY` on that wire in the Power Supply
sheet, then delete the `T2_ALLOW` entry.

### O4. Phantom net declarations

`LCD_BL` and `LCD_RD` remain declared in `primitives.NET_LIST` with zero
pads (currently a WARN in T5). Removing them is the real cleanup, but a PCB
regeneration drops every `filled_polygon` — measured at 7695 diff lines — so
it needs a zone re-fill and a `release_jlcpcb/` sync. Attempted during this
audit and deliberately reverted: disproportionate blast radius for two unused
lines. Bundle it with the next change that already regenerates the board.

IDs 18/19 can be left as gaps; `NET_ID` and `_NET_NAME` are name-keyed dicts
and the IDs are explicit in the tuples, so nothing downstream renumbers.

### O5. `collision.py` is default-open on pad nets

`_KNOWN_PAD_NETS` (`collision.py:215`) has 4 hardcoded entries. Every other
pad is registered with `net=0`, and **net=0 pads are skipped in collision
queries** (`collision.py:125`). A pad only acquires a net when the first
trace touches it (`collision.py:466`), so a pad the router never targets
stays invisible to collision detection forever and a trace can be routed
straight over it.

Contained today only by the post-hoc gates — `verify_trace_through_pad`,
`short_circuit_analysis`, `analyze_pad_distances` — all of which pass. The
Makefile's own description of `verify-trace-through-pad` ("catches fab-shorts
from missing `_PAD_NETS`") shows this class has bitten before.

Fix: seed pad nets from `routing._PAD_NETS` / the datasheet spec map before
routing begins, so the router is default-closed.

### O6. Smaller waivers reviewed but not yet acted on

- `verify_bom_values.KNOWN_MAPPINGS`: `"fpc-16p-0.5mm" → 40-pin` maps over a
  real schematic/BOM inconsistency. Fix the schematic symbol value instead.
- `verify_easyeda_footprint._GEOMETRIC_MISMATCH_ALLOWLIST`: still holds U2
  (90°) and LED2 (180°). Both are tied to O1 — resolve together.
- `verify_netlist_diff.EXCLUDED_REFS` contains `R14`, documented as DNP.
  **Not independently verified in this pass** — confirm R14 is genuinely
  do-not-populate before trusting the exclusion.
- `verify_copper_clearance`: the `nearest_points` fallback still reports
  `loc = (0,0,0,0)` on failure. It does not suppress the violation, only
  misreports its coordinates.
- `verify_net_connectivity.ACCEPTED_FRAGMENTATIONS["VBUS"]` (3 components,
  J1.9/J1.11 isolated) — **valid, keep**. Documented, real, functional
  single-orientation workaround, tracked as R5-CRIT-9 for the v2 respin.
- `POWER_HIGH_ALLOWLIST` BAT+ entries — **valid, keep**. Coordinate-pinned to
  0.02 mm with an IPC-2221 argument; cannot drift silently.
- `verify_stackup.IN2_ALLOWED_NETS` includes VBUS, which pours 0 mm².
  Harmless and unused.

---

## Principle that came out of this

Three distinct waiver shapes were found, and they fail differently:

1. **Absolute overrides** (`_JLCPCB_ROT_OVERRIDES`) freeze a value and stop
   tracking their input. They rot silently. → make them deltas.
2. **Exact-tuple exceptions** (`_T4_STRUCTURAL_EXCEPTIONS`, `_LAW_EXCEPTIONS`)
   restate the value they expect, so drift re-fails. They rot loudly. → the
   shape to prefer.
3. **Category suppressions** (`KNOWN_ACCEPTABLE`) hide a whole class forever
   and are invisible while the count is zero. → promote to real issues and
   let the gate speak.

And the coverage lesson: a gate that is not in `verify-all` is a waiver of
everything it checks. `make verify-all` now runs all 59.
