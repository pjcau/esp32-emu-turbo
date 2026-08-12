# Polarized Component Polarity Audit — Source of Truth

> **Purpose**: persistent, datasheet-grounded audit of every polarized component in
> the ESP32 Emu Turbo BOM. Each entry cites the manufacturer datasheet page, the
> EasyEDA reference footprint file+line, our routing pad-net assignment, and the
> final CPL rotation verdict. Intended to be read before any CPL / BOM / override
> change — **do NOT re-derive from scratch each session**.
>
> Last verified: 2026-07-25 (D1 re-derived against the LIVE EasyEDA
> reference, override removed, checker model corrected — see below).
> Previous full pass: 2026-04-15. Review after any LCSC part substitution or
> footprint library update. Cached EasyEDA footprints live in
> `scripts/.easyeda_cache/`.
>
> **R25-respin sync 2026-08-02**: C2 (22µF tantalum) is deleted from the
> design and U3 is now the SY8089AAAC buck (C78988, SOT-23-5) — the summary
> table, the U3 section, the delta table and the allowlist listing below were
> brought back in line with the code. The old C2/AMS1117 evidence is kept as
> clearly-marked history.
>
> **EasyEDA API status: WORKING** (re-confirmed 2026-07-25). The earlier
> `HTTP 403` was transient rate-limiting caused by several agents fetching
> concurrently, not a permanent block. `easyeda2kicad` repopulates the cache
> normally and `scripts/verify_easyeda_footprint.py` runs a real comparison
> for every polarized ref. C37704 and C10487 were re-fetched live and match
> their archived coordinates exactly.
>
> **Note on WARN**: a WARN from that checker means "could not verify", never
> "verified good". There are currently **no WARN refs** — J1 (USB-C) was the
> last one and is now positively verified via a datasheet-derived pad-name
> alias map (see the J1 section).

---

## Summary table

| Ref | LCSC | Package | CPL rot | Override | Verdict |
|-----|------|---------|---------|----------|---------|
| **LED1** | C84256 | LED 0805 red | 0° | — | CORRECT |
| **LED2** | C19171391 | LED 0805 **red** (was mislabelled green) | **0°** | — (delta removed 2026-08-12) | CORRECTED 2026-08-12, third correction of this row — the 180° override compensated a pin-NUMBERING difference, which is a label, not a geometry. Both vendors put the physical cathode at the SAME (-x) end of their library zero; the CPL angle is a rigid body rotation (no pad-number term), so 180° put the cathode on the anode net for LED2-LED6. Caught in phase A on the v4.6.1 JLC order preview (cathode marks rendered on the LEDn_RA side; viewer fidelity anchored by U2's proto-confirmed orientation). Full re-derivation: `jlcpcb_export.py` delta-table comment; empirical closure pending on the first v4.6.2 article via `verify_easyeda_footprint._PENDING_VALIDATION` |
| **D1** | C37704 | BAT54C SOT-23 | **90°** | — | CORRECTED 2026-07-26 — was 270°, which seated no lead at all (3.120 mm off). See the correction block below |
| **Q1** | C10487 | SI2301CDS SOT-23 | **90°** | — | CORRECTED twice. 2026-07-26: 90° → 270°, because 90° seated no lead at all (2.933 mm off). 2026-08-02 (R31-HIGH-1): the KiCad placement turned 0° → 180° so the **drain** faces the cell, which carries the CPL angle back to 90°. Seating never distinguished the two — only the netlist does. See both correction blocks below |
| **U1** | C2913202 | ESP32-S3-WROOM-1 | 0° | — | CORRECT |
| **U2** | C181692 | IP5306 ESOP-8 | **270°** | — | CORRECTED 2026-07-26 — was 0°, which put 0 of 8 leads on copper. **Confirmed on protos #1 and #2**: chip vertical, pin 1 top-left from the back with USB-C on the lower edge = pad 1 (VIN/VBUS) |
| **U3** | C78988 | SY8089AAAC buck SOT-23-5 (replaces AMS1117, R25 respin) | 180° | — (family formula) | CORRECT — our land pattern is a verbatim copy of the EasyEDA reference, δ_row = 0, no waiver; see section |
| **U4** | C7519 | USBLC6-2SC6 SOT-23-6 | 90° | — | CORRECT (datasheet `U4_USBLC6-2SC6_C7519.pdf` on disk, pinout confirmed) |
| **U5** | C5122557 | PAM8403 SOP-16 | 180° | 180° | CORRECT w/ override |
| **J1** | C2765186 | USB-C 16-pin | 0° | — | CORRECT |
| **J3** | C295747 | JST-PH 2P SMD | 180° | — (base rot) | CORRECT |
| **J4** | C2856812 | FPC 40P 0.5mm | 270° | 270° | CORRECT w/ override (datasheet PDF corrupted — see action #2) |

Non-polarized caps/resistors intentionally excluded. C19 and C30 (the SY8089
buck output cap) are 22uF MLCC — non-polarized, no polarity audit needed.
**C2 (22µF tantalum, C1953590) was deleted in the R25 respin** together with
the AMS1117 it stabilized; its audit section below is retained as history.

---

## Per-component evidence

### LED1 — Red LED 0805 (C84256)
- **Datasheet**: `hardware/datasheets/LED1_Red-LED-0805_C84256.pdf` p.2 — pin 1 =
  cathode, marked on the package side with the colored bar.
- **EasyEDA**: `scripts/.easyeda_cache/C84256/fp.pretty/LED0805-RD.kicad_mod`
  - pad 1 at `(-1.10, 0)` line 27 — LEFT
  - silk cathode notch lines 17-23 (x = -1.75..-2.10) — LEFT
  - fp_circle pin-1 at `(-1.00, 0.62)` line 28 — LEFT
  - **EasyEDA pad 1 = cathode (LEFT)** — agrees with datasheet
- **Our routing**: `scripts/generate_pcb/routing.py:4620-4645` — LED1 pad 1 → GND
  (cathode), pad 2 → anode via R17 → +3V3.
- **CPL rotation**: 0° (Top layer, no override).
- **Final orientation**: cathode LEFT → GND, anode RIGHT → R17. Forward biased.
- **Verdict**: CORRECT.

### LED2 — Red LED 0805 (C19171391) — verdict CONFIRMED 2026-07-26, derivation corrected

> **CORRECTION (2026-07-26).** The 180° override below is **correct and
> unchanged**, but three claims in the original chain were wrong, and H6
> in `docs/known-issues.md` stayed open for months on the doubt they
> created:
>
> 1. *"pin 1 = cathode (standard LED convention)"* — there is no such
>    standard. The YLED0805R datasheet p.1 draws **pin ① with a "+"
>    (ANODE)** and puts the green mark at pin ② = cathode. NationStar
>    (LED1) numbers the opposite way. Per-manufacturer convention, not law.
> 2. *"EasyEDA community-footprint author convention error"* — no error:
>    the footprint follows YONGYUTAI's own numbering exactly (pad 1 =
>    anode end, silk mark at the pad-2/cathode end).
> 3. *"Without override … physical cathode on our pad 1 (GND) →
>    reverse-biased"* — terminal swapped mid-sentence: cathode on GND
>    would be *forward*. Without the override it is the **anode** that
>    lands on pad 1 (GND), which is what reverse-biases the LED. The
>    conclusion (dark) was right; the terminal named was not.
>
> Also: the part is **red** (615–630 nm), not green — "Green" was a label
> error that reached BOM, CPL, schematic, docs and this file's own
> heading. And both LEDs are plain +3V3 power indicators: U2's LED pins
> (2–4) are NC on this board, so "does it light when powered" IS a valid
> bench check, not confounded by charge state.
>
> Evidence: both manufacturer datasheets in this directory; cache
> geometry re-read independently (pads + silk from `fp.pretty`); board
> nets from `pcb_cache`. See H6 (CLOSED) in `docs/known-issues.md`.

Original chain, kept for the record:

- **Datasheet**: `hardware/datasheets/LED2_Red-LED-0805_C19171391.pdf` p.1 —
  pin 1 = cathode (standard LED convention; triangle apex side). ← WRONG, see correction
- **EasyEDA**: `scripts/.easyeda_cache/C19171391/fp.pretty/LED0805-R-RD_RED.kicad_mod`
  - pad 1 at `(+1.05, 0)` line 24 — **RIGHT**
  - silk cathode notch lines 16-20 (x = -0.34..-2.22) — LEFT
  - fp_circle pin-1 at `(+1.00, -0.63)` line 25 — RIGHT
  - **EasyEDA pad 1 is on the ANODE side** (opposite of silk cathode marker).
    This is an EasyEDA community-footprint author convention error.
- **Our routing**: same as LED1 — pad 1 → GND, pad 2 → anode via R18 → +3V3.
  Generator treats `LED_0805` footprint uniformly.
- **Without override**: JLCPCB 3D model places the physical cathode on our pad 1
  (GND) → LED reverse-biased → stays dark.
- **CPL rotation**: 0° + **180° override** → JLCPCB rotates the part 180° during
  pick-and-place; the physical cathode lands on pad 1 (GND) and anode on pad 2
  (+3V3) → forward biased.
- **Verdict**: CORRECT with 180° override.
- **Override location**: `scripts/generate_pcb/jlcpcb_export.py`
  `_JLCPCB_ROT_DELTAS["LED2"] = 180` (the absolute-override table was
  converted to additive deltas on 2026-07-25 — see the delta table below).
- **Verify tool**: `scripts/verify_easyeda_footprint.py` — LED2 in
  `_GEOMETRIC_MISMATCH_ALLOWLIST` with datasheet+EasyEDA evidence.

### C2 — Tantalum 22µF 16V 1206 (C1953590) — HISTORICAL, deleted in the R25 respin

> **Component no longer on the board.** C2 was the AMS1117 output cap; the
> R25 respin replaced that LDO with the SY8089 buck (see U3), whose output
> cap is C30 — a non-polarized 22µF MLCC. The `"C2"` rotation entry was
> removed from `jlcpcb_export.py` in the same change (a comment there marks
> the removal). C2 destroyed prototype #1 when assembled reversed
> (`website/docs/rework/incident-c2-reversed.md`) — that history is why the
> respin deliberately eliminated the board's only polarized capacitor.
> Everything below describes the pre-respin design; kept for the record.

- **Datasheet**: `hardware/datasheets/C2_Tantalum-22uF-1206_C1953590_Vishay-TMCM.pdf`
  (Vishay TMCM series — downloaded 2026-04-15 from Distrelec).
- **MPN**: Vishay TMCMA1C226MTRF — Molded Case Tantalum Electrolytic (MnO2).
  - Capacitance: 22µF ±20%
  - Voltage: 16V
  - ESR: 2.9Ω @ 100kHz (center of AMS1117 stability zone 0.3–22Ω)
  - Package: 1206 (Case A)
  - Temperature: -55°C to +125°C
  - Stock at JLCPCB (2026-04-15): 26,815 units, Extended part.
- **Historical note**: originally specified as C7171 but that LCSC is
  TAJA106K016RNJ = 10µF (not 22µF). C1953590 substituted 2026-04-15 to match
  the original 22µF design intent. Ordering SMT026041362110 requires CPL+BOM
  re-upload with this change.
- **EasyEDA**: `scripts/.easyeda_cache/C1953590/easyeda2kicad.pretty/CAP-SMD_L3.2-W1.6-FD.kicad_mod`
  - pad 1 at `(-1.20, 0)` line 20 — LEFT
  - pad 2 at `(+1.20, 0)` line 21 — RIGHT
  - silk polarity stripe (solid filled rectangle) at x=-2.03..-2.41 line 27 — LEFT
  - fp_circle pin-1 at `(-1.60, 0.80)` line 22 — LEFT
  - 3D model rotation `(rotate (xyz 0 0 180))` at line 31 — 3D rendered
    pre-rotated 180° by EasyEDA, which is why the 180° CPL override is needed
    to compensate when placing on bottom layer.
  - **EasyEDA pad 1 = anode (+) on LEFT side, same convention as prior C7171.**
- **Polarity convention** (Vishay TMCM datasheet): anode (+) is the side
  marked by the polarity bar on the package body, aligned with pin 1.
- **EasyEDA**: `scripts/.easyeda_cache/C7171/fp.pretty/CAP-SMD_L3.2-W1.6-RD-C7171.kicad_mod`
  - pad 1 at `(-1.53, 0)` line 19 — LEFT
  - fp_circle pin-1 at `(-1.83, -0.80)` — LEFT
  - No silk `+` stripe drawn (EasyEDA footprint is bare pads).
- **Convention**: tantalum 1206 industry standard — anode (+) is the side marked
  by a stripe / bar on the component body. EasyEDA C7171 3D model renders the
  stripe on the LEFT (matching pad 1).
- **Our routing**: `scripts/generate_pcb/routing.py:4474-4486` — C2 pad 1 → +3V3,
  pad 2 → GND.
- **Bottom-layer mirror**: C2 is on B.Cu. KiCad mirrors pad 1 to physical x=+1.53
  (RIGHT). CPL rotation 0° on bottom = JLCPCB 3D model viewed from bottom → shows
  stripe where EasyEDA defines it.
- **User's iBOM vs JLCPCB preview finding (2026-04-15)**: iBOM shows pad 1 on
  RIGHT (post-mirror), JLCPCB preview shows stripe on LEFT — 180° mismatch.
- **CPL rotation**: 0° + **180° override** → stripe (anode +) lands on +3V3 pad.
- **Verdict**: CORRECT with 180° override.
- **Override location**: `_JLCPCB_ROT_OVERRIDES["C2"] = 180`.

### CORRECTION 2026-07-26 — the D1/Q1 derivation below rests on a retired argument

**Read this before the D1 and Q1 sections.** They are kept for the record;
their conclusion is superseded. D1 is now **90°** and Q1 is now **270°**.

The chain below is: "Q1 is empirically validated because boards R4–R8 power
up through it → D1 has identical topology → D1 must carry Q1's angle." The
first link is broken.

**U2 shipped at `cpl=0`, an angle at which 0 of its 8 leads touch copper,
and those same boards charge and boost through it anyway.** Prototypes #1
and #2 show the IP5306 sitting *vertical* — the orientation the copper
demands, not the one the CPL asked for. JLCPCB corrected it at assembly. So
"the boards work" says what the assembler did, not what our file said, and
it cannot validate a CPL angle. That argument is now retired repo-wide.

Re-derived instead by the route that is convention-free — place the physical
part at each candidate angle, see which board pad each pin lands on, read
that pad's net — anchored on U2, whose 270° is confirmed by eye:

| ref | old | seats? | new | seats? | nets at the new angle |
|---|---|---|---|---|---|
| D1 | 270° | no, 3.120 mm on bare mask | **90°** | yes, 0.187 mm | anodes → BTN_START / BTN_SELECT, common cathode → MENU_K |
| Q1 | 90° | no, 2.933 mm on bare mask | **270°** | yes, 0.000 mm | G/S/D → RPP_GATE / BAT_IN / BAT+ |

### SUPERSEDED FOR Q1 — 2026-08-02 (R31-HIGH-1)

The 270° row above is right about seating and wrong about the circuit.
S on BAT_IN puts the cell on the **source**, and a P-channel body diode
conducts drain→source, so a reversed pack forward-biases that diode and
Q1 protects nothing. The KiCad placement is now **180°** (CPL **90°**),
which seats just as exactly, with G/S/D → RPP_GATE / **BAT+** /
**BAT_IN** — the cell on the drain.

Note what this says about the method used for the whole table: the
pad-residual test cannot tell a correct FET from a backwards one, because
both orientations seat at 0.000 mm on a symmetric SOT-23-3 land. Only the
netlist can, and the netlist agreed with the wrong one for four releases.
A residual of 0.000 mm is evidence about solderability, never about
whether the part is doing its job.

Both wanted the same family constant, so the fix was one value in
`_JLCPCB_ROT_CORRECTIONS` (`^SOT-23`, −90 → +90), not two per-part deltas.
Unlike U2 there is no solderable-but-wrong option here: a 180° error on a
SOT-23-3 puts the single leg where the pair is, so it simply does not
assemble.

**The "identical topology ⇒ identical angle" reasoning below is still
sound** — D1 and Q1 do move together. It was the shared anchor that was
wrong, and it moved both of them by 180°.

### D1 — BAT54C SOT-23 dual Schottky (C37704)
- **Datasheet**: `hardware/datasheets/D1_BAT54C-SOT23_C37704.pdf` — Nexperia
  BAT54_SER (201KB, 9 pages, downloaded 2026-04-15 from LCSC
  `datasheet/pdf/753e903e66757b8dda706efd5e61ce1e.pdf`). Confirms BAT54C =
  **Common Cathode** dual Schottky, pin 1 = Anode1, pin 2 = Anode2, pin 3 =
  Cathode (common).
- **EasyEDA**: `scripts/.easyeda_cache/C37704/fp.pretty/SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR.kicad_mod`
  - pad 1 at `(+1.24, +0.95)` — top-right (standard SOT-23 layout)
  - pad 2 at `(+1.24, -0.95)` — bottom-right
  - pad 3 at `(-1.24, 0)` — solo LEFT (common cathode pin)
  - fp_circle pin-1 at `(+1.40, +1.46)` — top-right
- **Our routing**: `scripts/generate_pcb/routing.py::_menu_diode_traces`
  - pad 1 → BTN_START
  - pad 2 → BTN_SELECT
  - pad 3 → MENU_K (diode-OR into MENU input)
- **CPL rotation**: **270°, formula-derived, override REMOVED (2026-07-25)**.
- **RE-DERIVATION (2026-07-25, R5-CRIT-6 relocation)** — the old entry
  ("270° override = 90° base + 180° for JLCPCB 3D alignment", commit
  `c7514e7`) was **wrong by 180°** and is superseded:
  - C37704 and C10487 (Q1) have **identical SOT-23-3 EasyEDA pad topology**
    (see the Q1 section below: pad 1 top-right, pad 2 bottom-right, pad 3
    solo left). Both were placed with our `SOT-23-3` footprint at KiCad 0°
    on B.Cu, so their required CPL angle must be **identical**.
  - Q1 uses the plain formula result, **90°**, and is empirically validated
    on 8+ prototypes (R4-R8 power up through Q1). `_jlcpcb_rotation()` is
    linear in `rot`, so identical footprint + identical topology + identical
    layer ⇒ identical CPL angle.
  - **U4 is NOT a second confirmation** (correction, 2026-07-25, credit to
    the `d1-polarity` session). The first version of this entry cited U4
    alongside Q1; that was wrong. Per the U4 section below, C7519's EasyEDA
    footprint puts pads 1-2-3 on the **TOP row** (pad 1 at `(-0.95, +1.15)`),
    which **matches** our `sot23_6()` (pad 1 at `(-0.95, +1.10)`) — so U4 has
    δ_row = **0**, not 90 like D1/Q1. U4 reaches 90° by a different route and
    carries no information about D1. The derivation rests on Q1 alone, which
    is sufficient.
  - **Open question — RESOLVED (2026-07-25, `d1-polarity` session)**: the
    question was why U4 (δ_row=0) and Q1 (δ_row=90) both land on CPL 90°
    while both are empirically validated. The answer is that **δ_row is not
    a predictor of the CPL angle at all**, so there is nothing to
    reconcile. Two validated data points in the same package family with
    different δ_row and the same working CPL angle prove directly that the
    CPL angle is set by the per-family constant, not by δ_row. The
    mechanism: JLCPCB's 0° reference is the orientation of the part in
    **JLCPCB's own parts library** (tape-and-reel orientation), whereas
    δ_row compares two *land-pattern drawings*. EasyEDA simply draws
    SOT-23-3 with pads 1/2 in a column and SOT-23-6 with pads 1/2/3 in a
    row — an inconsistency internal to EasyEDA's library that has no
    bearing on how the physical part sits in its tape. That is exactly why
    rotation-correction databases are keyed by **package family** rather
    than per footprint drawing.
  - Consequently the defect was in `verify_easyeda_footprint.py`, which
    treated any δ_row ≠ 0 as requiring an override. It has been fixed: see
    "Checker model correction" below.
  - D1's 270° at KiCad 0° was therefore 180° out. It was never caught by
    assembly because D1's two anodes were unrouted on every board built so
    far (that is the R5-CRIT-6 bug itself), so the diode's orientation had
    no observable effect.
  - D1 is now placed at **KiCad 180°** (SOT-23 two-pad row faces the
    BTN_START / BTN_SELECT columns). The same formula
    `(rot - 180) % 360 + (-90)` yields **270°**, so the emitted CPL angle is
    numerically unchanged while the physical part finally matches its
    footprint. The override entry is deleted.
  - **LIVE RE-FETCH CONFIRMED (2026-07-25, `d1-polarity` session)**: the
    earlier `HTTP 403` was transient rate-limiting from several agents
    fetching concurrently. `python3 -m easyeda2kicad --full
    --lcsc_id=C37704` now succeeds and returns
    `SOT-23-3_L2.9-W1.6-P1.90-LS2.8-BR.kicad_mod` with pad 1 `(+1.24,
    +0.95)`, pad 2 `(+1.24, -0.95)`, pad 3 `(-1.24, 0.00)` — **byte-for-byte
    identical to the archived coordinates** used in the derivation above.
    C10487 (Q1) was re-fetched live in the same run and likewise matches
    its archived copy. The derivation therefore rests on live data, not on
    an archive.
  - **Full-constellation proof (live)**: fitting a rigid rotation across
    all 3 pads (centroid-aligned, pin numbering held fixed) gives:

    | rotation applied to EasyEDA ref | max pad error (D1 / C37704) | (Q1 / C10487) |
    |---|---|---|
    | 0°   | 2.210 mm | 2.074 mm |
    | **90°**  | **0.187 mm** | **0.000 mm** |
    | 180° | 2.210 mm | 2.074 mm |
    | 270° | 3.120 mm | 2.933 mm |

    Our `footprints.sot23_3()` is the EasyEDA reference **rotated 90° with
    pin numbering preserved** — pin 1 stays pin 1. There is **no pin
    permutation**, so this is a drawing-convention difference, not a
    polarity defect. The 0.187 mm residual for D1 is purely the landing-pad
    dimension difference (EasyEDA `x=±1.24` vs our `y=±1.10`); it is far
    below the 0.760 mm discrimination threshold (40 % of the 1.90 mm
    pad 1→2 pitch), and any genuine pin swap would displace a pad by a full
    pitch.
  - **Why a 180° error would have mattered**: on a SOT-23 the pad field is
    asymmetric (two pads one side, one pad the other). At CPL 270° with
    KiCad 0° the single cathode pin would have been driven onto the
    two-anode side. Harmless only because the anodes were unrouted.
- **Verdict**: CORRECT at KiCad 180° / CPL 270°, **no override**. Confirmed
  analytically against the live EasyEDA reference and the Nexperia
  datasheet; `verify_easyeda_footprint.py` reports D1 `[OK]` with the
  rigid-rotation proof inline, with **no allowlist entry**.

### Q1 — SI2301CDS P-MOSFET SOT-23 (C10487)
- **Datasheet**: `hardware/datasheets/Q1_SI2301CDS-SOT23_C10487.pdf` (198KB,
  9 pages, Vishay SI2301CDS, downloaded 2026-04-15 from LCSC). Confirms
  pin 1 = Gate, pin 2 = Source, pin 3 = Drain.
- **EasyEDA**: `scripts/.easyeda_cache/C10487/fp.pretty/SOT-23-3_L3.0-W1.4-P1.90-LS2.4-BR.kicad_mod`
  - pad 1 at `(+1.10, +0.95)` — top-right
  - pad 2 at `(+1.10, -0.95)` — bottom-right
  - pad 3 at `(-1.10, 0)` — solo LEFT (drain)
  - fp_circle pin-1 at `(+1.42, +1.50)` — top-right
- **Our routing**: `scripts/generate_pcb/routing.py:1388-1390`
  - pad 1 → RPP_GATE (gate, pulled to GND via R24)
  - pad 2 → BAT_IN (source — battery side)
  - pad 3 → BAT (drain — system rail side)
- **Topology**: standard P-MOSFET reverse-polarity protection.
- **CPL rotation**: 90° (bottom-side mirror formula, no override).
- **Geometric mismatch allowlist**: **entry REMOVED 2026-07-25.** Q1 is now
  cleared *analytically* by the rigid-rotation test in
  `verify_easyeda_footprint.py::_rigid_rotation_match()`: our `sot23_3()`
  footprint is the live EasyEDA C10487 reference rotated 90° with pin
  numbering preserved (max pad error **0.000 mm** across all 3 pads), and
  `^SOT-23` has an explicit correction in `_JLCPCB_ROT_CORRECTIONS`. A
  computed full-constellation proof is strictly stronger than a
  hand-maintained δ_row sign-off, so the allowlist entry had become dead
  code. Q1 now reports `[OK]`, not `[ALLOW]`.
- **Empirical evidence (preserved here, was the allowlist rationale)**:
  boards R4-R8 (8+ prototypes) power up through slide switch SW16, which
  requires Q1 to conduct — physical polarity validated on hardware. This is
  the anchor for the whole SOT-23-3 family, including D1.
- **Verdict**: CORRECT.

### U1 — ESP32-S3-WROOM-1-N16R8 (C2913202)
- **Datasheet**: `hardware/datasheets/U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf` —
  Espressif module, 41 castellated pads. Pin 1 = GND at one corner (marked by
  triangle on metal shield).
- **EasyEDA**: module footprint `Module_ESP32-S3-WROOM-1` — pin 1 at standard
  corner location.
- **Our routing**: GPIO map per Espressif datasheet pinout table.
- **CPL rotation**: 0°. No polarity hazard — module-scale placement, pin 1
  marker well-defined.
- **Verdict**: CORRECT.

### U2 — IP5306 ESOP-8 (C181692)
- **Datasheet**: `hardware/datasheets/U2_IP5306_C181692.pdf` p.2 — ESOP-8 pin 1
  = VIN at top-left (standard DIP-8 convention with PowerPAD=GND).
- **EasyEDA**: `scripts/.easyeda_cache/C181692/fp.pretty/ESOP-8*.kicad_mod`
  - pad 1 at `(-1.91, +2.91)` line 18 — top-left
  - pads 1-4 on TOP row (y=+2.91), pads 5-8 on BOTTOM row (y=-2.91)
  - pad 9 = central PowerPAD
  - fp_circle pin-1 at `(-2.45, +2.95)` — top-left
- **Our routing**: follows IP5306 datasheet pinout (VIN, BAT, GND, VOUT, KEY,
  LIGHT_LOAD, INDICATOR, …).
- **CPL rotation**: 0° (no override).
- **Geometric mismatch allowlist**: δ_row=90° (EasyEDA places pins in
  horizontal rows; our library uses vertical rows — topologically equivalent
  after rotation). Empirically validated on R4-R8 boards (charge/boost works).
- **Verdict**: CORRECT.

### U3 — SY8089AAAC synchronous buck SOT-23-5 (C78988) — replaces AMS1117, R25 respin
- **Datasheet**: `hardware/datasheets/U3_SY8089AAAC_C78988.pdf` — AN_SY8089/A
  Rev 0.9A p.2 "Pinout (top view)": pin 1 = EN, 2 = GND, 3 = LX, 4 = IN,
  5 = FB.
- **EasyEDA**: `scripts/.easyeda_cache/C78988/fp.pretty/SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR.kicad_mod`
  - pad 1 at `(+1.30, +0.95)`, pad 2 `(+1.30, 0)`, pad 3 `(+1.30, -0.95)`,
    pad 4 `(-1.30, -0.95)`, pad 5 `(-1.30, +0.95)` — all 1.10×0.60 rect.
  - Our `footprints.py::sot23_5` is a **verbatim copy** of this frame
    (comment block above the function records the provenance), so
    `verify_easyeda_footprint` reports **δ_row = 0** for U3 — no waiver, no
    per-part delta.
- **Our routing**: `scripts/generate_pcb/routing/power.py::_buck_traces` —
  pad 4 (IN) → +5V, pad 3 (LX) → BUCK_LX → L2, pad 5 (FB) → BUCK_FB →
  R25/R26 divider (Vout = 0.6 × (1 + R25/R26) = 3.327 V), pad 2 → GND,
  pad 1 (EN) → enable per `_buck_traces`.
- **CPL rotation**: **180°** (`release_jlcpcb/cpl.csv`: `U3, SOT-23-5,
  180, Bottom`) — produced by the "SOT-23-5" family entry in
  `_JLCPCB_ROT_CORRECTIONS`, which sits ahead of the generic `^SOT-23` rule
  because the EasyEDA SOT-23-5 frame is the KiCad-standard frame rotated
  −90°. NO `_JLCPCB_ROT_DELTAS` entry (see the jlcpcb_export.py comment:
  "U3 needs NO override").
- **Verdict**: CORRECT — δ_row = 0 against the EasyEDA reference, angle from
  the family formula, no waiver. Not yet assembled on any prototype (first
  R25-respin boards pending); flag for `/first-article-check` on the SOT-23
  package family.
- **Historical**: the pre-respin U3 was the AMS1117-3.3 SOT-223 (C6186),
  audited here until 2026-07 with a δ_row=90 allowlist waiver. Its section
  is in git history (pre-R25); the waiver was removed with the swap so it
  cannot silently re-arm for the new part.

### U4 — USBLC6-2SC6 SOT-23-6 (C7519)
- **Datasheet**: `hardware/datasheets/U4_USBLC6-2SC6_C7519.pdf` (219KB,
  14 pages, STMicroelectronics USBLC6-2SC6, downloaded 2026-04-15 from LCSC).
  Confirms pin 1 = I/O1, pin 2 = GND, pin 3 = I/O2, pin 4 = I/O2, pin 5 =
  VBUS, pin 6 = I/O1.
- **EasyEDA**: `scripts/.easyeda_cache/C7519/fp.pretty/SOT-23-6*.kicad_mod`
  - pad 1 at `(-0.95, +1.15)` line 16 — top-left
  - pads 1-2-3 on TOP row, 4-5-6 on BOTTOM row
  - fp_circle pin-1 at `(-1.46, +1.40)` — top-left
- **Our routing**: `scripts/generate_pcb/routing.py:2917-2922`
  - pad 1 → USB_DM, pad 2 → GND, pad 3 → USB_DP
  - pad 4 → USB_DP, pad 5 → +5V (VBUS), pad 6 → USB_DM
- **CPL rotation**: 90° (SOT-23 bottom-side correction).
- **Verdict**: CORRECT. Routing matches USBLC6 datasheet pinout.

### U5 — PAM8403 SOP-16 (C5122557)
- **Datasheet**: `hardware/datasheets/U5_PAM8403_C5122557.pdf` p.2-3 — SOP-16
  top view. Pin 1 = INL- (top-left), pin 16 = OUTR+ (top-right). Pins 1-8 left
  column top-to-bottom, 9-16 right column bottom-to-top.
- **EasyEDA**: `scripts/.easyeda_cache/C5122557/fp.pretty/SOP-16*.kicad_mod`
  - pad 1 at `(-4.45, +2.87)` line 17 — top-left
  - pads 1-8 on TOP row (y=+2.87) left-to-right, pads 9-16 on BOTTOM row
    (y=-2.87) right-to-left
  - fp_circle pin-1 at `(-5.00, +3.15)` — top-left
- **Our routing**: follows PAM8403 datasheet pinout (INL, INR, OUTL+, OUTL-,
  OUTR+, OUTR-, VDD, PVDD, GND, PGND, /SD, VREF).
- **CPL rotation**: 180° — produced by the `^SOP-` family correction alone.
  The old absolute `_JLCPCB_ROT_OVERRIDES["U5"] = 180` merely restated the
  formula's own result (its delta was 0) and was removed as dead code in the
  2026-07-25 conversion to additive deltas — the emitted CPL angle is
  unchanged.
- **Verdict**: CORRECT (no delta entry).

### J1 — USB-C 16-pin SMD (C2765186)
- **Datasheet**: `hardware/datasheets/J1_USB-C-16pin_C2765186.pdf` p.1 — 16-pin
  2MD breakout: 12 signal lands + 4 THT shield slots.
- **Land map (CORRECTED 2026-07-25)** — the previous version of this bullet
  claimed "pins 4/9 = VBUS, CC1 pin 5, CC2 pin 7" and "pin 1 = GND (A1)". All
  four were **wrong**; they were the stale land map that `j1-reconcile`
  deleted from `datasheet_specs.py` in `48c1482`, and "land 9 = VBUS" is what
  kept DRC demanding a VBUS connection on the SBU1 land. The four wide
  0.60 mm lands each carry **two** contacts; the eight narrow 0.30 mm lands
  carry one:

  | land | contact(s) | function | x (mm) |
  |---|---|---|---:|
  | 1 | A1 + B12 | GND | -3.200 |
  | 2 | A4 + B9 | **VBUS** | -2.400 |
  | 3 | B8 | SBU2 | -1.750 |
  | 4 | A5 | **CC1** | -1.250 |
  | 5 | B7 | DN2 | -0.750 |
  | 6 | A6 | DP1 | -0.250 |
  | 7 | A7 | DN1 | +0.250 |
  | 8 | B6 | DP2 | +0.750 |
  | 9 | A8 | **SBU1** | +1.250 |
  | 10 | B5 | **CC2** | +1.750 |
  | 11 | B4 + A9 | **VBUS** | +2.400 |
  | 12 | B1 + A12 | GND | +3.200 |

  Independently confirmed three ways: (a) the USB Type-C r2.1 receptacle
  pinout applied to the datasheet contact labels; (b) the alias map below,
  derived from the datasheet drawing by a separate session; (c) the net names
  in our own `.kicad_pcb` — land 4 is `USB_CC1` and land 10 is `USB_CC2`,
  which alone disproves "CC1 pin 5, CC2 pin 7".
- **EasyEDA**: `scripts/.easyeda_cache/C2765186/fp.pretty/USB-C-SMD*.kicad_mod`
  - pad 1 at `(-3.20, -2.38)` — bottom-left pin position
  - pad 12 at `(+3.20, -2.38)` — bottom-right
  - shield pads 13/14 = 4 THT oval slots at corners
  - fp_circle pin-1 at `(-4.45, -2.65)` — bottom-left
- **EasyEDA**: `scripts/.easyeda_cache/C2765186/fp.pretty/USB-C-SMD*.kicad_mod`
  - pad 1 at `(-3.20, -2.38)` — bottom-left pin position
  - pad 12 at `(+3.20, -2.38)` — bottom-right
  - shield pads 13/14 = 4 THT oval slots at corners
  - fp_circle pin-1 at `(-4.45, -2.65)` — bottom-left
- **Our sources** — cited **by symbol, not line number**. The previous
  citation `routing.py:907-923` was already wrong when written (that range is
  the VBUS-to-IP5306 last-mile stubs, not the land map) and drifted a further
  6 lines afterwards. Line-number citations into generated-from-Python
  sources rot silently; symbol names do not:
  - land geometry — `scripts/generate_pcb/footprints.py::usb_c_16p`
  - pad net assignment — `scripts/generate_pcb/routing.py::_usb_c_reversibility_traces`
- **CPL rotation**: 0° (no override).
- **Connector symmetry**: USB Type-C is reversible **only because we bond the
  A-row and B-row pairs on the PCB** (DP1-DP2, DN1-DN2 per USB Type-C r2.1
  §4.2) — it is not an inherent property of the receptacle. The earlier claim
  that "A-row and B-row are wired identically at the board level" was **false
  when written**: lands 5 (B7/DN2) and 8 (B6/DP2) had no net at all, which was
  the reversibility bug. It became true with `42f51ef`. Given the bonding,
  pin-1 orientation does not affect function; pad 1 (GND) must still land on
  the datasheet A1 corner.
- **Pad-name alias map (added 2026-07-25)**: our footprint numbers the lands
  `1`..`14`; the EasyEDA reference names them by the receptacle contact(s)
  each land carries. With no shared namespace the geometric cross-check was
  **undefined**, and the checker used to fabricate a comparison from
  unrelated pads (our signal pin 13 vs EasyEDA's shield post 13), yielding a
  bogus δ_row=180° FAIL that recommended an override on a real connector. It
  also made the verdict depend on glob order — the cause of J1's historic
  cache-dependent flip-flopping.

  The map lives in `verify_easyeda_footprint.py::_PAD_NAME_ALIASES`, keyed by
  **LCSC part number** (a 16-land or 24-pin receptacle merges its GND/VBUS
  pairs differently, so it is not reusable across USB-C parts). Derived by
  the `j1-reconcile` session from `J1_USB-C-16pin_C2765186.pdf` p.1
  "RECOMMENDED PCB LAYOUT (TOP VIEW)", rendered at 1800 dpi, which labels
  each land with its contact(s) — 4 wide double-labelled (`0.60(4X)`) and 8
  narrow single-labelled (`0.30(8X)`), left to right:

  `A1.B12 | A4.B9 | B8 | A5 | B7 | A6 | A7 | B6 | A8 | B5 | B4.A9 | B1.A12`

  Independently corroborated: the EasyEDA footprint lists its pads in
  byte-identical order to the datasheet drawing.

  Our `13`/`14` are deliberately **excluded**: on both sides they are shield
  through-hole posts, but nothing guarantees the two libraries number the
  left/right post alike, so including them could inject a phantom mismatch.
- **Geometric verification result (2026-07-25)**: with the alias applied,
  all **12 signal lands match at 0.0000 mm** with rotation 0° and pin
  numbering preserved (tolerance 0.200 mm = 40 % of the 0.5 mm pitch):

  | land | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | x (mm, centred) | -3.200 | -2.400 | -1.750 | -1.250 | -0.750 | -0.250 | +0.250 | +0.750 | +1.250 | +1.750 | +2.400 | +3.200 |
  | error | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

  The wide/narrow land pattern reproduces the datasheet's `0.60(4X)` /
  `0.30(8X)` callouts. Pin-1 orientation is confirmed by the row-end anchor
  `1`→A1B12 at -3.200 and `12`→B1A12 at +3.200, 6.400 mm apart and in the
  correct order (a reversed row would give δ_row = 180°). J1 therefore
  reports `[OK]` on **positive evidence**, not on absence of a check.
- **Verdict**: CORRECT — land map verified against the datasheet-derived
  reference, 12/12 lands exact.
- **Related history — shield slot drills (CORRECTED 2026-07-25)**: OVAL
  drills, but the two ends are **deliberately asymmetric** and the old
  "0.60×1.60 front, 0.60×1.50 rear" was half stale:
  - **Rear: 0.60 × 1.40 mm** — the 1.50 was 0.10 mm over the datasheet and
    was precisely what produced the 0.1449 mm annular ring. Corrected by
    `usbc-and-drc` in `42f51ef` (`footprints.py` `USBC_SHIELD_REAR_SLOT_H`).
  - **Front: 0.60 × 1.60 mm** — held at 1.60 against the datasheet's 1.70.
    This is an **intentional 0.10 mm deviation** backed by prototype #1, not
    an error. Stated explicitly because it otherwise reads as one and invites
    a well-meaning "fix" back to 1.70.

  Note: this worktree is based on `17ada49` and does **not** contain
  `42f51ef`, so `footprints.py` here still carries the 1.50 rear value and a
  docstring repeating it. The values above describe the corrected design and
  are owned by `usbc-and-drc` / `j1-reconcile`; do not "fix" this table to
  match a pre-`42f51ef` checkout.

  The `MEMORY.md` "USB-C shield THT" entry is stale for the same reason —
  flagged to the user rather than edited, since it is user memory.

### J3 — JST PH 2P SMD battery connector (C295747)
- **Datasheet**: `hardware/datasheets/J3_JST-PH-2P-SMD_C295747.pdf` — 2-pin SMD
  top-entry, 2.00mm pitch. Pin 1 marked by silk triangle on package.
- **EasyEDA**: `scripts/.easyeda_cache/C295747/fp.pretty/CONN-SMD*.kicad_mod`
  - pad 1 at `(-1.00, -2.93)` — LEFT
  - pad 2 at `(+1.00, -2.93)` — RIGHT
  - mount-tab pads 3, 4
  - fp_circle pin-1 at `(-3.95, -4.23)`
- **Our routing**: `scripts/generate_pcb/routing.py:1394` — pad 1 → BAT+ (to
  Q1 source), pad 2 → GND.
- **CPL rotation**: 180° (base rotation from KiCad placement; NOT an override —
  set in `board.py` placement for J3 orientation).
- **Convention**: the LiPo battery cable has red = + on pin 1 and black = GND
  on pin 2. Pin 1 silk triangle on PCB must point to the red wire side.
- **Verdict**: CORRECT.

### J4 — FPC 40P 0.5mm bottom-contact (C2856812) ⚠ datasheet PDF corrupted
- **Datasheet**: `hardware/datasheets/J4_FPC-40pin-0.5mm_C2856812.pdf` — **file
  corrupted** (Circular XRef error; both Read and pdftotext fail). Action #2.
- **EasyEDA**: `scripts/.easyeda_cache/C2856812/fp.pretty/FPC-SMD_40P*.kicad_mod`
  - pad 1 at `(-9.75, -1.29)` line 20 — LEFT end of connector
  - pads 2..40 stepping x=+0.5mm each
  - pads 41, 42 = mechanical shield tabs at `(±11.44, +1.29)`
  - fp_circle pin-1 at `(-12.20, -1.58)`
  - extra silk pin-1 ring at `(-10.33, -1.24)`
- **Our routing**: bottom-contact FPC → `scripts/generate_pcb/routing.py:638-647`
  implements `_fpc_display_pin(N)` → `connector_pad = 41 - N`. Correct for
  bottom-contact convention (panel-side pin order is reversed vs connector-pad
  order). See `MEMORY.md` "J4 FPC 41-N pin reversal — DO NOT fix".
- **CPL rotation**: emitted 270° — family formula plus
  `_JLCPCB_ROT_DELTAS["J4"] = 180` (the additive form of the old absolute
  270° override; the emitted angle is byte-identical). Without the delta,
  JLCPCB's 3D model places the pin-1 triangle on the opposite end vs our
  silk. The delta's own comment block in `jlcpcb_export.py` records two
  convention-free proofs (cable side + seating residual) — read it before
  ever touching this entry again.
- **Verdict**: CORRECT with the 180° delta (emitted CPL 270°).

---

## Rotation delta table (source of truth)

Located in `scripts/generate_pcb/jlcpcb_export.py` as `_JLCPCB_ROT_DELTAS`.
The table holds **additive deltas on top of the package-family formula**, not
absolute angles — it was converted from the old absolute
`_JLCPCB_ROT_OVERRIDES` on 2026-07-25 precisely because an absolute angle
stops tracking the placement when a part is rotated in the layout (that is
how D1 shipped 180° out for months). The emitted CPL was verified
byte-identical across the conversion.

Current entries (each with a long evidence comment in the source — that
comment, not this list, is the canonical rationale):

```python
_JLCPCB_ROT_DELTAS = {
    "J4":  180,   # FPC-40P C2856812 — emitted CPL 270; two convention-free
                  # proofs (cable side, seating residual) in the source
    "LED2": 180,  # Red LED 0805 C19171391 — YONGYUTAI numbers pin 1 = anode,
                  # opposite of LED1's NationStar convention (H6 closed)
}
```

Removed entries, recorded in comments at the same location: **U5** (delta
was 0 — dead code), **C2** (component deleted in the R25 respin), **D1**
(re-derived 2026-07-25, formula suffices at KiCad 180°).

## Geometric-mismatch allowlist

Located in `scripts/verify_easyeda_footprint.py::_GEOMETRIC_MISMATCH_ALLOWLIST`
with empirical-validation evidence strings. Entries:

- **U2** (δ=90°) — IP5306 ESOP-8, charge/boost operational on R4-R8.
- **LED2** (δ=180°) — red LED 0805 (C19171391, long mislabelled green),
  analytical per the manufacturer's pin-1 = anode numbering; 2-pad part, see
  caveat below.

Removed 2026-07-25:

- **Q1** — superseded by the analytical rigid-rotation proof (see the Q1
  section). Not silenced: it now passes a *stronger* computed check.
- **D1** — never added. D1 was resolved by fixing the checker, not by
  allowlisting it.

Removed with the R25 respin:

- **U3** — the δ=90 waiver described the AMS1117 SOT-223 footprint, which no
  longer exists. The SY8089's land pattern is a verbatim EasyEDA copy
  (δ_row = 0) and needs no waiver; the source comment at the old entry's
  location warns against re-adding one for a different part.

---

## Checker model correction (2026-07-25)

`verify_easyeda_footprint.py` previously treated **any** δ_row ≠ 0 as a
defect requiring a `_JLCPCB_ROT_OVERRIDES` entry. That model was wrong and
produced a false FAIL on D1. The script's own comments admitted the gap
("the CPL rotation may already be compensated … we can't cleanly derive
this without assembly feedback, so conservatively FAIL and ask human").

**Why δ_row ≠ 0 is not, by itself, a defect.** δ_row compares two
*land-pattern drawings*. It can mean either of two very different things:

1. **Benign drawing-convention difference** — the same pad field drawn at a
   different angle, pin numbering intact. EasyEDA draws SOT-23-3 with pads
   1/2 in a column; the KiCad standard draws them in a row. No pin can land
   on the wrong net. The CPL angle for such a part comes from the
   empirically-derived per-family constant in `_JLCPCB_ROT_CORRECTIONS`,
   because JLCPCB's 0° reference is the part's orientation in **JLCPCB's
   parts library** (tape-and-reel), not in a footprint drawing.
2. **Real polarity bug** — pad *numbering* permuted or mirrored relative to
   the package geometry, so physical pin 1 lands on the pad we routed to
   pin 2. This is the C2 (since deleted) and LED2 class, and no rotation
   repairs it.

Proof that δ_row does not drive the CPL angle: Q1 (δ_row = 90) and U4
(δ_row = 0) are in the same `^SOT-23` family, both emit CPL 90°, and **both
are empirically validated on hardware**. Two validated points with different
δ_row and the same working angle settle it.

**The fix** — `_rigid_rotation_match()` fits a rigid rotation across *all*
pads with pin numbering held fixed. A match proves case 1; a non-match
leaves case 2 and still FAILs. A part is cleared automatically only when it
matches rigidly **and** its package family has an explicit entry in
`_JLCPCB_ROT_CORRECTIONS`. Tolerance is scale-aware (40 % of the tightest
pad pitch), so a genuine pin swap — always a full pitch — can never pass.

**Two-pad caveat.** For a symmetric 2-pad part (0805 LED, 1206 tantalum) a
180° rotation and a pad-1/pad-2 swap are geometrically *indistinguishable*.
The test therefore requires ≥ 3 pads and never clears such parts; LED2
remains on the manual lists, decided by silkscreen / 3D marker (C2, the
other member of this class, was deleted in the R25 respin — the board no
longer carries any polarized capacitor).

**Undefined-comparison guard.** If a pad *name* does not denote the same pin
in both libraries the comparison is meaningless. The old code silently fell
back to "first pad in file" and "lowest numeric pad > 1", fabricating a
correspondence — for J1 it compared our signal pin 13 against EasyEDA's
shield through-hole 13, yielding a bogus δ_row = 180° and a FAIL recommending
a bogus override. It also made J1's verdict depend on file/glob ordering,
which is why J1 flip-flopped with cache state. Such refs now report **WARN
("cannot verify")** instead of an invented number.

---

## Action items

1. ~~Download C7171 tantalum datasheet~~ — **OBSOLETE 2026-08-02**: C2 was
   deleted in the R25 respin; no polarized capacitor remains on the board.
2. **Re-download J4 FPC datasheet** (HRS / Hirose FH12-40S-0.5SH or equivalent)
   from LCSC product page `C2856812` into
   `hardware/datasheets/J4_FPC-40pin-0.5mm_C2856812.pdf`. Current file is
   corrupted. Verify contact side (bottom vs top) matches `41 - panel_pin`.
3. ~~Download Q1 SI2301CDS datasheet~~ — **DONE**:
   `Q1_SI2301CDS-SOT23_C10487.pdf` on disk (198KB, 9 pages, Vishay), cited
   in the Q1 section.
4. ~~Download U4 USBLC6-2SC6 datasheet~~ — **DONE**:
   `U4_USBLC6-2SC6_C7519.pdf` on disk (219KB, 14 pages, ST), cited in the
   U4 section.
5. **Replace HTML-as-PDF BAT54C files** — all four D1 files in
   `hardware/datasheets/` are LCSC product-page HTML dumps saved with `.pdf`
   extension. Replace with the actual Nexperia/Diodes Inc BAT54C,215 PDF.

Completing these actions elevates UNVERIFIED entries to datasheet-grounded
CORRECT. The current verdicts are still defensible (via EasyEDA + routing +
empirical evidence) but not primary-source-proven.

---

## How to extend this document

- After any `_JLCPCB_ROT_DELTAS` change: add/update the corresponding entry
  above, cite datasheet page + EasyEDA file:line, and re-run
  `make verify-easyeda`.
- After any LCSC part substitution: re-run the audit for that ref only (fetch
  new EasyEDA footprint via `easyeda2kicad --full --lcsc_id=C######`, diff pad
  positions and silk markers, update here).
- Before every JLCPCB PCBA order: re-read this document, verify the summary
  table matches `release_jlcpcb/cpl.csv` rotations for all polarized refs.
