# Known issues — what is still broken

Everything in this file is **open**: it fails a gate, or it is an
unverified claim about a board that has already been fabricated. Nothing
here is a plan, a nice-to-have, or a closed finding. Closed work lives in
`docs/waiver-audit-recovery.md` (Part 1) and `hardware-audit-bugs.md`.

**This file is a snapshot, the gates are the truth.** Measured on
`2a7a469`, 2026-07-26, macOS + local `kicad-cli`. Before acting on any
entry, re-derive the current state:

```bash
make open-issues     # the 6 gates that guard known-open work (~10 s)
make verify-all      # the exhaustive suite, 66 checks (~20 s)
```

At the snapshot commit: `verify-all` is **61/66**, `open-issues` is
**5 of 6 gates red**. Every entry below names the gate that proves it, so
a fixed entry goes green on its own rather than needing this file edited
to stay honest. If an entry's gate is green and the text still says open,
**the gate wins** — delete the entry.

Every remaining entry is a real defect. The two gates that used to fail
for their own reasons — a stale machine-global ERC report, and a rotation
law whose verdict moved as an untracked cache warmed — were fixed in
`2a7a469`, so red now means the board, never the tooling.

Reading order is by consequence, not by section: **H2 and H4 are the two
that can put a wrong board or a wrong part on the desk.**

---

## H — Hardware: the design or the board is wrong

### H1. Three copper stubs end in the air

**Gate:** `verify_dangling_copper.py` — FAIL
**Introduced:** pre-R24, first visible when the gate was written (no
earlier gate could see this class).

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

### H2. Schematic and PCB disagree on 7 pin↔net assignments

**Gate:** `verify_netlist_diff.py` [T4] — FAIL, 7 mismatches

```
J3.1    sch='GND'       pcb='BAT_IN'
Q1.2    sch='GND'       pcb='BAT_IN'
U1.3    sch='+3V3'      pcb='EN'
LED1.1  sch='LED1_RA'   pcb='GND'
LED1.2  sch='GND'       pcb='LED1_RA'
LED2.1  sch='LED2_RA'   pcb='GND'
LED2.2  sch='GND'       pcb='LED2_RA'
```

Three distinct problems, not one:

- **J3.1 / Q1.2 — the battery path.** J3 is the battery connector and Q1
  is the reverse-polarity FET. The schematic says these pins are GND; the
  board says they are `BAT_IN`. This is not a pin-number cosmetic flip —
  the two files disagree about which side of the protection FET is
  battery and which is ground. Resolve against
  `hardware/datasheets/POLARITY_AUDIT.md`, which is the source of truth
  for polarity; do **not** re-derive it.
- **U1.3 — `+3V3` vs `EN`.** One of the two files has the regulator
  enable pin tied to the rail it is supposed to gate.
- **LED1 / LED2 — pads 1 and 2 swapped on both.** Same shape on both
  parts, and it is the *same fact* the LED2 rotation question turns on
  (see H6). Fixing the schematic pin numbering and flipping the CPL
  override are two ways to produce a reversed LED; do not do both, and do
  not do either before H6's visual check.

Note the R20/R21 PAM8403 bias mismatch documented in
`docs/waiver-audit-recovery.md` §O3 is **closed** upstream (`ee0ec02`) —
that document is stale on this point, this list is current.

### H3. Four VBUS segments are below their net-class minimum

**Gate:** `verify_net_class_widths.py` — FAIL, "Power High traces >= 0.50mm"

Four B.Cu segments at **0.273 mm** against the 0.50 mm Power High
minimum, all at the J1 (USB-C) fan-out:

```
(77.6, 68.8)   (82.4, 68.8)   (77.5, 69.0)   (81.8, 70.2)
```

VBUS carries USB charging current, so this is a current-density question,
not a style question. `POWER_HIGH_ALLOWLIST` covers only the BAT+
corridor and does not reach these.

**Fix — two honest options, no third:** widen the segments, or add
coordinate-pinned allowlist entries with an IPC-2221 calculation, written
the way the BAT+ entries are written. The calculation has to be *done*.

### H4. The CPL rotation law disagrees with three placements

**Gate:** `verify_cpl_rotation_law.py` — FAIL
**Result:** OK 10 · FAIL 3 · UNEVALUABLE 1 · NOREF 0 · total 14
(reproducible since `2a7a469` tracked the reference footprints; a missing
reference now reports NOREF and exits 2 instead of counting as a violation)

| ref | LCSC | package | layer | law wants | CPL emits | gap |
|---|---|---|---|---|---|---|
| U2 | C181692 | ESOP-8 | bottom | 90° | 0° | 90° |
| U4 | C7519 | SOT-23-6 | bottom | 0° | 90° | 90° |
| J4 | C2856812 | FPC-40P | bottom | 90° | 270° | 180° |
| J1 | C2765186 | USB-C | bottom | — | 0° | UNEVALUABLE |

**Highest-stakes item in this file.** Each row is a claim about the
physical orientation of a part on a board that has been fabricated.

- **U2** — evidence runs *against* the law. Boards R4–R8 charge over
  USB-C and boost to 5 V through the IP5306, and an ESOP-8 rotated 90°
  could not seat on its pads at all. Probably a law false positive.
- **U4 — the credible bug.** `^SOT-23` in `_JLCPCB_ROT_CORRECTIONS`
  applies −90° to both SOT-23-3 and SOT-23-6, but EasyEDA draws the two
  families in frames 90° apart (`jlcpcb_export.py` says so in its own
  comment). Q1, a SOT-23-3, satisfies the law; U4 does not. **If the law
  is right the fix is to split the regex, not to add a per-part delta.**
- **J4** — a 180° delta with no geometric derivation behind it, only the
  note "JLCPCB 3D: 90° puts pins on wrong side". Same shape as the D1 bug
  that turned out to be 180° out. This is a *different axis* from the
  documented `connector_pad = 41 − panel_pin` netlist reversal — do not
  conflate them (see "Do not fix" below).
- **J1** — `_row_bearing()` returns `None` because the USB-C footprint
  has duplicate/unnumbered shield pads, so this connector sits permanently
  outside the law. Needs pad-pair selection that skips shield tabs.

`_LAW_EXCEPTIONS` in the gate is an **empty dict**, so what is known about
these parts — and it is written down, in `jlcpcb_export.py` comments —
cannot reach the gate. Deciding test for each: the JLCPCB 3D preview for
that LCSC part, then either fix the footprint or record a
`_LAW_EXCEPTIONS` entry that states the physical claim and names the
residual, so drift re-fails.

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

## V2 — as-built limitations of the v1 board, not fixable in place

Real, confirmed, and deliberately not being fixed on v1. Listed so nobody
re-discovers them as bugs.

- **SW_PWR is not in series with the battery.** Only the common pin
  (pad 2) is routed, as a stub tap on BAT+ at (39.25, 70.3); throw pins
  1/3 have no net. The path J3 → Q1 → BAT+ → IP5306 pin 6 is continuous
  copper that never passes through the switch, so **the switch cannot
  power the board down**. True isolation on v1 = unplug J3. v2: route the
  battery through switch pins 1–2.
- **VBUS is fragmented into 3 components** (J1.9 / J1.11 isolated) — a
  documented, functional single-orientation workaround, allowlisted in
  `verify_net_connectivity.ACCEPTED_FRAGMENTATIONS`. Tracked as R5-CRIT-9
  for the v2 respin. **Keep the allowlist entry.**
- **`SW_PWR` carries the legacy footprint key `SS-12D00G3`** everywhere in
  routing/CPL; the actual part is MSK12C02 (C431540). The schematic value
  must stay `SS-12D00G3` or `verify_schematic_pcb_sync.py` fails. Renaming
  the key across routing/footprints/CPL is a v2 cleanup.

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
- **`verify_net_connectivity.ACCEPTED_FRAGMENTATIONS["VBUS"]`** — see V2
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
