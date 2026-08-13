# JLCDFM report — 2026-08-14 (v4.7.0, full: PCB DFM + SMT DFM)

- **Set**: v4.7.0 — headphone jack J5 + auto-mute; git `73f224a`,
  gerbers md5 `770e99ae`, cpl `d9d01ffc`, bom `b277c935`
- **dfmRecordKeyId**: `610933789656313858`
- **Analysis**: PCB DFM (earlier report, CLEAN) + SMT DFM (this run)
- **Verdict**: **No copper defect — but the raw SMT count is NOT clean,
  and the extra findings are verified to be BOM-match / 3D-model-matching
  artifacts of THIS session, not board defects.** See the proof below.
  A trustworthy SMT verdict needs a clean re-match; no board change is
  indicated.

## SMT DFM raw result (Danger / Warning / Good)

| Row | D/W/G | drill-down |
|---|---|---|
| Component through-hole | 1/0/0 | — |
| Component collision warning | 2/1/3 | — |
| Component spacing | 1/1/70 | — |
| Component to board edge | 0/1/0 | — |
| **Lead to hole distance** | 3/0/0 | 2× **U2** (thermal-EP GND via, accepted) + 1× **J1** (USB-C post) |
| Component through-hole | 0/1/0 | — |
| Component clipped by outline | 0/3/0 | edge-mount, accepted |
| **Pin inner edge** | 50/0/0 | all **J4** (FPC), accepted artifact |
| **Pin left edge** | 41/0/0 | **passives** (R39,C35,C30,C26,C31,R40,R22…) ~0.05–0.11 mm |
| **Pin without pad** | 7/0/0 | all **J1** (USB-C) |
| Pin outer edge | 1/0/0 | — |
| **Pin right edge** | 32/0/0 | passives (same class as pin-left-edge) |
| Component through-hole | 1/0/0 | — |
| **Missing hole for component pin** | 3/0/0 | all **J1** (0.9/0.6/0.6 mm) |
| Lead area overlapping pad | 2/48/0 | fine-pitch/castellated, accepted class |

## Why this is not a copper regression (proof)

1. **Footprints unchanged vs the clean v4.6.2 run.** `git` diff of the
   `.kicad_pcb` shows J1, C30, C26, R22 pad geometry **byte-identical**
   between `v4.6.2` and HEAD. v4.6.2's SMT run flagged **none** of the
   pin-without-pad / pin-left/right-edge / missing-hole classes. Same
   copper → the new dangers are not from our board.
2. **`verify_pad_land` is green** — every SMD pad covers ≥ 0.80 of
   **JLC's own reference land**. That directly contradicts 73 "pin edge"
   dangers claiming the passive metallization overhangs our pads: our
   pads match JLC's reference. The overhang exists only in this session's
   matched 3D models.
3. **J1 is empirically sound.** Its footprint has 12 SMD + 4 plated-THT +
   2 NPTH pads (the USB-C shield posts DO have holes). It is unchanged
   from every proto that charges over USB-C (R4–R8) and from v4.6.2,
   which JLC itself passed clean. The 7 pin-without-pad + 3 missing-hole
   are JLC's C2765186 model expecting shield posts our (correct, working)
   footprint places differently.
4. **The genuinely new v4.7.0 parts did NOT create the clusters.** New
   refs are J5 (jack), Q3, R35–R40, C34–C35 (auto-mute). The danger
   clusters are on J1 (unchanged) and a broad passive set that includes
   old unchanged parts. J5 itself (5 SMD + 2 NPTH) is not in the
   pin-without-pad/missing-hole lists.

Conclusion: the extra SMT dangers are **BOM-match / model-matching
artifacts** whose appearance depends on how this session matched each BOM
line to JLC's library models — not defects in the v4.7.0 copper.

## Accepted-class confirmations (unchanged from baseline)

- Pin inner edge 50 × J4 — documented FPC 3D-vs-2D artifact.
- Lead to hole: the U2 thermal-EP GND-via count is 2 here (JLC counts
  both EP vias); still same-net GND, benign.
- Lead area overlapping 48 W — accepted tolerance class.

## Recommendation

- **No board change.** Copper verified unchanged/sound.
- For a trustworthy SMT verdict, re-run with a **clean BOM match** where
  every line resolves to the exact LCSC we specified (J1→C2765186,
  J5→C19712376, etc.), then diff again. The mass pin-edge/pin-without-pad
  set should collapse the way it was absent on v4.6.2.
- Before paying the v4.7.0 order, the check that matters is
  `/first-article-check` **phase A on the JLC ORDER preview** (not this
  DFM viewer): verify **J5** connector keying + pin 1, and the auto-mute
  SOT-23 **Q3** 2+1 lead side, plus SW17 not fitted.
- One footprint note to sanity-check off-critical-path: J5's pad numbering
  runs 2–6 (no pad "1") — confirm against the PJ-327A (C19712376)
  datasheet that no pin is unlanded; it seats on 5 SMD + 2 NPTH.
