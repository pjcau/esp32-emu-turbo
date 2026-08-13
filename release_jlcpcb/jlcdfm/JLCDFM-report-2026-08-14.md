# JLCDFM report — 2026-08-14 (v4.7.0, pcb: PCB DFM only)

- **Set**: v4.7.0 — first JLCDFM check WITH the headphone jack J5 +
  speaker auto-mute (branch merged 73f224a, regen 0cc9304)
- **Hashes**: gerbers md5 `770e99ae`, cpl md5 `d9d01ffc`, bom md5
  `b277c935`, git `73f224a`
- **dfmRecordKeyId**: `610932343818244097`
- **Analysis**: PCB DFM only (invoked as `pcb`)
- **Verdict**: **CLEAN** — 0 DANGER on every PCB DFM row; every Warning
  matches the accepted-findings table. The v4.7.0 audio-jack/mute
  additions introduced **no new PCB DFM finding** vs the v4.6.x baseline.

## PCB DFM (Danger / Warning / Good)

| Row | D/W/G | vs accepted table |
|---|---|---|
| Sharp trace corner | 0/0/0 | ok |
| BGA pad | 0/0/0 | ok |
| Via placed within a pad | 0/0/0 | ok |
| Trace to board edge | 0/0/0 | ok |
| Trace spacing | 0/0/9 | ok |
| Unconnected trace end | 0/0/0 | ok |
| Trace width | 0/0/100 | ok |
| Fiducial | 0/3/0 | accepted (no fiducials by design) |
| Pad to board edge | 0/0/4 | ok |
| Pad spacing | 0/2/74 | accepted (same-net landing-stub vias @0.145) |
| PTH-to-trace clearance | 0/0/5 | ok |
| Annular ring | 0/100/0 | accepted (0.46/0.20 via family = 0.13 min) |
| tht to smd | 0/0/0 | ok |
| Via to pad | 0/0/0 | ok |
| Soldermask bridge | 0/0/46 | ok |
| Solder mask opening exposing trace | 0/0/0 | ok |
| Soldermask opening multiple segments | 0/0/0 | ok |
| Negative soldermask expansion | 0/0/0 | ok |
| Silkscreen to pad | 0/4/4 | accepted (0.15 mm gate floor) |
| Silkscreen to hole | 0/0/0 | ok |
| Silkscreen line width | 0/0/33 | ok |
| Slot width check | 0/4/0 | accepted (J1 shield slots 0.65) |
| all drill rows | 0/0/0 | ok |

**0 DANGER on PCB DFM.** Warning set byte-for-byte the same classes and
counts as the accepted-findings baseline.

## Not done this run

- **SMT DFM (BOM/CPL) not run** — this was a `pcb` invocation. Strongly
  recommend a follow-up `/jlcdfm-upload full`: v4.7.0 adds the **J5
  headphone jack** (a new connector whose CPL has a position/orientation
  correction flagged "verify on 3D preview") and the auto-mute parts.
  The SMT pass + 3D render is the independent orientation cross-check for
  those new parts, the way it caught the reversed LEDs on v4.6.
- Phase A `/first-article-check` on the JLC order preview still owed for
  the v4.7.0 order (new J5 connector family — keying + pin 1).

## Dispatch

- No PCB Danger to fix.
- Next: `/jlcdfm-upload full` for the SMT/assembly verdict on the new
  jack + mute circuit before the v4.7.0 order is paid.
