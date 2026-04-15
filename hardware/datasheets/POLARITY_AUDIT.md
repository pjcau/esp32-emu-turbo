# Polarized Component Polarity Audit — Source of Truth

> **Purpose**: persistent, datasheet-grounded audit of every polarized component in
> the ESP32 Emu Turbo BOM. Each entry cites the manufacturer datasheet page, the
> EasyEDA reference footprint file+line, our routing pad-net assignment, and the
> final CPL rotation verdict. Intended to be read before any CPL / BOM / override
> change — **do NOT re-derive from scratch each session**.
>
> Last verified: 2026-04-15. Review after any LCSC part substitution or footprint
> library update. Cached EasyEDA footprints live in `scripts/.easyeda_cache/`.

---

## Summary table

| Ref | LCSC | Package | CPL rot | Override | Verdict |
|-----|------|---------|---------|----------|---------|
| **LED1** | C84256 | LED 0805 red | 0° | — | CORRECT |
| **LED2** | C19171391 | LED 0805 green | 180° | 180° | CORRECT w/ override |
| **C2** | C1953590 | Tantalum 22µF 16V 1206 (Vishay TMCMA1C226MTRF, ESR 2.9Ω) | 180° | 180° | CORRECT w/ override |
| **D1** | C37704 | BAT54C SOT-23 | 270° | 270° | CORRECT w/ override |
| **Q1** | C10487 | SI2301CDS SOT-23 | 90° | — | CORRECT (datasheet not on disk — uses Vishay SI2301 industry convention) |
| **U1** | C2913202 | ESP32-S3-WROOM-1 | 0° | — | CORRECT |
| **U2** | C181692 | IP5306 ESOP-8 | 0° | — | CORRECT |
| **U3** | C6186 | AMS1117-3.3 SOT-223 | 0° | — | CORRECT |
| **U4** | C7519 | USBLC6-2SC6 SOT-23-6 | 90° | — | CORRECT (datasheet not on disk — uses ST USBLC6-2SC6 industry convention) |
| **U5** | C5122557 | PAM8403 SOP-16 | 180° | 180° | CORRECT w/ override |
| **J1** | C2765186 | USB-C 16-pin | 0° | — | CORRECT |
| **J3** | C295747 | JST-PH 2P SMD | 180° | — (base rot) | CORRECT |
| **J4** | C2856812 | FPC 40P 0.5mm | 270° | 270° | CORRECT w/ override (datasheet PDF corrupted — see action #2) |

Non-polarized caps/resistors intentionally excluded. C19 is 22uF MLCC (same 1206
package as C2 but non-polarized — no polarity audit needed).

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

### LED2 — Green LED 0805 (C19171391) ⚠ EasyEDA pad numbering reversed
- **Datasheet**: `hardware/datasheets/LED2_Green-LED-0805_C19171391.pdf` p.1 —
  pin 1 = cathode (standard LED convention; triangle apex side).
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
  `_JLCPCB_ROT_OVERRIDES["LED2"] = 180`.
- **Verify tool**: `scripts/verify_easyeda_footprint.py` — LED2 in
  `_GEOMETRIC_MISMATCH_ALLOWLIST` with datasheet+EasyEDA evidence.

### C2 — Tantalum 22µF 16V 1206 (C1953590 Vishay TMCMA1C226MTRF)
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
- **Our routing**: `scripts/generate_pcb/routing.py:4784-4786`
  - pad 1 → BTN_START
  - pad 2 → BTN_SELECT
  - pad 3 → MENU_K (diode-OR into MENU input)
- **CPL rotation**: 270° override (90° base + 180° for JLCPCB 3D alignment).
- **Verdict**: CORRECT with 270° override.

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
- **Geometric mismatch allowlist**: δ_row=90° recorded in
  `scripts/verify_easyeda_footprint.py::_GEOMETRIC_MISMATCH_ALLOWLIST["Q1"]`
  with empirical-validation evidence (R4-R8 boards power via SW_PWR → Q1 conducts).
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

### U3 — AMS1117-3.3 SOT-223 (C6186)
- **Datasheet**: `hardware/datasheets/U3_AMS1117-3.3_C6186.pdf` p.1 SOT-223 Top
  View — pin 1 = GND/ADJ, pin 2 = VOUT, pin 3 = VIN, tab (pin 4) = VOUT
  (electrically same net as pin 2).
- **EasyEDA**: `scripts/.easyeda_cache/C6186/fp.pretty/SOT-223-3*.kicad_mod`
  - pad 1 at `(+2.97, +2.30)` line 17
  - pad 2 at `(+2.97, 0)`
  - pad 3 at `(+2.97, -2.30)`
  - pad 4 (tab) at `(-2.97, 0)`
  - fp_circle pin-1 at `(+3.40, +3.25)`
- **Our routing**: `scripts/generate_pcb/routing.py:5206` — pad 1 → GND, pad 2
  → +3V3, pad 3 → +5V, pad 4 (tab) → +3V3 (same net as pad 2, per datasheet).
- **CPL rotation**: 0° (no override).
- **Geometric mismatch allowlist**: δ_row=90° (EasyEDA's row direction differs
  from our library; topologically consistent). Empirically validated: R4-R8
  boards boot ESP32 on +3V3 rail.
- **Verdict**: CORRECT.

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
- **CPL rotation**: 180° override (base 90° + 180° = rotation exported).
  Per JLCPCB DFM history: without override the 3D pin-1 dot lands opposite to
  our silk pin-1 marker. Override aligns them.
- **Verdict**: CORRECT with 180° override.
- **Override location**: `_JLCPCB_ROT_OVERRIDES["U5"] = 180`.

### J1 — USB-C 16-pin SMD (C2765186)
- **Datasheet**: `hardware/datasheets/J1_USB-C-16pin_C2765186.pdf` p.1 — 16-pin
  2MD breakout. Pin 1 = GND (A1), pin 12 = GND (A12/B1), pins 4/9 = VBUS, CC1
  pin 5, CC2 pin 7, DP1/DN1 pair, DP2/DN2 pair, SBU1/SBU2, plus 4 THT shield
  slots.
- **EasyEDA**: `scripts/.easyeda_cache/C2765186/fp.pretty/USB-C-SMD*.kicad_mod`
  - pad 1 at `(-3.20, -2.38)` — bottom-left pin position
  - pad 12 at `(+3.20, -2.38)` — bottom-right
  - shield pads 13/14 = 4 THT oval slots at corners
  - fp_circle pin-1 at `(-4.45, -2.65)` — bottom-left
- **Our routing**: `scripts/generate_pcb/routing.py:907-923` — matches USB-C
  symmetric pinout (GND, VBUS, CC, data, SBU pairs on both A and B rows).
- **CPL rotation**: 0° (no override).
- **Connector symmetry**: USB-C Type-C is reversible; A-row and B-row are
  wired identically at the board level, so pin-1 orientation does not affect
  function. Still, pad 1 (GND) must physically land on the datasheet A1 corner.
- **Verdict**: CORRECT.
- **Related history**: USB-C shield slots use OVAL drills per datasheet
  (0.60×1.60 front, 0.60×1.50 rear) — see `MEMORY.md` "USB-C shield THT" entry.

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
- **CPL rotation**: 270° override. Without override, JLCPCB 3D model places pin
  1 triangle on the opposite end vs our silk.
- **Verdict**: CORRECT with 270° override.
- **Override location**: `_JLCPCB_ROT_OVERRIDES["J4"] = 270`.

---

## Override table (source of truth)

Located in `scripts/generate_pcb/jlcpcb_export.py:66-72` as `_JLCPCB_ROT_OVERRIDES`:

```python
_JLCPCB_ROT_OVERRIDES = {
    "U5":  180,  # PAM8403 C5122557 — JLCPCB 3D pin-1 dot alignment
    "J4":  270,  # FPC-40P C2856812 — bottom-contact pin-1 triangle
    "D1":  270,  # BAT54C C37704 — SOT-23 3D orientation
    "C2":  180,  # Tantalum 22uF C1953590 Vishay TMCMA1C226MTRF — EasyEDA 3D model pre-rotated 180° in kicad_mod, override compensates on bottom layer
    "LED2": 180, # Green LED C19171391 — EasyEDA pad numbering reversed
}
```

## Geometric-mismatch allowlist

Located in `scripts/verify_easyeda_footprint.py::_GEOMETRIC_MISMATCH_ALLOWLIST`
with empirical-validation evidence strings. Entries:

- **Q1** (δ=90°) — SI2301 SOT-23, boards R4-R8 (8+ prototypes) validated.
- **U2** (δ=90°) — IP5306 ESOP-8, charge/boost operational on R4-R8.
- **U3** (δ=90°) — AMS1117 SOT-223, +3V3 rail operational on R4-R8.

---

## Action items

1. **Download C7171 tantalum datasheet** (AVX / KEMET 22uF 16V 1206) into
   `hardware/datasheets/C2_Tantalum-22uF-1206_C7171.pdf`. Verify stripe side
   relative to EasyEDA pad 1. Currently relying on industry-convention +
   user's visual iBOM-vs-preview mismatch observation.
2. **Re-download J4 FPC datasheet** (HRS / Hirose FH12-40S-0.5SH or equivalent)
   from LCSC product page `C2856812` into
   `hardware/datasheets/J4_FPC-40pin-0.5mm_C2856812.pdf`. Current file is
   corrupted. Verify contact side (bottom vs top) matches `41 - panel_pin`.
3. **Download Q1 SI2301CDS datasheet** (Vishay or Alpha & Omega) into
   `hardware/datasheets/Q1_SI2301CDS-SOT23_C10487.pdf`. Currently relying on
   industry convention.
4. **Download U4 USBLC6-2SC6 datasheet** (STMicroelectronics) into
   `hardware/datasheets/U4_USBLC6-2SC6_C7519.pdf`. Currently relying on
   industry convention.
5. **Replace HTML-as-PDF BAT54C files** — all four D1 files in
   `hardware/datasheets/` are LCSC product-page HTML dumps saved with `.pdf`
   extension. Replace with the actual Nexperia/Diodes Inc BAT54C,215 PDF.

Completing these actions elevates UNVERIFIED entries to datasheet-grounded
CORRECT. The current verdicts are still defensible (via EasyEDA + routing +
empirical evidence) but not primary-source-proven.

---

## How to extend this document

- After any `_JLCPCB_ROT_OVERRIDES` change: add/update the corresponding entry
  above, cite datasheet page + EasyEDA file:line, and re-run
  `make verify-easyeda`.
- After any LCSC part substitution: re-run the audit for that ref only (fetch
  new EasyEDA footprint via `easyeda2kicad --full --lcsc_id=C######`, diff pad
  positions and silk markers, update here).
- Before every JLCPCB PCBA order: re-read this document, verify the summary
  table matches `release_jlcpcb/cpl.csv` rotations for all polarized refs.
