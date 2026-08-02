---
id: incident-power-short
title: "Incident: Power Short Circuit (PCB v1)"
sidebar_position: 4
---

# Incident: Power Short Circuit — PCB v1

**Date:** 2026-03-26 (BUG #3 added 2026-03-28) · **Severity:** Critical ·
**Affected:** 5/5 boards — design bug, not assembly ·
**Status:** fixed in `routing.py`; boards reworkable by scraping copper

## TL;DR

Six decoupling capacitors read 0 Ω to GND on every board. Three copper bugs on
F.Cu chained **GND = VBUS = +5V = +3V3** into one net:

| Bug | What | Where | Overlap |
|---|---|---|---|
| #1 | C19's GND via ring touches the VBUS horizontal trace | (108.5, 60.5) vs y=61 | 0.20 mm |
| #2 | C19's +5V via ring touches the VBUS vertical trace | (111.5, 56.5) vs x=111 | 0.20 mm |
| #3 | the 40 mm LCD_RST trace passes over a GND via **and** a VBUS via — the signal copper itself bridges two power nets | y=33, vias at x=81.5 and x=110.95 | 0.48 / 0.52 mm |

Origin: C19 was moved during a DFM fix without re-checking its ±2 mm via
offsets against the F.Cu VBUS routes, which "SHORT FIX v4" had just moved into
their path.

## Why no check caught it

- The collision grid **did** report it — buried among 180+ FPC violations,
  none treated as blocking.
- `verify_dfm_v2` checked drill-to-trace with the **drill** radius (0.175 mm),
  not the annular-ring copper radius (0.45 mm): a 0.275 mm blind spot per via.
- Bug #3 needs **grouping**: two independent "signal vs power" violations on
  the same trace are a power bridge only when seen together.

## Rework (per board, ~10 min)

No jumpers — the vias keep their inner-layer connections; only the accidental
F.Cu contact must go.

1. Scrape a 0.3 mm copper gap between the GND via ring at (108.5, 60.5) and
   the VBUS trace above it.
2. Scrape the same gap between the +5V via ring at (111.5, 56.5) and the VBUS
   trace to its left.
3. Cut the LCD_RST trace at (95, 33) — it still works via its B.Cu route.
4. Verify: all six caps (C17, C1, C18, C19, C2, C3) read high-Z; power up on a
   current-limited supply (100 mA): VBUS 5 V, +5V ≈ 5 V, +3V3 3.3 V.
5. Protect scraped areas with UV mask or clear nail polish.

Beyond these three, the manufactured board carries **44 routing violations**
(8 power bridges, 19 signal-to-power shorts) — full map and per-violation
rework in
[all-shorts-rework.md](https://github.com/pjcau/esp32-emu-turbo/blob/main/hardware/debug/all-shorts-rework.md).
Display, SD, several buttons and USB data remain compromised: v1 is a
power-rail testbed, not a fixable console.

## Gates added

| Test (in `verify_dfm_v2.py`) | Catches | Violations on v1 |
|---|---|---|
| `test_via_annular_ring_trace_clearance` | via **copper** vs traces | 72 |
| `test_signal_power_via_overlap` | signal trace touching a power via | 32 |
| `test_trace_crossing_same_layer` | same-layer trace crossings | 55 |
| `test_power_bridge_detection` | one trace touching vias of 2+ power nets | 6 |

## Lessons

1. Violations that are not blocking errors do not exist — the report that
   mentioned the short was ignored 186 times.
2. Test the right dimension: drill radius ≠ copper radius.
3. Any moved component needs its via paths re-verified against current routing.
4. Bridge detection requires grouping by trace, not pairwise checks.
