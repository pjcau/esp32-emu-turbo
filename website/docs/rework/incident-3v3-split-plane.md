---
id: incident-3v3-split-plane
title: "Incident: +3V3 Split Plane — Regulator Feeds Nothing (PCB v1)"
sidebar_position: 5
---

# Incident: +3V3 Split Plane — the regulator feeds nothing

**Date:** 2026-07-25
**Severity:** Critical (board cannot boot, display cannot be powered)
**Affected boards:** all PCB v1 — design bug, not an assembly defect
**Status:** Root cause identified from the copper geometry — rework documented below, v2 fix pending
**Related:** [C2 reversed](incident-c2-reversed.md) · [Power short](incident-power-short.md) · [Short-Circuit Test Bible](../manufacturing/short-test-multimeter.md)

## TL;DR

The AMS1117 outputs a clean 3.3 V. That 3.3 V reaches **nothing**.

On the inner layer `In2.Cu` the `+3V3` copper is cut into **four electrically
separate groups**. The regulator sits on a 4.92 mm² orphan island. The ESP32,
the display connector, the SD card and all twelve button pull-ups sit on a
different island that no source ever reaches.

There is **no short**. It is an **open circuit** — which is exactly why the
thermal camera shows nothing.

## Symptoms — and why each one fits

| Observed | Explanation |
|---|---|
| 3.3 V present at the regulator | Correct — the AMS1117 works |
| 0 V at the ESP32, display, SD | Their copper is a separate island |
| No short anywhere | It is an open, not a short |
| Thermal camera completely cold | No load on the island ⇒ no current ⇒ no heat. **Cold is the expected signature of an open** |
| Continuity fails with the board unpowered | The correct test — and the one that found it |

> A trace that "should go somewhere but doesn't get there" does not exist.
> That reading was right; the schematic was the thing that was wrong.

## Root cause — the inner plane is split

`In2.Cu` is a **split plane**. The `+3V3` zone covers the whole board at
priority 0. Two `+5V` zones sit on top of it at **higher priority** and carve
it up:

```
ZONE +3V3  In2.Cu  priority=0  outline = (0.5, 0.5) -> (159.5, 74.5)   whole board
ZONE +5V   In2.Cu  priority=1  outline = (105, 35)  -> (140, 65)
ZONE +5V   In2.Cu  priority=2  outline = (20, 24)   -> (42, 53)
```

**U3 (AMS1117) sits at (125, 55.5) — inside the priority-1 rectangle.** The
higher-priority `+5V` zone ate the `+3V3` copper around the regulator output
and left it as an island. The same happened to three of the display's supply
pins on J4.

![In2.Cu split plane with the orphan +3V3 islands](/img/debug/3v3-plane-split.svg)

## The four groups

Measured by geometric connectivity on the real copper (filled zone polygons,
vias, traces and pads — not the schematic):

| Group | Contains | Voltage today |
|---|---|---|
| **Regulator island** (4.92 mm²) | `U3.2` (VOUT), `U3.4` (tab), `C2.1` | **3.3 V** |
| **Main plane** | `U1.2` (ESP32), `J4.2`, `J4.3`, `J4.8`, `C3`, `C4`, `C26`, `C28`, `U6.4` (SD), `R4`–`R15` (button pull-ups) | **0 V** |
| Orphan island (0.27 mm²) | `J4.34`, `J4.35` | floating |
| Orphan island (0.20 mm²) | `J4.29` | floating |

The regulator island is **12.1 mm** from the main plane, with no trace
bridging the gap.

**Control test — same method, same board:** `GND` resolves to **1 group** and
`+5V` resolves to **1 group**. Only `+3V3` is broken. The method is not
producing false positives.

Reproduce it with:

```bash
python3 scripts/render_3v3_rework_figures.py
```

## Why the checks did not catch it

`scripts/drc_baseline.json`:

```json
{ "unconnected_zone": 7, "unconnected_accepted": 4 }
```

KiCad's DRC **was reporting these**. They were baselined under the rationale in
`scripts/drc_native.py:41`:

> `"unconnected_zone": "Power/data nets connected through inner-layer zones (not direct traces)"`

That assumption is false for `+3V3`, because the zone that was supposed to
connect them is itself split. A real defect was suppressed by a category of
accepted false positives. See the project rule: *never silence errors — no
"known false positive" filter without proof*.

## Rework on the prototype

Both jumpers are **mandatory**. Jumper 1 powers the board; jumper 2 powers the
display.

![Rework jumpers, bottom view](/img/debug/3v3-rework-jumpers.svg)

### Jumper 1 — bring +3V3 from the regulator to the main plane

| From | To | Length | Notes |
|---|---|---|---|
| **`U3` pad 4** (the wide SOT-223 tab) at (125.00, 52.35) | **`C4` pad 1** at (92.95, 42.00) | **33.7 mm** | Recommended — both are large pads, and C4 is the ESP32 decoupling cap, so the wire lands exactly where the current is needed |
| `C2` pad + (1206) at (126.50, 62.50) | `C4` pad 1 | 39.3 mm | Lower thermal mass than the tab — easier iron work |
| `U3` pad 4 | `R15` pad 2 at (97.05, 46.00) | 28.7 mm | Shortest accessible route |

:::danger Do not use the 14.6 mm via
The nearest main-plane anchor is a `+3V3` via at **(141.06, 61.72)** — only
14.6 mm away. It is **buried under the microSD socket (U6) and the SW13
button**. It is not reachable with either component fitted.
:::

**Wire gauge: AWG26 / 0.4 mm² minimum.** The entire board current — ESP32-S3 +
display + SD + audio — flows through this single jumper.

### Jumper 2 — the display supply pins

`J4.29`, `J4.34` and `J4.35` are each on an orphan island. In panel numbering
(`connector_pad = 41 − panel_pin`) those are **panel pins 12, 7 and 6** — the
ILI9488's own VDD / VDDI supplies. Without this jumper the display gets no
power even after jumper 1.

Bridge all three to **`J4.3`**, which is on the main plane. Pitch is 0.5 mm —
work under magnification, with flux, and check for bridges to the neighbouring
signal pads afterwards.

![J4 pinout with island pins highlighted](/img/debug/3v3-j4-islands.svg)

### Bring-up order after the rework

1. Board unpowered — confirm continuity from `U3` pad 4 to `U1` pin 2, to
   `C3.1`, to `J4.3` **and** to `J4.35`. All must beep.
2. Confirm `+3V3` to `GND` is **not** 0 Ω.
3. Bench supply, current limit 200 mA, ammeter in series. Idle draw under
   50 mA.
4. Measure 3.3 V at `C4.1` — not just at the regulator.
5. Regulator and ESP32 must stay cool.

## Display pin 40 is not a fault

Worth recording, because it was inspected as a suspect. The FPC has a
documented reversal (`scripts/generate_schematics/sheets/display.py:14`):

```
connector_pad = 41 - panel_pin
```

So **panel pin 40 ↔ J4 pad 1 = GND**, confirmed in the copper. Panel pin 40 is
**IM2**, the ILI9488 interface-mode select, deliberately tied to GND to select
the 8-bit 8080 parallel mode. Reading continuity to GND there is correct
behaviour.

⚠️ Note the two numbering schemes. If you probe **connector pad 40** on the
PCB, that pad carries **no net at all** — like pads 9–16, 27, 28, 33 and
37–40. Confirm which numbering is in use before calling a pin dead.

## v2 fix

The prototype rework is a patch. The layout fix is one of:

1. Raise the `+3V3` zone priority above the `+5V` zones, so `+3V3` stays
   continuous and `+5V` is the net that gets routed with traces; **or**
2. Reshape the priority-1 `+5V` rectangle so it does not enclose U3; **or**
3. Route `+3V3` from the regulator output to the ESP32 area with explicit
   copper instead of relying on the plane.

Whichever is chosen, it must be paired with a **regression guard**: a test that
fails when any power net resolves to more than one geometric group. The
grouping code in `scripts/render_3v3_rework_figures.py` (`groups_for()`) is the
working implementation. The baselined `unconnected_zone` entries must be
removed at the same time, not kept alongside the guard.
