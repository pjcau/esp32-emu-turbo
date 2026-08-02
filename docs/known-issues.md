# Known issues — what is still broken

Everything in this file is **open**: it fails a gate, or it is an
unverified claim about a board that has already been fabricated. Nothing
here is a plan, a nice-to-have, or a closed finding. Closed work lives in
`docs/archived/waiver-audit-recovery.md` (Part 1) and `hardware-audit-bugs.md`.

**This file is a snapshot, the gates are the truth.** Measured on
`35d6454`, 2026-07-26, macOS + local `kicad-cli`. Before acting on any
entry, re-derive the current state:

```bash
make open-issues     # the gates that guard known-open work (~10 s)
make verify-all      # the exhaustive suite (~20 s)
```

**No suite size is written here, on purpose.** This block said "6 gates" and
"68 checks / 68/68" while the suite had already grown — to 70, then 73, and
`open-issues` to 7 — because those counts are maintained by hand and the
suite is not. A number that can only drift is worse than no number: it invites
the reader to trust the sentence instead of running the command, which is the
exact failure this file exists to prevent. Both commands print their own
totals. (Same rule as MEMORY.md, where `make verify-memory` rejects
hand-written gate state outright.)

Every entry below names the gate that proves it, so a fixed
entry goes green on its own rather than needing this file edited to stay
honest. If an entry's gate is green and the text still says open, **the
gate wins** — delete the entry.

No gate is red right now, and that is not the same as "nothing is open".
Four of the fourteen parts the rotation law judges now pass as declared
`EXCEPTION` rather than `OK`, because **the law is wrong for one of its
cells** (H4). The remaining entries are the RESPIN list, plus closed records kept
because each documents a way a gate can be fooled (H1–H6). A green suite means
no check currently disagrees with the design; it does not mean the design was
checked against the physical board.

Reading order is by consequence, not by section. **H4 was the entry that
could put a wrong part on the desk, and it is now resolved** — but read it
anyway: it is the clearest worked example in this repo of a gate being
confidently, narrowly wrong, and of the answer that was 180° from both the
gate's verdict and the shipped value being the destructive one. H6 — long the
only entry that depended on evidence no gate could produce — is now closed
by the two LED manufacturers' datasheets: the "inverted pad numbering" was
an artifact of assuming pin 1 = cathode universally, when the two vendors
simply number their pins oppositely.

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

**Fix:** delete the segments in `scripts/generate_pcb/routing/`, or
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
  also meant SW15 was drawn shorting the rail to ground on every press.
- **LED1 / LED2** — *not* rewired. A pin-vs-pad numbering translation in
  `SCH_PIN_TO_PCB_PADS` (`_LED_MAP`), with each side checked
  independently: on the PCB pad 2 carries `LED{n}_RA` through R17/R18 to
  +3V3 and pad 1 carries GND; in the schematic pin 1 (A) carries
  `LED{n}_RA` and pin 2 (K) carries GND. Same circuit, different numbers.
  A wrong entry there still fails T4, exactly as for J1/J4/U5/U6. **This
  does not answer H6** — the CPL override question is untouched.
- **C3** — the schematic was describing a circuit the board does not
  have; see the RESPIN section below.

Also added to the table while closing this: `SW15` and `SW14`, which
had never been in it because their schematic pins were floating, so no
pin of theirs ever reached the comparison. Adding them immediately caught
`SW14` drawn on the wrong pole.

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
`docs/archived/waiver-audit-recovery.md` §O3 is **closed** upstream (`ee0ec02`) —
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
move to open it. `routing/_shared.py` (POWER_HIGH_ALLOWLIST derivation) solves the width from the
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

### H4. The CPL rotation law was wrong for one of its own cells — RESOLVED

**Gate:** `verify_cpl_rotation_law.py` — PASS
**Result:** OK 12 · **EXCEPTION 2** · FAIL 0 · UNEVALUABLE 0 · NOREF 0 · total 14
**Closed:** `8b24728`, 2026-07-26.

| ref | LCSC | package | layer | was emitting | now emits | verdict |
|---|---|---|---|---|---|---|
| U2 | C181692 | ESOP-8 | bottom | 0° | **270°** | real bug, fixed |
| J4 | C2856812 | FPC-40P | bottom | 270° | **270°** | was already correct |
| U4 | C7519 | SOT-23-6 | bottom | 0° | 0° | closed `1765982` |
| J1 | C2765186 | USB-C | bottom | 0° | 0° | evaluable, OK |

**The law derived 90° for both parts and 90° was wrong for both.** U2 and
J4 are the only two members of the cell `(row_board=90, row_ee=0)`; every
other part on the board sits at `row_board + row_ee ∈ {0, 180}`, where the
law's bottom form coincides with the geometry. That is why twelve parts
agreed with it and no passing sibling ever exposed the cell. Both now carry
a `_LAW_EXCEPTIONS` entry pinning the residual at 0 — **one law defect
recorded twice, not two part quirks.**

**U2 was a real bug, and the interesting part is that it had three wrong
answers.** `"ESOP-8"` cannot match the `^SOP-` rule in
`_JLCPCB_ROT_CORRECTIONS` — the anchor is blocked by the leading E — so it
fell through to `_JLCPCB_ROT_DEFAULT` and shipped at 0°. The same
one-letter miss that put U4's SOT-23-6 on the SOT-23-3 rule.

| cpl | what actually happens |
|---|---|
| 0° (shipped) | lead row runs along Y, pads along X. **0 of 8 leads touch copper**, worst offset 5.012 mm. Held only by EP paste. |
| 90° (**the law's answer**) | **solders, and that is what makes it the worst option.** Pin *i* lands on pad *i+4*: BAT+, an unfused 4.2 V cell, onto LED1 — an open-drain indicator sink — while BAT and VOUT reach nothing. |
| 180° | as 0°: does not seat. |
| **270°** | every pin on its own pad, 0.090 mm uniform, every net right: VIN→VBUS, KEY→IP5306_KEY, BAT→BAT+, SW→LX, VOUT→+5V, EP→GND, LED1‑3 open. |

**J4's 270° was correct all along**, and it was briefly deleted during this
work on the theory that its justification was only an eyeballed 3D overlay
(`404f31a`). Deleting it emits 90°, which is wrong. Two checks that need no
angle convention at all:

1. **Cable side.** The contacts must face the FPC slot. `board.py` puts
   `FPC_SLOT` at x 125.5–128.5 with J4's body at 133.5–136.5, so the slot
   is on J4's −X side, and on the copper the signal pads sit at lower x
   than the mount tabs (`verify_dfm_v2` asserts exactly this). At 270° the
   contacts land at x=133.712 and the tabs at 136.288 — contacts toward the
   slot. At 90° the two swap and the ribbon would enter from off the right
   board edge.
2. **Seating.** Loading the LCSC reference into pcbnew, flipping to B.Cu
   and rotating — so KiCad does the Y-down rotation and the bottom mirror,
   not a hand-rolled matrix — the matching orientation has a worst residual
   of **0.002 mm across all 42 pads**; the 180°-away alternative contacts
   **0 of 42**.

**What the argument actually turned on.** Not the law's algebra, which is
sound in form: `cpl + row_board + row_ee` is invariant under the placement
rotation, while the obvious-looking alternative moves 180° every time you
rotate a part in the layout, so it cannot be a law. The disputed step was
the KiCad-orientation → CPL convention. `CPL_bottom = (180 − O)` is what
both `kicad-jlcpcb-tools` (`fabrication.py`) and KiBot
(`fil_rot_footprint`, `mirror_bottom`) implement, and it predicts J4's 270°
and U5's independently confirmed 180°. Nothing implements the `CPL = −O`
that 90° would require.

**Do not conflate any of this with `connector_pad = 41 − panel_pin`.** That
netlist mapping is correct, untouched, and a different axis — see "Do not
fix" below.

**Confirmed on hardware, 2026-07-26.** The deciding test this entry used to
ask for has now been done, on prototypes #1 and #2:

- **The IP5306 sits vertical on both boards.** The copper demands a vertical
  body — the two pad columns are 6 mm apart in X with the 1.27 mm pitch
  running along Y — so this rules out 0° and 180° outright, and confirms the
  shipped `cpl=0` is not what those boards were built with. JLCPCB corrected
  it at assembly. **That is why the boards charge despite the CPL, and it
  retires the "boards R4–R8 charge, therefore 0° is fine" argument for
  good.**
- **Pin 1 is at the top-left**, viewed from the bottom side with the USB-C
  on the lower edge. U2 is on B.Cu, so X mirrors in that view, and pad 1
  (VIN, on VBUS) is exactly the top-left position — pad 8 (VOUT) is
  top-right, pad 5 (KEY) bottom-right. So the physical pin 1 sits on pad 1:
  the identity mapping, which is `cpl=270`.

This is independent of the geometry and of the `CPL_bottom = (180 − O)`
convention, and it agrees with both. It also transfers to J4, whose 270°
comes from the same convention.

**D1 and Q1 were the same bug and are now closed too.** Both are SOT-23-3
and both hit the generic `^SOT-23` rule, whose −90 was 180° out; SOT-23-5
and SOT-23-6 match their own rules and were unaffected. Re-derived by the
same convention-free route, anchored on U2:

| ref | was | seats? | now | seats? | nets at the new angle |
|---|---|---|---|---|---|
| D1 | 270° | no — 3.120 mm on bare mask | **90°** | 0.187 mm | anodes → BTN_START / BTN_SELECT, cathode → MENU_K |
| Q1 | 90° | no — 2.933 mm on bare mask | **270°** | 0.000 mm | G/S/D → RPP_GATE / BAT_IN / BAT+ |

One family constant, not two per-part deltas. There is no
solderable-but-wrong option here as there was for U2: a 180° error on a
SOT-23-3 puts the single leg where the pair is, so it does not assemble.

`POLARITY_AUDIT.md` recorded Q1 as empirically validated "because boards
R4–R8 power up through it". **That argument is retired**, by U2: U2 shipped
at an angle where 0 of 8 leads touch copper and those same boards charge,
because the assembler corrected it. "The boards work" describes what JLCPCB
did, not what our file said.

So the law's blind cell has exactly four members, and now all four are
accounted for: **it is wrong whenever `(row_board + row_ee) mod 180 ≠ 0`** —
U2, J4 and Q1 at 90, D1 at 270. Every other part sums to 0 or 180. If that
exception list ever grows, check the sum before believing it is a new part
quirk.

**A design-side fix is not done until the CPL is re-uploaded** and the
uploaded file matches `release_jlcpcb/cpl.csv` at HEAD. That directory was
itself found stale during this work: at `74c196e` the generator emitted
U4=0° while `release_jlcpcb/cpl.csv` still carried the pre-fix 90°, so the
fix closed in `1765982` had never reached the files anyone orders from.

### H5. SW15 and SW14 are floating in the schematic — CLOSED

**Gate:** `verify_schematic_pin_connectivity.py` — **PASS**, 338 pins
checked, **0 floating**, 1 documented N.C. Closed by `397c854` (geometry)
and `916c01c` (the pole mapping); both switches are now in
`SCH_PIN_TO_PCB_PADS` and reach `verify_netlist_diff` T4.

This entry stayed written as open long after its gate went green, which is
the thing this file's own header forbids — kept, per the header's rule for
H1–H3, because the *mechanism* is still worth reading: it is the clearest
case in the repo of a defect that every gate was structurally unable to see.
The original text follows.

**Original finding:** FAIL, 4 floating pins in `02-mcu.kicad_sch`
(339 pins checked repo-wide, 1 documented N.C.)

```
SW15   pin 1 @ (144.68, 164.98)
SW15   pin 2 @ (154.84, 164.98)
SW14  pin 1 @ (114.68, 201.98)
SW14  pin 2 @ (124.84, 201.98)
```

`scripts/generate_schematics/sheets/mcu.py` wires `SW_Push` vertically at
`y ± 3.81` while the symbol's pins are horizontal at `x ± 5.08`, so the
wires land next to the pins instead of on them.

**The PCB is unaffected and the buttons work on the board** — this is a
drawing defect, but a floating pin means the component is absent from the
schematic netlist, which is what feeds every schematic-side cross-check.

KiCad's own ERC sees these only as *warnings* ("Pin not connected"), which
is why they survived until a dedicated gate was written.

**Postscript (R27).** That last sentence understated it. `erc_check.py` did
not merely down-rank the class — its verdict never read KiCad's `severity`
field at all, and suppressed `wire_dangling` (an *error*) wholesale as a
"generator artifact". Re-planting this exact defect on a copy of the
schematic proved it: detaching SW3's ground pin took `SW3.2` off the GND net
in the exported netlist, and `erc_check` printed PASS before and after. Fixed
in the same round — errors now fail unless individually waived, guarded by
`scripts/test_erc_severity.py`.

### H6. The LED2 CPL override may itself be the bug — CLOSED

**Closed 2026-07-26 by the manufacturer datasheets, not by a gate.** The
entry's premise — "C19171391's pad numbering is inverted relative to its
physical cathode mark" — turned out to be an artifact of an assumption
baked into the extractors: that **pin 1 = cathode for every LED**. That is
a per-manufacturer convention, not a law, and the two vendors here chose
opposite ones:

| part | vendor | datasheet says | cache geometry agrees |
|---|---|---|---|
| LED1 `C84256` | NationStar NCD0805R1 | mark = **cathode = pin 1** | pad 1 x=−1.10, silk feature mean x=−0.57 — same end |
| LED2 `C19171391` | YONGYUTAI YLED0805R | p.1 draws **pin 1 with a "+" (ANODE)**; green mark at pin 2 = cathode | pad 1 x=+1.05, silk feature mean x=−0.38 — opposite ends |

Both datasheets are now in `hardware/datasheets/` (`LED1_Red-LED-0805_C84256.pdf`,
`LED2_Red-LED-0805_C19171391.pdf`). Nothing is inverted: the mark sits at
the cathode on both parts, and the cathode is pin 1 on one and pin 2 on
the other. The extractors' `OPPOSITE` verdict for C19171391 was the
correct geometry read through the wrong universal assumption.

With that resolved, the override follows analytically:

- **Board requirement (copper, both LEDs identical):** pad 1 = `GND` →
  needs the cathode; pad 2 = `LED_RA` → R17/R18 → `+3V3` → needs the anode.
- **Identical placements** (rot 0, Top), opposite pin-1 conventions ⇒ the
  two CPL angles must differ by exactly 180°. Shipped CPL: LED1 = 0°,
  LED2 = 180°. The `"LED2": 180` delta **is** that difference.
- **The "machine aligns by the 3D model" alternative collapses:** within
  C19171391's own EasyEDA part, the model colour patch (142.7°) and the
  silk (178.3°) sit at the same pad-2/cathode end — the two frames agree
  about physical reality and only disagreed about labels. The pad-number
  frame itself is hardware-anchored by U2 (protos #1 and #2).

**What hardware can still add (optional cross-check, not blocking):**
proto #1 was assembled from the PRE-fix CPL (LED2 at 0°), so the
prediction is that its LED2 is reversed and stays dark. Note the old
advice here — "do not use 'does it light up', it is confounded by battery
state" — was itself wrong: **U2's LED pins (2–4) are NC on this board**,
so both LEDs are plain +3V3 power indicators and LED2 should be lit
whenever the board is powered. If proto #1's LED2 *is* lit, that means
JLCPCB hand-corrected the reversed part at assembly, exactly as they did
U2 — not that 0° was right.

**Collateral finding:** C19171391 is a **red** LED (YLED0805R, 615–630 nm),
not green. The BOM, CPL, schematic value, docs and even the datasheet
*filename* said green for months — the file `LED2_Green-LED-0805_C19171391.pdf`
was byte-identical to the red YLED0805R datasheet fetched from LCSC. All
renamed/corrected 2026-07-26. If a green fully-charged indicator is still
wanted, that is a respin decision: pick an actual green part AND route
U2 pins 2/4 to the LEDs, which are currently NC.

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

- **SW16 is not in series with the battery.** Only the common pin
  (pad 2) is routed, as a stub tap on BAT+ at (39.25, 70.3); throw pins
  1/3 have no net. The path J3 → Q1 → BAT+ → IP5306 pin 6 is continuous
  copper that never passes through the switch, so **the switch cannot
  power the board down**. True isolation on the fabricated board = unplug J3. Respin: route the
  battery through switch pins 1–2.
- **VBUS is fragmented into 3 components** (J1.9 / J1.11 isolated) — a
  documented, functional single-orientation workaround, allowlisted in
  `verify_net_connectivity.ACCEPTED_FRAGMENTATIONS`. Tracked as R5-CRIT-9
  for the respin. **Keep the allowlist entry.**
- **EN has no RC delay network, and no pull-up at all — on every board
  fabricated through `v4.3.1`. FIXED IN THE DESIGN 2026-07-31** (R25-CRIT-1):
  `R3` (10 kΩ, EN→+3V3) and `C31` (100 nF, EN→GND) now sit on the EN trace
  5–7 mm east of `U1` pin 3 (`routing/_shared.py::R3_POS/C31_POS`), and
  `verify_strapping_pins` passes on the copper arm — it reads both parts
  off the pad nets, not off this record. The next fabrication gets them;
  nothing is reworkable on the assembled protos, where the failure mode
  remains slow supply ramps and brown-outs (margin defect, not dead board).

  The module datasheet is not ambiguous about this. Page 28, under the
  peripheral reference schematic: *"To ensure the ESP32-S3 chip's supply is
  correct at power-up, an RC delay circuit **must** be added at the EN pin.
  R = 10 kΩ and C = 1 µF are the usual recommendation, but the values
  should be adjusted to the module's power-up timing and the chip's
  power-on reset timing."* Its figure 7 draws R7 from VDD33 to EN and C8
  (0.1 µF) from EN to GND, with the reset button across the cap.

  On the fabricated boards R3 is absent and C3 is wired as a second
  decoupling cap, so EN reaches only `U1.3` and `SW15` pad 1. How it
  survived 25 audit rounds: `mcu.py` carried the comment *"the module
  integrates a 10k EN pull-up on-module (per Espressif reference design),
  so an external pull-up is redundant"*, which is false, and
  `hardware-audit-bugs.md` asserted "EN RC delay (R3+C3) intact" in two
  places without anyone comparing that sentence to copper. Same class as
  the R25 finding that a justification comment can outrank the datasheet.
  It was also deliberately not patched onto the assembled protos: the only
  cap available was 28 mm away, and dragging a net that far would trade a
  missing RC for a long high-impedance antenna on the reset line.

  **This sentence stays load-bearing even with the parts fitted:
  `verify_strapping_pins` greps this file for "EN has no RC delay network"
  whenever the copper LOSES the RC** — so if R3/C31 are ever deleted from
  the generators without this record, the gate goes red (and
  `scripts/test_strapping_en_rc.py::test_the_doc_anchor_still_exists_in_the_real_file`
  pins the anchor itself). Until `93bf286` that gate regex-matched a
  *justification comment* in the schematic (`"R3 DNP"`, `"WROOM-1
  integrates"`) and computed τ from a WROOM-1 internal ~45 kΩ pull-up the
  module does not have — the one gate whose job was to check EN was
  asserting the network's presence *from the prose that excused its
  absence*. It now reads copper: a pull-up is a resistor bridging
  `EN`→`+3V3`, the RC cap a capacitor bridging `EN`→`GND`. **Never "fix" a
  red result by restoring a comment or an allowlist** — fit the parts or
  keep the record honest.

  `scripts/test_strapping_en_rc.py` drives every arm (9 mutation tests):
  a planted 10 k + 100 nF passes on the parts with the record *absent*;
  either half alone fails; an unrecorded missing RC fails; the doc anchor
  is asserted to still exist in this file; and re-planting the old
  justification comment must change nothing.
- **The ESP32-S3 has no bulk capacitor within reach of its supply pin.**
  C28 (10 µF) was designed 3.7 mm from U1 pin 2 for exactly this job, but its
  land sits **under the module body**, so it was removed from assembly
  (`scripts/generate_pcb/jlcpcb_export.py` — "C28 REMOVED from assembly: was
  at (86,26) UNDER ESP32 module body"). It is not in the BOM, not in the CPL,
  and not on any assembled board. The nearest bulk on the +3V3 net is C30
  (22 µF), the buck's own output capacitor, ~45 mm away — outside any useful
  decoupling radius. What the module's supply pin actually has within 15 mm is
  C26's 100 nF.

  `verify_decoupling_adequacy` reported this requirement as satisfied for
  months because its capacitor table was hand-written and still listed C28 —
  a budget computed from a part that is not fitted, the same shape as the R3
  story. The gate now derives the fitted set from the CPL (via
  `verify_bom_cpl_pcb.DNP_REFS`) and passes only while this entry records the
  deviation. Respin: **relocate** C28 beside the module — fitting it where it
  is remains impossible.
- **Panel pin 13 (SPI SDI) floats on every board fabricated before
  2026-07-26** (R28-HIGH-1 — found by R28, FIXED in the design by R29's
  follow-up). The panel's pin table: *"If not used, please fix this pin at
  VDDI or DGND level"* — it is an input, unlike pin 14 (SDO) which the same
  table says to leave open. The design now ties J4 pad 28 to pad 29's +3V3
  with one same-net stub (`routing/display.py`, the pin-38→39 pattern);
  `datasheet_specs.py::J4.28` carries the datasheet sentence, and the
  vbench keeps the old float as a `detach_pin` mutation entry so the bench
  must still rediscover it. On the fabricated boards this is margin/EMI
  exposure on an unused CMOS input — the protos drive the panel fine — not
  a dead display. Nothing to rework in place; the next fabrication gets it.
- **The display backlight has no current-limiting element at all — on every
  board fabricated through `v4.3.1`. FIXED IN THE DESIGN 2026-07-31**
  (R25-HIGH-1, raised 2026-07-26): `J4` pad 8 (panel pin 33, LED-A) now
  carries the dedicated `LED_BLA` net, fed from **+5V through `R27`
  (20 Ω 1206, C17955)** — the resistor the analysis below sizes from the
  family class rating. `verify_datasheet_nets` now checks pad 8 against
  `_exact("LED_BLA")`, so a regression to the hard tie goes red. What is
  still owed: **one bench measurement on the actual panel** (see below) to
  confirm 20 Ω; the fabricated protos keep the old hard `+3V3` tie —
  cathodes (panel 34–36 → pads 7/6/5) on `GND`, no resistor, no driver,
  no PWM — and cannot be reworked in place.

  Everything below is the analysis that produced the fix, kept because the
  numbers are the record:

  **Citation corrected (R29).** This entry used to say `components.md`,
  "quoting the panel", specified "+3V3 *via resistor*". R29 read the panel's
  own pin table (`website/static/img/ili9488-fpc40-pinout.png`, surfaced by
  R28): pin 33 says only *"Anode of Backlight (2.9V–3.3V Typical: 3.1V)"* —
  **no resistor mention, no current rating**. The "via resistor" was our
  design note wearing quote marks — the same invented-citation class as
  R25's justification comments. The finding itself is unchanged and rests
  on physics, not on any quote: parallel white LEDs across a 3.327 V rail
  with 0.13–0.23 V of headroom have no defined operating point.

  **Why this is worse than a missing part.** The panel is 8 chip white LEDs at
  Vf 2.9–3.3 V, typ 3.1 V. Eight in series would need ~24.8 V, so they are
  parallel strings, and the whole array sits across the rail. `+3V3` measures
  **3.327 V** (vbench Phase 1), so at typical Vf the headroom is
  `3.327 − 3.1 = 0.227 V`, dropped across nothing but the LEDs' own dynamic
  resistance. Over the datasheet's own Vf spread that operating point is not
  defined at all: a 2.9 V part sees 0.427 V of overdrive, a 3.3 V part sees
  0.027 V and barely lights. White-LED Vf also falls roughly −2 mV/°C, so
  current *rises* as the panel warms — the wrong sign for stability.

  **A series resistor on +3V3 is the documented fix but a poor one.** With
  0.227 V of headroom, `R = 0.227 / I_BL` — about 3.8 Ω at 60 mA or 1.9 Ω at
  120 mA, which is why `routing.py` guesses "1–10 Ω". A resistor that drops
  0.2 V cannot regulate against a ±0.4 V Vf spread; it mostly limits the
  worst case rather than setting a current.

  **Respin: drive LED-A from `+5V`, not `+3V3`.** `5.0 − 3.1 = 1.9 V` of
  headroom makes the resistor dominant and the current actually defined
  (~32 Ω at 60 mA), or fit a constant-current LED driver. Either is a routing
  change at `J4` pad 8 plus one part in BOM/CPL.

  **Evidence found 2026-07-26 — the family rating, not yet the exact panel.**
  The exact 3.95" 40-pin bare panel is a generic AliExpress product
  (item `1005009422879126`) with no published spec, but a same-family
  panel — Focus LCDs `E35RG73248LW6M250-R`: ILI9488, 320×480, white-LED
  backlight, common anode + per-string cathodes — publishes the class
  rating, and its datasheet is now in the repo
  (`hardware/datasheets/DISPLAY-FAMILY_E35RG73248LW6M250-R_FocusLCDs.pdf`,
  outline drawing note 7):

  > **BACK LIGHT: LED WHITE, 6 LED, 90mA, 3.2V±0.3V**

  i.e. 6 parallel strings at 15 mA each, and — the number that matters —
  **backlight Vf = 3.2 V ± 0.3 V**. Against our measured 3.327 V rail that
  is 0.127 V of typical headroom, and a Vf-max (3.5 V) string never reaches
  rated current at all. This *sharpens* the analysis above: the family
  datasheet puts typical Vf 0.1 V higher than `components.md`'s 3.1 V.

  **Sizing from the family numbers, once LED-A moves to +5 V:**
  `R = (5.0 − 3.2) / 0.090 ≈ 20 Ω` for the 6-LED/90 mA class
  (P = 0.16 W → 1206 or two 0805 in parallel); an 8-LED variant at
  15 mA/string is 120 mA → ≈ 15 Ω, 0.22 W. **Final value still needs one
  bench measurement on the actual panel** (drive LED-A from a bench supply
  at 3.2 V, read the current) — that one number replaces the remaining
  guess, and it is a 2-minute measurement on proto #1, not a purchase.

  **As-built risk (fabricated protos only):** prototypes light up, so the
  array survives whatever it draws today; the defect is that nobody knows
  what that is, and it varies per unit and with temperature. On the current
  design this is closed: `datasheet_specs.py::J4.8` records `LED_BLA` (not
  the hard tie), so `verify_datasheet_nets` would catch a regression — the
  R25 pattern (spec file agreeing with the deviation) no longer applies to
  this pin.
- **The IP5306 boost auto-shuts down after 32 s below 45 mA, and nothing
  can wake it** (R30-MED-3, raised 2026-07-31). Datasheet V1.32 p.8/p.10:
  the boost turns off on sustained light load and restarts only on a KEY
  press or USB insertion. On this board net `IP5306_KEY` = {R16.2, U2.5} —
  a static 100 k pull-up, **no button** — so a light-load shutdown on
  battery is terminal until a cable is plugged in. Today it never triggers
  only because the running CPU + backlight keep +5V draw above 45 mA; that
  is an accident, not a design property (and the backlight respin above
  would thin exactly that margin). **Firmware constraint until the respin:
  no idle/sleep state may drop +5V draw below 45 mA** — RTC wake is
  impossible once VOUT cuts. Respin: route KEY to a real button and/or fit
  a keep-alive bleeder. No gate can see dynamic load; the deciding test is
  a bench idle-current measurement on a proto.
- **The PDM audio line reaches the PAM8403 with no reconstruction
  low-pass** (R3-MED-2, deferred to the respin since R3 — recorded here
  2026-07-31 because it was previously only in `hardware-audit-bugs.md`
  and invisible to anyone treating this file as the open list). The only
  elements between GPIO17 and the amp input are C22 (series DC-block) and
  R20/R21 bias to VREF: the sigma-delta carrier reaches the amp
  unfiltered. Works on the bench (amp bandwidth does the filtering,
  badly); respin: series-R + shunt-C integrator sized for the audio band.
  Deciding test: scope the amp input on a proto.
- **The panel controller identity is unrecorded: ILI9488 or ST7796S**
  (R30-MED-4). CLAUDE.md, `datasheet_specs.py` and `software/main/display.c`
  say ILI9488 3.95"; project memory and the retro-go target driver say
  ST7796S 4.0". The two firmwares send different init sequences and one of
  them is initializing the wrong part. This is an unverified claim about
  the fabricated board; the deciding test is a **RDDID (0x04) read on a
  proto** — then make CLAUDE.md, memory, `datasheet_specs.py` and the
  losing firmware agree.
- **VBUS has no fuse — R3-HIGH-4, never actioned for 27 rounds. FIXED IN
  THE DESIGN 2026-07-31** (rediscovered by the R30 full-history
  re-verification): `F1` — BHFUSE BSMD1812-200-30V PTC (hold 2 A / trip
  4 A / 20 mΩ, C960026), sized for the IP5306's ~2 A charge draw — now
  sits in series between J1's VBUS lands and everything downstream. The
  connector side is net `VBUS_IN` (J1 pads 2/11 + the reversibility
  loop); `VBUS` proper starts at F1 pad 2 (U2.1, U4.5, C17.1).
  `datasheet_specs.py::J1.2/J1.11` record `VBUS_IN`, so
  `verify_datasheet_nets` catches a regression to the fuseless path.
  Every board fabricated through `v4.3.1` has no fuse: what stands
  between a downstream short and the USB source there is the source's
  own current limit and the IP5306's internal protections — the waiver
  that was never written down. Those boards stay as they are; the next
  fabrication gets F1.
- **R22/R23 22 Ω in series on the FS USB pair** (R30-LOW-4). Espressif S3
  reference designs connect D+/D− through the TVS only — the PHY provides
  the driver impedance. Protos enumerate fine, so this is respin guidance
  only: consider 0 Ω/DNP. Gate-free by nature; the deciding evidence is
  that enumeration already works.
- **`SW16` carries the legacy footprint key `SS-12D00G3`** everywhere in
  routing/CPL; the actual part is MSK12C02 (C431540). The schematic value
  must stay `SS-12D00G3` or `verify_schematic_pcb_sync.py` fails. Renaming
  the key across routing/footprints/CPL is a respin cleanup.

---

## C — Cleanups with a known fix and a known reason they are still open

- ~~**`make render-pcb` leaves the tree in a state that fails
  `verify-all`**~~ — FIXED. There is now a `pcb-filled` target
  (`generate-pcb` → `scripts/fill-zones.sh` → Net Explorer refresh) and both
  `render-pcb` and `export-gerbers-fast` depend on it.

  Worth keeping the shape of it, because it bit three different ways from
  one cause. `generate_pcb` writes the board with **no** `filled_polygon` —
  the fill needs the pcbnew Python API, which only exists in the Docker
  image — so every consumer had to remember to fill, and the render path did
  not. That meant: the zone-fill gate went red after a documentation-only
  action; a render running concurrently with a commit made the pre-commit
  DFM hook block that commit citing zone fills, which had nothing to do with
  the change; and, least visible and worst, **renders drawn from an unfilled
  board show a board with no copper pours**.

  Fixing it exposed the same ordering bug one level further in:
  `generate-pcb` refreshed the Net Explorer data *before* the fill, so the
  shipped JSON described an unfilled board — which is also why this session
  kept having to run `make net-explorer` by hand after every gerber export.
  `pcb-filled` now refreshes it after.

  Two guards, so this cannot come back silently: `fill-zones.sh` fails if
  the fill produces zero polygons, and `verify_net_explorer_fresh` already
  catches stale JSON (it is what caught the ordering bug).

- ~~**Phantom nets `LCD_BL` and `LCD_RD`**~~ — DONE in `35d6454`. They were
  declared in `primitives.NET_LIST` with zero pads and were the only two
  `drc_check` warnings; ids 18/19 are now retired gaps, and DRC reports
  **0 errors, 0 warnings**. The prune really was two lines, and the reason
  it had been deferred was right: it forced a regeneration, a zone re-fill
  and a `release_jlcpcb/` sync. What the estimate missed is that it also
  moved five other files, because the net names were *claims* made in more
  than one place — the display sheet emitted the global labels,
  `datasheet_specs.py` accepted them via `_any_of`, `net_classifier.py`
  listed them as `lcd_ctrl`, and `verify_dfm_v2` swept ids `range(6, 20)`.
  Three gates went red in sequence during the change (`verify_netlist_diff`
  T1, `verify_schematic_pcb_sync`, `verify_schematic_overlaps`) and each
  one was pointing at a real leftover. Both FPC pins remain tied to +3V3 on
  the copper, which is what they always were.
- ~~**`collision.py` reported 31 violations on every generation that no gate
  agreed with**~~ — FIXED. It now reports **0 violations and 17 margin
  notes**, and the difference is the point: a report that is always red is a
  report nobody reads, which is how a real violation gets through.

  Two separate defects, and the split between them is worth keeping:

  1. **14 via-to-via reports were false.** Vias enter the spatial index as
     their bounding *square*, which is right for indexing and wrong for
     measuring — for a diagonal pair the square corners face each other and
     understate the gap (0.200 mm reported against 0.254 mm real). That
     approximated *ring-to-ring* number was then compared against
     `CLEARANCE_VIA_VIA`, which is the **drill** rule. The true hole gaps
     were 0.55–0.67 mm against a 0.25 mm limit. Now measured as circles,
     against both rules separately.
  2. **The other 17 were real but mis-labelled.** They are 0.150–0.170 mm
     against the *house* target of 0.175 mm, and all clear JLCPCB's 0.15 mm
     minimum. Buildable. They are now listed as margin notes rather than
     printed under a "violations detected" banner.

  Zero risk to the board, and it was checked rather than assumed: the
  collision result is only appended to `_GRID.violations`, never acted on —
  `routing._via_net` places the via either way — and the regenerated
  `.kicad_pcb` came out with **0 inserted lines**, i.e. byte-identical
  copper. Guarded by `scripts/test_collision_via_metric.py` (in
  `verify-all`), which plants both a real breach and the exact historical
  false positive; reverting the metric makes 3 of its 10 tests fail.

- ~~**`collision.py` is default-open on pad nets**~~ — FIXED 2026-08-02.
  It is default-closed now, and the way it was closed is the part worth
  keeping.

  The hole: a pad only acquired a net when the first trace endpoint landed
  on it, and net-0 pads were *skipped* in queries. A pad the router never
  targets therefore stayed invisible for the whole run and a trace could be
  laid straight across it with nothing reported — contained only by the
  post-hoc gates (`verify_trace_through_pad`, `short_circuit_analysis`,
  `analyze_pad_distances`).

  `routing.generate_all_traces()` now routes **twice**: a discovery pass
  whose output is discarded, then the emitted pass, seeded before its first
  trace with the pad→net map the first pass produced. Net 0 no longer means
  "not known yet"; it means "unconnected copper", which nothing may
  overlap. Legitimate because collision results are only appended to
  `_GRID.violations` and never steer the router — the regenerated
  `.kicad_pcb` is **byte-identical**, uuids included (the counter is
  rewound between passes, `P.uid_restore`).

  Closing one default exposed another, which is the reason this entry is
  longer than the fix: `register_pads` decided F.Cu vs B.Cu from a literal
  set of front-side refs, and that set omitted the three **fiducials**. So
  F.Cu fiducials were modelled on B.Cu, where the BTN_START track at
  x=12.20 runs through FID3 — and the moment net-0 pads stopped being
  skipped it reported as a 0.425 mm overlap. Not a board defect: FID3 is on
  F.Cu, the track is on B.Cu, they never meet. The side now comes from
  `pad_positions.get_pads_and_layers()`, i.e. from the placements, one walk
  for both halves (a second walk would consume UUIDs and shift every id in
  the board).

  Net effect on the report: **0 violations, 17 → 21 margin notes.** The
  four newly visible pairs are 0.155–0.160 mm against the 0.175 mm house
  target, all above JLCPCB's 0.15 mm minimum — buildable, same class as the
  17 that were already listed. Guarded by
  `scripts/test_collision_pad_nets.py` (13 tests, in `verify-all`), which
  plants each of the three properties: reinstating the net-0 skip fails 2
  tests, removing the uuid rewind fails 3, and mislabelling FID3's side is
  required to still reproduce the historical phantom.
- **`verify_bom_values.KNOWN_MAPPINGS`** maps `"fpc-16p-0.5mm" → 40-pin`,
  papering over a real schematic/BOM inconsistency. Fix the schematic
  symbol value instead.
- **`verify_easyeda_footprint._GEOMETRIC_MISMATCH_ALLOWLIST`** still holds
  U2 (90°) and LED2 (180°). U2's entry is now *explained* rather than
  merely tolerated — the 90° is the real ESOP-8 frame delta that H4 traced,
  and the CPL that follows from it is 270° — but the allowlist itself is
  still a tolerance, not a proof. LED2 remains tied to H6.
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
  H4's rotation question about the same connector, and conflating the two
  is not hypothetical: `2d35646` removed J4's rotation delta reasoning that
  it "would reverse all 40 FPC pins", which is the netlist axis, not the
  placement axis.
- **J4's CPL rotation of 270°** — see H4. It has now been deleted twice on
  the grounds that its justification looked thin, and both times 90° was
  the wrong answer. The contacts must face the FPC slot on J4's −X side;
  90° swaps contacts and mount tabs and contacts 0 of 42 pads.
- **USB Zdiff of 130 Ω** — a non-issue. Do not move parts or traces for it.
- **The twelve `GND on B.Cu width=0.2mm` warnings from `validate-jlcpcb`** —
  expected, and widening those traces is the wrong fix. They are the debounce
  caps C5–C16: each one's GND pad runs ~2 mm on B.Cu and drops through a
  single 0.60/0.20 via into the In1.Cu ground plane. **The layer is the
  point.** The only inner layer they could otherwise cross is In2.Cu, which
  carries the +3V3 pour — twelve traces through it would carve the plane into
  channels, which is how H-class "+3V3 resolved into four isolated groups"
  happened in the first place. One small via per cap punches a clearance
  circle the plane flows around instead; `make verify-power-nets` confirms
  +3V3 stays a single copper group. The 0.2 mm width is separately pinned by
  the button B.Cu verticals running between the caps (0.175 mm gap), and a
  wider stub would invite a wider via — a bigger hole in the same plane.
  These carry a decoupling cap's return current over 2 mm, not a supply rail;
  the rule that flags them is a blanket power-net width rule that cannot see
  the difference. Rationale is also at the generation site in
  `routing.py`, next to `DEBOUNCE_REFS`.
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
