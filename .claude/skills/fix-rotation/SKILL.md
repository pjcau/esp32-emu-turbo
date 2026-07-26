---
name: fix-rotation
model: claude-opus-5
description: Investigate and fix a JLCPCB CPL rotation by pin→pad→net geometry, against the one-law-per-layer gate
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
argument-hint: <REF> (e.g. U5)
---

# Component Rotation Investigation

Settle the JLCPCB CPL rotation for one component.

**Argument**: Component reference designator (e.g. `U5`).

## Read this before you start

Rotation is the single area of this project with the worst track record, and
every past failure came from the same two habits. Do not repeat them:

1. **Do not add a per-part delta.** Rotation is governed by **one law per
   layer** (`scripts/verify_cpl_rotation_law.py`), not a table:

   ```
   top     R = cpl - (row_board - row_ee)   == 0°
   bottom  R = cpl + row_board + row_ee     == 180°
   ```

   `row_*` is the bearing of the pad-1 → pad-2 vector, so exposed pads,
   shield tabs and mounting pads cannot skew it. The old
   `_JLCPCB_ROT_DELTAS` table is dead: it was a hand-tuned sign-off
   registry, and *a gate shaped like a sign-off cannot catch a wrong
   sign-off*. If two parts want the same correction, that is one **family
   constant** in `_JLCPCB_ROT_CORRECTIONS`, not two deltas.

2. **Never make a verification assert the generator's own output.**
   `verify_dfm_v2` once contained `j4_rot == 270` — a tautology that
   restated what the generator emitted, so when the number was wrong the
   assertion defended the bug. Derive the expected angle from the law.

**"The boards work" is not evidence.** U2 shipped at an angle where 0 of 8
leads touch copper and those boards charge anyway, because JLCPCB corrected
it at assembly (confirmed by eye on protos #1 and #2). The old
`POLARITY_AUDIT.md` claim "boards R4–R8 power up through Q1, so its polarity
is proven" is **retired repo-wide** — it described what the assembler did,
not what our file said.

## The convention-free method

Every KiCad-orientation-to-CPL convention is disputable, so do not rely on
one. Instead ask a question that has a physical answer:

> Place the part at each candidate angle. Which board pad does each **pin**
> land on, and what **net** is that pad on?

Only one rotation puts every pin on its own pad with the right net.

### 1. Gather component data

- **BOM**: `release_jlcpcb/bom.csv` — LCSC part number, footprint
- **CPL**: `release_jlcpcb/cpl.csv` — current position, rotation, layer
- **EasyEDA reference**: `scripts/.easyeda_cache/` (tracked in git — judge
  against the reviewed geometry; **do not re-fetch on a miss**)
- **Board placement**: `scripts/generate_pcb/board.py`
- **Footprint**: `scripts/generate_pcb/footprints.py`

### 2. Let KiCad do the transforms

Load the LCSC reference into `pcbnew`, flip it to B.Cu if the part is on the
bottom, and read the pad positions back. This makes KiCad perform the Y-down
rotation and the bottom mirror, rather than hand-rolled matrices — which is
what made the earlier derivations disagree with each other.

Pad transform order elsewhere in the codebase is
`rotate → mirror_X → translate` (`get_pads` and `routing._compute_pads`).

### 3. Score all four angles by pin → pad → net

For each of 0/90/180/270, report **per pin**: the pad it lands on, the
residual distance, and that pad's net. A correct angle looks like U2's:

```
cpl=270  every pin on its own pad, 0.090 mm uniform, nets all correct:
         VIN->VBUS, KEY->IP5306_KEY, BAT->BAT+, SW->LX, VOUT->+5V, EP->GND
```

Watch for the **solderable-but-wrong** case — the dangerous one. U2 at 90
solders cleanly with pin *i* on pad *i+4*, putting BAT+ (an unfused 4.2 V
cell) onto the LED1 open-drain indicator sink. A part that does not seat at
all is a safer failure than one that seats wrong.

Symmetric packages need an extra argument, because both angles solder:

- **J4 (FPC-40P)**: a 180° turn maps a 40-contact row onto itself; the two
  differ by contact *i* landing on pad *i* vs pad *41−i*. Settle it by
  **which way the contacts face**: they must face the FPC slot
  (`board.py` puts it at x 125.5–128.5, J4's body at 133.5–136.5).
- **Tact switches**: pads 1+2 are one pole and 3+4 the other, and the symbol
  has one pin per pole (`_TACT_MAP`). Pad 2 belongs to the pole that is
  symbol **pin 1** — reading "routing drives BTN_SELECT onto pad 2" and
  reaching for pin 2 is how SW_BOOT ended up 90° out.

### 4. Check the law's blind cell first

The law is wrong **whenever `(row_board + row_ee) mod 180 != 0`**. That is
the entire defect, stated exactly. All four current exceptions live there:

| Ref | Part | Sum | CPL |
|-----|------|-----|-----|
| U2 | IP5306 ESOP-8 (C181692) | 90 | 270 |
| J4 | FPC-40P (C2856812) | 90 | 270 |
| Q1 | SI2301CDS SOT-23-3 (C10487) | 90 | 270 |
| D1 | BAT54C SOT-23-3 (C37704) | 270 | 90 |

Every other part sums to 0 or 180, where the bottom form coincides with the
geometry — which is why no passing sibling ever exposed this. **If the
exception list grows, check the sum before believing it is a new part
quirk.**

### 5. Apply the fix at the right level

Decide which of the three you actually have:

- **A family constant** → `_JLCPCB_ROT_CORRECTIONS` in
  `scripts/generate_pcb/jlcpcb_export.py`. Regex order matters (first match
  wins), and anchors are literal: `^SOP-` does **not** match `ESOP-8` — that
  one-letter miss is what emitted U2 at cpl=0, the same class as U4's
  SOT-23-6 falling onto the SOT-23-3 rule. Current entries include
  `^ESOP-` +90, `^SOT-23` +90 (D1, Q1 — was −90, a full 180 out),
  `^SOP-(?!18_|4_)` / `^SOIC-` / `^TSSOP-` +270.
- **A genuine taping quirk** → `_LAW_EXCEPTIONS` in
  `verify_cpl_rotation_law.py`. Each entry must state a claim about the
  **physical part** and pin the residual it produces, so any drift in the
  copper or the placement fails it as stale. "It seemed to work" is not a
  reason.
- **A placement error** → fix `board.py`, not the CPL.

Regenerate: `make generate-pcb`

### 6. Prove the gate still discriminates

```bash
make verify-cpl-law     # 10 OK, 4 EXCEPTION, 0 FAIL
make test-cpl-law       # mutation tests: plant errors, require every catch
make verify-all
```

An assertion that never fires is not evidence. `test_cpl_rotation_law.py`
plants rotation errors on purpose and requires the gate to catch each one.

For the physical polarity marker (silk asymmetry + 3D mesh, two independent
extractors): `make analyze-pin1`.

### 7. Ship it

**A design-side fix is not done until the CPL is re-uploaded.** Verify the
uploaded file matches `release_jlcpcb/cpl.csv` at HEAD — that directory was
found stale once already, carrying U4=90° for months after the generator had
been fixed to emit 0°. Gates compare the generator to the board, never the
release directory to the generator.

## Key Files

- `scripts/generate_pcb/jlcpcb_export.py` — `_JLCPCB_ROT_CORRECTIONS`,
  `_JLCPCB_ROT_OVERRIDES`, `_JLCPCB_POS_CORRECTIONS`
- `scripts/verify_cpl_rotation_law.py` — the law, `_LAW_EXCEPTIONS`
- `scripts/test_cpl_rotation_law.py` — mutation tests
- `scripts/analyze_pin1_marker.py` — physical pin-1 marker extraction
- `scripts/generate_pcb/footprints.py` — `get_pads()`,
  `_pre_rotate_element()`, `_mirror_pad_x()`
- `hardware/datasheets/POLARITY_AUDIT.md` — polarity source of truth; read
  its correction block, not just the original chain
- `docs/known-issues.md` — H4 (how the law landed), H6 (LED2, still open)

## Still open

**H6 — the LED2 override may itself be the bug.** No gate can settle it:
`verify_cpl_rotation_law` reports LED2 OK with residual 0.0°, which is easy
to misread as a resolution. Two extractors agree C19171391's pad numbering
is inverted relative to its cathode mark; they differ on whether the machine
aligns by pad numbers or by the 3D model. **The same reasoning pattern signs
off Q1, U2 and U3 — and it has already failed once, on U2.** The deciding
test is visual, on proto #1, and takes 30 seconds.
