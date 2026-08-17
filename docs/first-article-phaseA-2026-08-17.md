# First-Article Check — Phase A (pre-order) — 2026-08-17

**Verdict: PASS — cleared for payment.**

> **ORDER PLACED 2026-08-17 — JLCPCB order `W2026081721393881`.** The paid
> order corresponds to the manifest hashes below (gerbers `df25252b…`, bom
> `e98f0ad5…`, cpl `9bf758c1…`), git set v4.9.0 == tag v4.6.2. This is the
> first physical article of the design — bring-up follows Phase B on arrival.
> JLC's own DFM review runs 4-6 h post-order; forward any note it raises.

- **Set**: v4.9.0 (board byte-identical to tag v4.6.2), git HEAD on `main`.
- **JLC order preview**: cart.jlcpcb.com PCBA viewer, `pcbFileNo=e7be776c5aed490eab91d352741c822b`,
  Component Placements tab (2D + 3D), Top and Bottom.
- **Manifest the paid order must correspond to** (order-manifest.json):
  - `gerbers.zip` `df25252b471664e3f021193dbc56fb4a2b15a8714dab441b171b7414c99ea1c0`
  - `bom.csv` `e98f0ad5eaee803efdacbe6f1a541a7a532ee76375019f3a29c0aeac15054c3b`
  - `cpl.csv` `9bf758c1557788dc8c5059403de12df0fdc4b8b44bdf609f73d865b0c2c4082f`

## BOM/CPL match
JLC Component Placements table matches our BOM exactly: LED1 C84256, LED2 +
LED3-6 C19171391, U1 ESP32-S3 C2913202, U2 IP5306 C181692, U3 SY8089 C78988,
U4 USBLC6 C7519, U5 PAM8403 (SOP-16), Q1/Q2 AO3401A C15127, D1 BAT54C C37704,
J1 USB-C C2765186, J3 JST C295747, J4 FPC C2856812, U6 SD, SW16 C431540.

## Per-family sweep (both sides)

| Family | Refs | Verdict |
|---|---|---|
| Module | U1 ESP32-S3 | PASS — antenna outward, pin-1 dot lower-left (rot 0°) |
| ESOP-8 | U2 IP5306 | PASS — pin-1 marked, seated (rot 270°; proto #1/#2 confirmed orientation) |
| SOT-23-5 | U3 SY8089 | PASS — seated on 5 lands (rot 180°) |
| SOT-23-6 | U4 USBLC6 | PASS — pin-1 marked, seated (**rot 0°** — gate-verified; POLARITY_AUDIT's "90°" is stale doc, to fix) |
| SOP-16 | U5 PAM8403 | PASS — pin-1 marked, on pad rows (rot 180°) |
| SOT-23 | Q1, Q2, D1 | PASS — 2+1 pattern seated on the 3 lands (Q1/Q2 90°, D1 90°) |
| Connectors | J1, J3, J4, U6, SW16 | PASS — keying / pin-1 correct |
| LEDs | LED1-6 | PASS (see note) |
| Buttons | SW1-SW16 | PASS — seated |

- **No "rotation adjusted" / "part rotated" warning** from JLC on any part.
- JLC states its own DFM review runs 4-6 h after the order is placed
  (additional net).

## LED polarity note (the R33-MED-2 class)
In 2D and 3D (Top), LED1 (CHG), LED2 (FULL) and LED3-6 (VBUS/5V/3V3/HB) all
carry a clear polarity mark and are **consistently oriented — no gross or
differential reversal**. Absolute cathode-on-GND is **not eyeball-certified
from the render** (skill rule: no pixel-estimate) and does not need to be:
it is closed by the gate (`verify_cpl_rotation_law` with the declared LED2-6
numbering-role exception; the R33-MED-2 180° delta was removed and is
gate-verified absent) and gets its physical confirmation on first-article
power-up (`_PENDING_VALIDATION`, Phase-B checklist item). Consequence-of-error
is low: these are diagnostic/status LEDs — a reversed one simply does not
light, a cents-level rework found at power-up, not a board failure.

## Dispatch
Phase A clean across every package family, both sides. **Proceed to payment.**
Record the order number alongside the manifest hashes above. On arrival, run
Phase B (bench checklist): thermal probe (U3/Q1), SNES measured FPS, IP5306
KEY wake pulse, SD enumeration, LED power-up (closes the LED polarity item),
audio listen, mechanical fit.
