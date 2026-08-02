# Diagnostic LEDs — first power-on without instruments

Introduced after v4.4.0 for the next fabrication run. The board's
historical dead-board classes (split +3V3 plane, reversed C2 shorting the
rail, rotated U2 killing the boost, open protection) all present the same
way: **a rail is silently missing**. With bench instruments unavailable,
diagnosis used to require a multimeter on the gated test points. Four
LEDs make the first photo of a powered board carry the diagnosis.

## The diagnostic tree

Power flows USB → F1 → IP5306 boost → SY8089 buck → ESP32. Each stage
has an eye on it:

| LED (silk) | Watches | OFF means | Historical bug it would have shown |
|---|---|---|---|
| **VBUS** (LED3) | VBUS, after F1 | no USB power, or F1 open | fuse F1 protection event |
| **5V** (LED4) | +5V boost output | IP5306 not boosting | U2 rotated 90° (v4.3.1) |
| **3V3** (LED5) | +3.3V buck output | buck dead, divider wrong, or rail shorted | v1 split-plane; C2 reversed (0 Ω short); R25 divider |
| **HB** (LED6) | GPIO15 heartbeat | chip not booting (straps, EN, flash) | EN with no RC delay (pre-R3/C31) |

Read it as a chain, left to right — the first dark LED names the failed
stage:

- **all dark** → no USB or F1 open (check the cable, then F1 continuity)
- **VBUS only** → boost stage: U2 orientation, L1 path, BAT+ feed
- **VBUS+5V** → buck stage: U3, R25/R26 divider, +3V3 short to GND
- **VBUS+5V+3V3, HB dark** → power is fine, boot is not: EN (R3/C31),
  GPIO0 strap (BTN_SELECT/SW14 stuck), flash
- **HB blinking 1 Hz** → alive; any subsystem failure shows as a code

## Heartbeat blink codes

While `software/bringup_test` runs, LED6 toggles at 1 Hz. On a subsystem
failure it repeats **N short blinks + pause** (cycling through all failed
codes):

| Blinks | Subsystem |
|---|---|
| 2 | SD card |
| 3 | Display |
| 4 | Audio |
| 5 | Buttons |
| 6 | PSRAM |

Serial/USB telemetry remains the detailed channel; the LED is the
cable-free fallback readable from a photo or video.

The staged commissioning walk-through that uses this tree end-to-end is
[First boot — a linear, staged session](../manufacturing/first-boot.md).

## Design notes

- All four LEDs are **C19171391** — the same red 0603 used for the
  IP5306 charge LEDs (LED1/LED2): one BOM line, JLC Basic, and a package
  whose polarity and CPL rotation law are already field-proven here.
- ~1 mA per LED. They are **bring-up parts, DNP in production**: the BOM
  marks them, the footprints stay for rework, and a shipped handheld
  does not spend ~4 mA of battery on them.
- Deliberately **no LED on BAT+**: it would drain the battery
  continuously (SW_PWR is not in series on v1 — permanent invariant).
  Battery-side diagnosis stays on the gated test points (BUCK_FB, EN).
- GPIO15 is one of only two truly free pins on this board — the
  unassigned GPIO26-37 belong to the module's flash/octal PSRAM.
- No enclosure light pipes: these LEDs are read with the case open
  during commissioning; they are not user UI.
