# JLCDFM report — 2026-08-13 (v4.6.2, full: PCB DFM + SMT DFM)

- **Set**: v4.6.2 — gerbers md5 `c1939430`, cpl md5 `4c2a0640`, git `22b3d95`
- **dfmRecordKeyId**: `610732699448332290`
- **JLC report generated**: 2026-08-13 11:06:49 — PCB 4-layer, 16×7.5 cm
- **Analysis**: PCB DFM ✔ + SMT DFM ✔ (first full run of the reversed-LED-fix set)
- **Verdict**: **CLEAN** — every finding matches the accepted-findings table
  (`website/docs/manufacturing/verification.md`). Zero real findings. The
  LED2-6 CPL→0° fix introduced **no** new pin/polarity findings (proven
  point-by-point below).

## PCB DFM (Danger / Warning / Good per row)

| Row | D/W/G | vs accepted table |
|---|---|---|
| Trace spacing | 0/0/8 | ok |
| Trace width | 0/0/100 | ok |
| Fiducial | 0/3/0 | accepted (no fiducials by design) |
| Pad to board edge | 0/0/4 | ok |
| Pad spacing | 0/2/74 | accepted (same-net landing-stub vias @0.145) |
| PTH-to-trace clearance | 0/0/5 | ok |
| Annular ring | 0/100/0 | accepted (0.46/0.20 via family = 0.13 min) |
| Soldermask bridge | 0/0/46 | ok |
| Silkscreen to pad | 0/4/2 | accepted (0.15 mm gate floor) |
| Silkscreen line width | 0/0/33 | ok |
| Slot width | 0/4/0 | accepted (J1 shield slots 0.65) |
| all other rows | 0/0/0 | ok |

**0 DANGER on PCB DFM.**

## SMT DFM — Component assembly analysis (D/W/G)

| Row | D/W/G | verdict |
|---|---|---|
| Component collision warning | 0/0/3 | Good |
| Component spacing | 0/0/72 | Good |
| **Lead to hole distance** | **1**/0/0 | accepted artifact — see drill-down |
| Component clipped by board outline | 0/3/0 | accepted (J1/U6/SW16 edge-mount) |
| **Pin inner edge** | **50**/0/0 | accepted artifact — see drill-down |
| Lead area overlapping pad | 0/45/0 | accepted (3D-vs-2D tolerance class) |
| all other rows | 0/0/0 | clean |

### Point-by-point drill-down (viewer "Details", captured this run)

- **Lead to hole distance — 1 Danger**: `Value 0mm, Object1 = U2, Object2 =
  hole r13.7795`. Verified locally: the vias surrounding U2's ESOP-8
  thermal EP (108.55/109.55,44.3 and 108.95,40.5) are all **net 1 = GND**,
  the same net as the EP. A GND lead 0 mm from a GND thermal via is a
  benign same-net condition, not a joint defect. Copper is byte-identical
  to v4.6.1, whose single lead-to-hole Danger was already accepted (then
  attributed to the J1 pegs); the SMT pass re-attributes the same one
  count to U2 now that the CPL is loaded. **Same finding, same count.**
- **Pin inner edge — 50 Danger**: every one is `Value 0.16mm, Object1 =
  J4, Object2 = null`. All 50 are the FPC fine-pitch connector — the
  documented 3D-vs-2D artifact. Value drifted 0.03→0.08→**0.16** across
  reports (JLC 3D model revs), exactly as the accepted-table note
  predicts. **None is a LED** — the CPL fix added nothing here.

### LED reversal fix — confirmation

The whole reason for v4.6.2 was the LED2-6 CPL 180°→0° reversal fix.
Independent confirmation from JLC's own SMT analysis on the new set:
no polarity/rotation Danger on any LED, pin-inner-edge unchanged at 50×J4
(no LED refs), lead-overlap unchanged at 45. The fix is clean by JLC's
engine, not just by our gates.

## Dispatch

- No Danger to fix; no `/dfm-fix` or `/fix-rotation` needed.
- One accepted-table maintenance note: the "Lead to hole 1 Danger" row may
  read **U2** (SMT pass) or **J1** (PCB pass) depending on which analysis
  labels it — same copper, same count. Recorded so a future diff does not
  treat the U2 label as a new finding.
- Set is CLEAN on both analyses → ready for `/first-article-check` phase A
  (already done for v4.6.1 copper; only re-verify the LED cathode-side
  marks on the reloaded CPL before payment).
