# JLCDFM report — 2026-08-14/15 (v4.8.0, full: PCB DFM + SMT DFM)

- **Set**: v4.8.0 — J5 headphone-jack TIP/SLEEVE fix (R36-HIGH-1); git
  `6447b24`, gerbers md5 `95a5f00`, **cpl/bom byte-identical to v4.7.0**
- **dfmRecordKeyId**: `611529937427304449` (report exported 2026-08-15)
- **Verdict**: **No real finding. CLEAN.** PCB DFM 0 DANGER; the SMT
  "red dangers" are the exact same BOM-match/model-match artifact set as
  the v4.7.0 run (proven, not copper defects), and **none of them is J5**
  — so JLC's own SMT pass confirms the jack fix introduced nothing.

## PCB DFM — 0 DANGER (exported PDF)

Every row 0 Danger; warnings = accepted table (fiducial 3, pad-spacing 2,
annular 100, silk-to-pad 4, slot 4). Identical to v4.6.x/v4.7.0.

## SMT DFM — same artifact profile as v4.7.0, drilled point-by-point

| Row | D/W/G | drill-down (Object1) | verdict |
|---|---|---|---|
| Component through-hole | 1/0/0 | **J1** (USB-C peg, val −18.27) | artifact |
| Component collision | 2/1/3 | — | artifact |
| Component spacing | 1/1/70 | — | artifact |
| Lead to hole distance | 3/0/0 | **U2** ×2 (thermal-EP GND via) + **J1** (peg) | artifact |
| Pin inner edge | 50/0/0 | **J4** (FPC) | artifact |
| Pin left edge | 41/0/0 | **U5** (SOP-16, 0.06 mm) | artifact |
| Pin without pad | 7/0/0 | **J1** (USB-C) | artifact |
| Pin outer edge | 1/0/0 | (U5/J1 class) | artifact |
| Pin right edge | 32/0/0 | passive/IC class | artifact |
| Missing hole for component pin | 3/0/0 | **J1** (0.9/0.6/0.6 mm) | artifact |
| Lead area overlapping pad | 2/48/0 | fine-pitch class | artifact |

Every drilled Danger hits **J1 / U2 / U5 / J4** — JLC's library 3D models
vs our (correct, working) pads. The counts are identical to the
2026-08-14 v4.7.0 run, which was fully root-caused as BOM-match /
model-match artifacts. Specific refs drift by session (v4.7.0 pin-left-edge
was passives; here it is U5) — that is the documented BOM-match variance,
not a change in the board.

## J5 is clean — the fix is confirmed

- **J5 appears in NO danger list** (checked lead-to-hole, pin-without-pad,
  missing-hole, component-through-hole, pin-left-edge — all J1/U2/U5).
- Copper proof: **cpl.csv and bom.csv are byte-identical to v4.7.0**
  (J5 placement 52.40/68.90 @180 Bottom unchanged), J5 pad/hole geometry
  unchanged (the fix was net-assignment only), and `verify_pad_land` is
  green. So the SMT geometric model-match is expected to — and does —
  reproduce v4.7.0 exactly, with J5 absent from every finding.
- The netlist fix (pad2=GND, pad3=HP_L, pad6=JACK_DET) is not visible in
  the SMT DFM (which is geometric) — it is gate-asserted (polarity +
  datasheet-nets + netlist-diff, verify-all 200/0). The 3D-orientation
  check adds nothing here because J5's CPL rotation is unchanged.

## Dispatch

- **No board change.** PCB DFM clean; SMT dangers proven to be the
  standard model-match artifacts (copper unchanged vs the clean v4.7.0
  baseline); J5 fix confirmed clean by JLC's SMT pass.
- Ready for `/first-article-check` phase A. First-article residual
  (physical-only): confirm the speaker mutes on plug insert (J5 pin 6,
  the sleeve switch, opens on insertion).
