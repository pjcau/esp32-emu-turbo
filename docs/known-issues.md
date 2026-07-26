# Known issues — what is still broken

Everything in this file is **open**: it fails a gate, or it is an
unverified claim about a board that has already been fabricated. Nothing
here is a plan, a nice-to-have, or a closed finding. Closed work lives in
`docs/waiver-audit-recovery.md` (Part 1) and `hardware-audit-bugs.md`.

**This file is a snapshot, the gates are the truth.** Measured on
`35d6454`, 2026-07-26, macOS + local `kicad-cli`. Before acting on any
entry, re-derive the current state:

```bash
make open-issues     # the 6 gates that guard known-open work (~10 s)
make verify-all      # the exhaustive suite, 68 checks (~20 s)
```

At the snapshot commit: `verify-all` is **68/68** and `open-issues` reports
**all clear**. Every entry below names the gate that proves it, so a fixed
entry goes green on its own rather than needing this file edited to stay
honest. If an entry's gate is green and the text still says open, **the
gate wins** — delete the entry.

No gate is red right now. That is not the same as "nothing is open": the
entries that remain are unverified claims about an already-fabricated
board (H6), and closed records kept because each documents a way a gate
can be fooled (H1–H5). A green suite means no check currently disagrees
with the design — it does not mean the design was checked against the
physical board.

Reading order is by consequence, not by section. **H4 was the entry that
could put a wrong part on the desk, and it is now closed**: both of its
rows were generator bugs and were fixed at the source in `35d6454`, with
`_LAW_EXCEPTIONS` still an empty dict. H6 is now the only entry that
depends on evidence no gate can produce.

---

## H — Hardware: the design or the board is wrong

### H1. Three copper stubs end in the air — CLOSED

**Gate:** `verify_dangling_copper.py` — PASS
**Introduced:** pre-R24, first visible when the gate was written (no
earlier gate could see this class). Closed by the routing changes in
`397c854`.

| net | layer | end point |
|---|---|---|
| GND | B.Cu | (108.500, 44.000) |
| GND | B.Cu | (109.300, 44.000) |
| VBUS | F.Cu | (90.950, 61.000) |

Each is a track end that reaches no pad, no via, no other segment and no
zone. The nets are connected elsewhere, so DRC and the connectivity gates
stay green — that is exactly why this needed its own gate. A stub is
still a routing mistake: it is unterminated copper on a finished board.

**Fix:** delete the segments in `scripts/generate_pcb/routing.py`, or
terminate them where they were meant to land. Regenerating the PCB drops
every `filled_polygon`, so this needs a zone re-fill and a
`release_jlcpcb/` sync — bundle it with H3, which touches the same area.

### H2. Schematic and PCB disagree on 7 pin↔net assignments — CLOSED

**Gate:** `verify_netlist_diff.py` [T4] — PASS, 0 mismatches

Resolved in three different ways, because they were three different
problems and only one of them was a wiring error:

- **J3.1 / Q1.2** — fixed in `power_supply.py`; the schematic had the
  battery path drawn on the wrong side of the protection FET.
- **U1.3** — fixed in `mcu.py`; EN is now its own net with a global label
  matching the PCB net name. The schematic had it tied to +3V3, which
  also meant SW_RST was drawn shorting the rail to ground on every press.
- **LED1 / LED2** — *not* rewired. A pin-vs-pad numbering translation in
  `SCH_PIN_TO_PCB_PADS` (`_LED_MAP`), with each side checked
  independently: on the PCB pad 2 carries `LED{n}_RA` through R17/R18 to
  +3V3 and pad 1 carries GND; in the schematic pin 1 (A) carries
  `LED{n}_RA` and pin 2 (K) carries GND. Same circuit, different numbers.
  A wrong entry there still fails T4, exactly as for J1/J4/U5/U6. **This
  does not answer H6** — the CPL override question is untouched.
- **C3** — the schematic was describing a circuit the board does not
  have; see the RESPIN section below.

Also added to the table while closing this: `SW_RST` and `SW_BOOT`, which
had never been in it because their schematic pins were floating, so no
pin of theirs ever reached the comparison. Adding them immediately caught
`SW_BOOT` drawn on the wrong pole.

Historical record of the original 7:

```
J3.1    sch='GND'       pcb='BAT_IN'
Q1.2    sch='GND'       pcb='BAT_IN'
U1.3    sch='+3V3'      pcb='EN'
LED1.1  sch='LED1_RA'   pcb='GND'
LED1.2  sch='GND'       pcb='LED1_RA'
LED2.1  sch='LED2_RA'   pcb='GND'
LED2.2  sch='GND'       pcb='LED2_RA'
```

Note the R20/R21 PAM8403 bias mismatch documented in
`docs/waiver-audit-recovery.md` §O3 is **closed** upstream (`ee0ec02`) —
that document is stale on this point, this list is current.

### H3. Four VBUS segments below their net-class minimum — CLOSED

**Gate:** `verify_net_class_widths.py` — PASS

Four B.Cu segments at **0.273 mm** against the 0.50 mm Power High
minimum, all at the J1 (USB-C) fan-out:

```
(77.6, 68.8)   (82.4, 68.8)   (77.5, 69.0)   (81.8, 70.2)
```

This entry used to offer "two honest options, no third: widen the
segments, or add coordinate-pinned allowlist entries with an IPC-2221
calculation". Widening turned out not to be one of them.

The first two are **inside their own land**: the copper there is the
0.55 mm pad, not the 0.273 mm line, so there is no neck to widen.
`_buried_in_own_pad` exempts them on the pad's *inscribed circle*, which
is rotation-proof and can therefore only ever exempt less than it should.

The other two are the escape diagonals, and 0.50 mm is unreachable there
by any routing. Both features that pin the gap belong to J1 itself — the
moulded peg hole and the corner of land 10 — so nothing on the board can
move to open it. `routing.py:3596-3660` solves the width from the
connector's datasheet dimensions instead of typing one in (0.293 mm
budget), and a maximin-clearance path search over an exact B.Cu clearance
field agrees to 5 µm: 0.2888 mm, pinch at (77.795, 69.485). The
alternative escape upward measures 0.170 mm and is blocked anyway.

So only the second option existed, and the calculation is now done and
attached to the rows in `POWER_HIGH_ALLOWLIST`: 0.273 mm carries 0.93 A
alone at a 10 °C rise; this gate is a ~9.7 mΩ parallel bond across two
extra connector contacts (~20 mΩ) while land 2 keeps its own 0.60 mm run
as the supply path, so its share of the 2.1 A peak is ~0.7 A → ~5 °C.
Even the whole 2.1 A through one escape is ~13 °C on a 1.4 mm segment
that sinks into a land at one end and a 0.76 mm bus at the other.

Not a suppression: the gate still prints both rows on every run, and
because the width is derived rather than typed, any change to the
footprint or the clearance constants moves the coordinates, stops the
rows matching, and turns the gate red again.

### H4. The CPL rotation law disagrees with two placements

**Gate:** `verify_cpl_rotation_law.py` — FAIL
**Result:** OK 12 · FAIL 2 · UNEVALUABLE 0 · NOREF 0 · total 14

| ref | LCSC | package | layer | law wants | CPL emits | gap | state |
|---|---|---|---|---|---|---|---|
| U2 | C181692 | ESOP-8 | bottom | 90° | 0° | 90° | **open** |
| J4 | C2856812 | FPC-40P | bottom | 90° | 270° | 180° | **open** |
| U4 | C7519 | SOT-23-6 | bottom | 0° | 0° | — | closed, `1765982` |
| J1 | C2765186 | USB-C | bottom | 0° | 0° | — | now evaluable, OK |

**U4 is closed and it was the credible bug, as this entry predicted.** The
fix was splitting the regex, not a per-part delta: `^SOT-23` applied −90°
to SOT-23-3 and SOT-23-6 alike, but EasyEDA draws the two families 90°
apart, and the two parts differ by nothing else —

```
Q1  SOT-23-3  C10487  row_board=180  row_ee=270  cpl=90   OK
U4  SOT-23-6  C7519   row_board=180  row_ee=  0  cpl=90   FAIL
```

U4's cell `(180, 0, bottom)` also holds J1 and SW_PWR, both OK at cpl=0,
and J1's orientation is confirmed on fabricated hardware. **Consequence:
the assembled boards carry a USBLC6 placed 90° out.** It survived because
it is the one part whose misplacement is invisible — shunt ESD diodes, so
USB enumerates without them.

**What is left, and why it is not guessable.** Both remaining parts sit in
the law's single cell with no OK sibling, `(row_board=90, row_ee=0)`. That
cell being untested is *not* an escape route: U2 is off by 90° and J4 by
180°, so no cell-level correction explains both, and they have to be
judged individually. On the generator side each has a named, precedented
bug pattern — U2's `ESOP-8` misses the `^SOP-` regex by one letter, the
same shape as U4; J4 is the only live entry in `_JLCPCB_ROT_DELTAS`,
justified by a note with no derivation, which is exactly how D1 carried a
wrong 270° for months. Neither has a pattern on the law's side.

That is a strong case and it is still not proof, so neither has been
flipped: U2 wrong means a charger that cannot solder, J4 wrong means a
dead display. **Deciding test: the visual check below.**

**Highest-stakes item in this file.** Each row is a claim about the
physical orientation of a part on a board that has been fabricated.

- **U2** — the counter-evidence is that boards R4–R8 charge over USB-C and
  boost to 5 V through the IP5306, and an ESOP-8 rotated 90° could not seat
  on its pads at all. Weigh that against the generator-side pattern above,
  and note the counter-evidence has a hole: it assumes the boards were
  assembled from the CPL the generator emits today.
- **J4** — this is a *different axis* from the documented
  `connector_pad = 41 − panel_pin` netlist reversal — do not conflate them
  (see "Do not fix" below).

`_LAW_EXCEPTIONS` in the gate is an **empty dict**, so what is known about
these parts — and it is written down, in `jlcpcb_export.py` comments —
cannot reach the gate.

**Deciding test, and it is two questions on one board:**

1. Is the IP5306 (U2) sitting square on its footprint, or across it? A 90°
   error on an ESOP-8 is not subtle and does not solder.
2. Does the display light and show a correct image with the FPC inserted as
   designed? That answers J4's 180°.

Either fix the footprint afterwards, or record a `_LAW_EXCEPTIONS` entry
that states the physical claim and names the residual, so drift re-fails.
The JLCPCB 3D preview for `C181692` and `C2856812` is the same evidence if
opening the prototype is not convenient.

**This also settles H6.** The LED2 override question turns on the same
reasoning pattern — "the board works, therefore the hand-written override
is right" — so one look validates or destroys the pattern, not just one
part.

**A design-side fix here is not done until the CPL is re-uploaded** and
the uploaded file matches `release_jlcpcb/cpl.csv` at HEAD.

### H5. SW_RST and SW_BOOT are floating in the schematic

**Gate:** `verify_schematic_pin_connectivity.py` — FAIL, 4 floating pins
in `02-mcu.kicad_sch` (339 pins checked repo-wide, 1 documented N.C.)

```
SW_RST   pin 1 @ (144.68, 164.98)
SW_RST   pin 2 @ (154.84, 164.98)
SW_BOOT  pin 1 @ (114.68, 201.98)
SW_BOOT  pin 2 @ (124.84, 201.98)
```

`scripts/generate_schematics/sheets/mcu.py` wires `SW_Push` vertically at
`y ± 3.81` while the symbol's pins are horizontal at `x ± 5.08`, so the
wires land next to the pins instead of on them.

**The PCB is unaffected and the buttons work on the board** — this is a
drawing defect, but a floating pin means the component is absent from the
schematic netlist, which is what feeds every schematic-side cross-check.

KiCad's own ERC sees these only as *warnings* ("Pin not connected"), which
is why they survived until a dedicated gate was written.

### H6. The LED2 CPL override may itself be the bug

**No gate can settle this.** `verify_cpl_rotation_law` reports LED2 `OK`
with residual 0.0°, identical to LED1 — which is easy to misread as a
resolution. It is not.

Two independent geometric extractors (F.SilkS mirror-asymmetry, and an
off-centre colour patch in the manufacturer `.wrl`) agree that
**C19171391's pad numbering is inverted** relative to its physical cathode
mark, while C84256 (LED1) is aligned:

```
C84256    (LED1)  pad1=180.0  silk=176.8  mesh=180.3  delta=  0.3  aligned
C19171391 (LED2)  pad1=  0.0  silk=178.3  mesh=142.7  delta=142.7  OPPOSITE
```

Both readings of the evidence agree the numbering is inverted; they differ
only on **which frame the pick-and-place follows**. The law derives its
reference from the EasyEDA pad 1 → pad 2 bearing, i.e. it assumes the
machine aligns by pad *numbers* — that is one of the two competing
readings, so the gate cannot arbitrate between them. If the machine
instead orients by the 3D model, then `_JLCPCB_ROT_OVERRIDES["LED2"] = 180`
rotates a correct placement into a reversed one.

**Deciding test, 30 seconds, the board is on the desk:** proto #1 was
assembled from the PRE-fix CPL (LED2 at 0°). Look at LED2 under
magnification and compare its cathode mark against which pad goes to GND.
Do **not** use "does it light up" — LED2 is the IP5306 *fully-charged*
indicator, so a dark LED is confounded by battery state.

This matters beyond LED2: **the same reasoning pattern signs off Q1, U2
and U3.** If it is wrong here it is suspect there too.

Work in progress on branch `worktree-pin1-analytic-rotation` (`faf61d7`),
tool `scripts/analyze_pin1_marker.py`.

---

## RESPIN — as-built limitations of the fabricated board, not fixable in place

Real, confirmed, and deliberately not being fixed on the board that exists.
Listed so nobody re-discovers them as bugs.

**On the numbering.** This section used to be called "V2 — limitations of the
v1 board", which collided with the release tags: those run `v2.3 … v4.3.1`,
so "v2" meant the *final product phase* in CLAUDE.md and a *release from
7 April* in `git tag`. Two scales, one name. Here and below:

- **the fabricated board** = the design at the latest release tag,
  currently **`v4.3.1`** (2026-04-16) — this is what prototype #1 is
- **the respin** = the next fabrication, whenever it is cut; that is where
  everything in this section gets fixed

Note `release_jlcpcb/README.md` still heads its history with "v3.2 (current)"
and is six releases stale; the tag is the truth.

- **SW_PWR is not in series with the battery.** Only the common pin
  (pad 2) is routed, as a stub tap on BAT+ at (39.25, 70.3); throw pins
  1/3 have no net. The path J3 → Q1 → BAT+ → IP5306 pin 6 is continuous
  copper that never passes through the switch, so **the switch cannot
  power the board down**. True isolation on the fabricated board = unplug J3. Respin: route the
  battery through switch pins 1–2.
- **VBUS is fragmented into 3 components** (J1.9 / J1.11 isolated) — a
  documented, functional single-orientation workaround, allowlisted in
  `verify_net_connectivity.ACCEPTED_FRAGMENTATIONS`. Tracked as R5-CRIT-9
  for the respin. **Keep the allowlist entry.**
- **EN has no RC delay network, and no pull-up at all.** The module
  datasheet is not ambiguous about this. Page 28, under the peripheral
  reference schematic: *"To ensure the ESP32-S3 chip's supply is correct
  at power-up, an RC delay circuit **must** be added at the EN pin.
  R = 10 kΩ and C = 1 µF are the usual recommendation, but the values
  should be adjusted to the module's power-up timing and the chip's
  power-on reset timing."* Its figure 7 draws R7 from VDD33 to EN and C8
  (0.1 µF) from EN to GND, with the reset button across the cap.

  The fabricated board has **neither**: R3 is DNP and C3 is wired as a second
  decoupling cap, so EN reaches only `U1.3` and `SW_RST` pad 1. It boots
  today, so this is a margin defect, not a dead board — the failure mode
  is slow supply ramps and brown-outs, i.e. a fraction of units in the
  field rather than anything reproducible on the bench.

  How it survived: `mcu.py` carried the comment *"the module integrates a
  10k EN pull-up on-module (per Espressif reference design), so an
  external pull-up is redundant"*, which is false, and
  `hardware-audit-bugs.md` asserts "EN RC delay (R3+C3) intact" in two
  places without anyone comparing that sentence to copper. Same class as
  the R25 finding that a justification comment can outrank the datasheet.

  Not patched on the fabricated board: the only cap available is 28 mm away, and dragging a
  net that far would trade a missing RC for a long high-impedance antenna
  on the reset line — worse than leaving it bare. **Respin: 10 kΩ from +3V3
  to EN and 100 nF from EN to GND, both placed adjacent to module pin 3.**
  The schematic now draws C3 where the board actually has it, so `T4`
  stays honest instead of describing a network that does not exist.
- **`SW_PWR` carries the legacy footprint key `SS-12D00G3`** everywhere in
  routing/CPL; the actual part is MSK12C02 (C431540). The schematic value
  must stay `SS-12D00G3` or `verify_schematic_pcb_sync.py` fails. Renaming
  the key across routing/footprints/CPL is a respin cleanup.

---

## C — Cleanups with a known fix and a known reason they are still open

- **Phantom nets `LCD_BL` and `LCD_RD`** are declared in
  `primitives.NET_LIST` with zero pads (WARN in `verify_netlist_diff` T5).
  Removing them is two lines, but a PCB regeneration drops every
  `filled_polygon` — measured at 7695 diff lines — so it needs a zone
  re-fill and a `release_jlcpcb/` sync. Attempted and deliberately
  reverted: disproportionate blast radius. **Bundle with H1 or H3**, which
  regenerate the board anyway. IDs 18/19 can be left as gaps.
- **`collision.py` is default-open on pad nets.** `_KNOWN_PAD_NETS`
  (`collision.py:215`) has 4 hardcoded entries; every other pad is
  registered with `net=0`, and net=0 pads are *skipped* in collision
  queries (`collision.py:125`). A pad only acquires a net when the first
  trace touches it (`collision.py:466`), so a pad the router never targets
  is invisible to collision detection forever and a trace can be routed
  straight over it. Contained today only by post-hoc gates
  (`verify_trace_through_pad`, `short_circuit_analysis`,
  `analyze_pad_distances`) — all currently green. This class has bitten
  before. **Fix:** seed pad nets from `routing._PAD_NETS` before routing
  begins, so the router is default-closed.
- **`verify_bom_values.KNOWN_MAPPINGS`** maps `"fpc-16p-0.5mm" → 40-pin`,
  papering over a real schematic/BOM inconsistency. Fix the schematic
  symbol value instead.
- **`verify_easyeda_footprint._GEOMETRIC_MISMATCH_ALLOWLIST`** still holds
  U2 (90°) and LED2 (180°). Both are tied to H4/H6 — resolve together.
- **`verify_netlist_diff.EXCLUDED_REFS` contains `R14`**, documented as
  DNP but **never independently verified**. Confirm R14 is genuinely
  do-not-populate before trusting the exclusion.
- **`verify_copper_clearance`** still reports `loc = (0,0,0,0)` on the
  `nearest_points` fallback path. It does not suppress the violation, only
  misreports where it is.

---

## Do NOT "fix" these

Each of these looks like a bug, has been investigated, and is correct as
it stands. Changing them breaks a working board.

- **J4 FPC `41 − N` pin reversal** — panel-side vs connector-side pinout.
  Both files are correct: `connector_pad = 41 − panel_pin`. Distinct from
  H4's rotation question about the same connector.
- **USB Zdiff of 130 Ω** — a non-issue. Do not move parts or traces for it.
- **`POWER_HIGH_ALLOWLIST` BAT+ entries** — coordinate-pinned to 0.02 mm
  with an IPC-2221 argument; they cannot drift silently. Keep.
- **`verify_net_connectivity.ACCEPTED_FRAGMENTATIONS["VBUS"]`** — see RESPIN
  above. Keep.
- **`verify_stackup.IN2_ALLOWED_NETS` includes VBUS**, which pours 0 mm².
  Harmless and unused.

---

## How to keep this file honest

Every entry above names a gate or a deciding physical test. When you close
one:

1. Make the **gate** go green — not the edit look right.
2. Delete the entry here in the same commit.
3. If the fix touched PCB, gerbers, BOM or CPL, sync `release_jlcpcb/` in
   that same commit (`git diff --stat` before committing), and re-upload
   the CPL if it changed.

If this file and `make open-issues` ever disagree, the command is right.
