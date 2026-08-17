# JLCDFM report — 2026-08-17 (v4.9.0, full: PCB DFM + SMT DFM)

- **Set**: v4.9.0 — headphone jack dropped, board reverted **byte-identical
  to tag v4.6.2**; git `99be0de`, gerbers md5 `c1939430`, sha256
  `df25252b…`. BOM/CPL = v4.6.2 (`e98f0ad5…` / `9bf758c1…`).
- **dfmRecordKeyId**: `611626965157208066` (live run 2026-08-17, user did
  the BOM match; PCB DFM + SMT DFM both executed).
- **Verdict**: **No real finding. CLEAN.** PCB DFM 0 DANGER; SMT DFM = 2
  artifact classes only, both proven benign, neither a board defect.

## PCB DFM — 0 DANGER

Every row 0 in the Danger column. Warnings = the accepted baseline table
(fiducial 3, pad spacing 2, annular 100, silk-to-pad 4, slot 4). Identical
to every prior v4.6.x/v4.7.0/v4.8.x PCB DFM pass — the copper is unchanged.

## SMT DFM — 2 artifact classes, drilled point-by-point

| Row | D/W/G | Object1 (drill-down) | Verdict | Our gate |
|---|---|---|---|---|
| Pin inner edge | 50/0/0 | **all J4** (FPC display connector), 0.16 mm | artifact — JLC's FPC 3D-model contacts extend past the pad inner edge by design | `verify_pad_land` (PASS) |
| Lead to hole distance | 1/0/0 | **U2** (IP5306 ESOP-8), 0 mm, hole = its own thermal via | artifact — thermal-EP GND lead vs its **same-net GND** thermal via; 0 mm is intentional (heat sink to In1.Cu GND plane), no short possible | `verify_via_in_pad` (PASS) |

Everything else = **0 DANGER**: pin left/right edge 0, pin without pad 0,
missing hole 0, component collision 0 (no J5/Q3 → the v4.8.x J1↔R2 / Q3↔J5
pairs are gone), lead-area-overlap 45 Warning (fine-pitch, accepted).

### U2 lead-to-hole — checked locally, definitively benign
Local geometry of U2 (IP5306) confirms the only holes near its leads are
GND thermal vias. The nearest **different-net** via to any U2 pad is
0.55 mm (VBUS↔+5V_VOUT, LX↔PWR_SW) — well beyond the 0.20 mm netclass, and
`verify_copper_clearance` (0 DANGER) + `verify_via_in_pad` confirm it. The
flagged 0 mm pair is the EP (GND) → its same-net GND thermal via, or the
NC pin 4 → that same via — both electrically harmless. Not a defect;
"fixing" it would mean moving a needed thermal via for a same-net advisory.

## Why these two do not go away — the proven principle

These are JLC library **3D-model** artifacts, measured model-lead-vs-our-pad,
not copper defects. Proven in v4.8.1: U5's land was grown to match JLC's
OWN reference land exactly (`verify_pad_land` coverage 1.000) and the 73
"pin edge" flags STILL persisted, because JLC's model lead extends past
their own reference land. No IPC-compliant footprint clears this class. The
J4 FPC and U2 thermal-via flags are the same class — neither is eliminable
without violating a standard footprint / removing a needed thermal via, and
neither is a real problem.

## Dispatch

- **No board change.** PCB DFM clean; SMT = 2 proven artifacts (J4 FPC
  pin-inner-edge, U2 thermal-via lead-to-hole). No NO-GATE findings — both
  classes are covered by existing gates (`verify_pad_land`,
  `verify_via_in_pad`, `verify_copper_clearance`), all green.
- Certified by hardware-audit **Round 37** (Layer 1 all green, revert
  clean, 0 findings). Board == v4.6.2 (Round-34 validated).
- **Ready for `/first-article-check` phase A** and the JLCPCB order. No
  physical first-article residual beyond the standard LED cathode-side /
  polarity checks (no jack, so no speaker-mute test).
