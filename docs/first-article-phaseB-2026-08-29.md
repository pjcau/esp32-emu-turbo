# First-Article Check — Phase B (arrival) — 2026-08-29

**Verdict: PASS — cleared for first power-up (bring-up protocol).**

- **Order**: JLCPCB `W2026081721393881`, v4.9.0 (board byte-identical to tag
  v4.6.2). Boards arrived 2026-08-29; article photographed is serial `0003`.
- **Evidence**: `hardware/first-article/v4.9.0-W2026081721393881/IMG_5901.jpeg`
  (top / button side), `IMG_5903.jpeg` (bottom / dense side). Compared against
  `release_jlcpcb/renders/pcba-top.png` / `pcba-bottom.png`, verified
  byte-identical to the v4.9.0 order manifest before comparison.
- **Method**: per skill — crop + magnify per package family, judge by
  body-vs-pad contradiction only (no pixel angle estimates). First-glance
  reads that the top-side LEDs were "bare pads" were overturned by the crops
  (warm HASL-toned lighting), exactly the failure mode
  `feedback_photo_pixel_estimates_unreliable` warns about.

## Per-family sweep — Bottom (dense side, checked first)

| Family | Refs | Verdict |
|---|---|---|
| Module | U1 ESP32-S3 | PASS — antenna outward at board top, matches render |
| ESOP-8 | U2 IP5306 | PASS — all 8 leads on lands; pin-1 dot not resolvable in photo (180° not photo-decidable for SOP; closed by Phase A preview, no JLC rotation warning) |
| SOT-23-5 | U3 SY8089 | PASS — 3+2 leads seated on the 5 lands |
| SOT-23-6 | U4 USBLC6 | PASS — 3+3 leads seated on the 6 lands |
| SOP-16 | U5 PAM8403 | PASS — 16 leads on both pad rows; marking orientation consistent with rot 180 (same 180° caveat as U2, closed by Phase A) |
| SOT-23 (2+1) | D1, Q1, Q2 | PASS — every part's 2+1 lead pattern is on its 3 lands. **Q1 = CLAIM-006 respin-watch item: closed** (a 90°-off SOT-23 cannot seat; no contradiction) |
| Inductors | L1 "1R0", L2 "2R2" | PASS — correct values, seated |
| Fuse | F1 ("H 200") | PASS |
| Connectors | J1 USB-C, J3 JST, J4 FPC, U6 SD | PASS — keying and body geometry match render; USB-C shell THT tabs soldered |
| Slide switch | SW16 (PWR) | PASS — actuator toward board edge |
| Buttons | SW11/12 (R/L), SW14/15 | PASS — 4 present, legs on pads |
| SW17 | (DNP by design) | PASS — correctly absent |
| Passives | C/R 0402–1206 | PASS — spot-checked along pads, no tombstones visible |

## Per-family sweep — Top (button side)

| Family | Refs | Verdict |
|---|---|---|
| Buttons | SW1–10, SW13 (D-pad 4, ABXY 4, Start/Select 2, MENU 1) | PASS — 11/11 present, 4 legs on pads each |
| LEDs | LED1 (CHG), LED2 (FULL), LED3–6 (VBUS/5V/3V3/HB) | PASS — 6/6 bodies present on pads. Absolute cathode polarity is not photo-certifiable (by design, per Phase A note): confirmed at power-up; a reversed diagnostic LED simply does not light |
| Resistors | 4× R_0805 (diag LED series) | PASS — 4/4 present above VBUS/5V/3V3/HB |

## Notes

- Panel rails / mouse bites still attached on the photographed article —
  snap off and deburr before enclosure fit checks.
- No solder anomaly visible at crop resolution; photo lighting too warm for
  fillet-quality judgment — not a Phase B requirement.

## Dispatch — cleared for power-up, in this order

1. Bring-up firmware (`/hardware-test-gen`, `software/bringup_test`),
   lowest-current supply first (USB, no battery).
2. **C33 wake RC** (respin watch list): USB out, SW16 OFF ≥1 min, then ON —
   board must boot on the cell alone. If not: press SW17 footprint's node
   or enlarge C33 on next build (SW17 populate decision hangs on this).
3. LED power-up check (closes the LED polarity `_PENDING_VALIDATION`).
4. SD enumeration, audio listen, SNES measured FPS, mechanical fit.
5. U3 `BUCK_FB` = 0.600 V is DEFERRED — no bench instruments available
   (project constraint); revisit if a multimeter materializes.
