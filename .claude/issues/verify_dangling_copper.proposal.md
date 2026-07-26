# verify_dangling_copper — proposal (PROPOSE-ONLY pass)

Reproduce: `python3 scripts/verify_dangling_copper.py`

Three flagged ends:

```
GND   B.Cu  (108.500, 44.000)
GND   B.Cu  (109.300, 44.000)
VBUS  F.Cu  ( 90.950, 61.000)
```

## Root cause

**Stub A — GND B.Cu (108.500, 44.000)** and **Stub B — GND B.Cu (109.300, 44.000)**
are two of the three IP5306 (U2) EP thermal-via stubs. Both come from
one loop that special-cases only the middle via:

```python
# scripts/generate_pcb/routing.py:1410-1416
for tvx, tvy in _ip5306_therm_vias:
    parts.append(_via_net(tvx, tvy, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
    # Center via (tvx = ip_ep[0]) goes all the way to EP centre (ip_ep[1]).
    if abs(tvx - ip_ep[0]) < 0.01:
        parts.append(_seg(tvx, tvy, tvx, ip_ep[1], "B.Cu", W_PWR, n_gnd))
    else:
        parts.append(_seg(tvx, tvy, tvx, ip_ep[1] + 1.5, "B.Cu", W_PWR, n_gnd))
```

`ip_ep` is the U2 EP pad centre `(110.000, 42.500)`, pad size `3.4 x 2.8`,
so the EP pad's **top edge is at y = 43.9**. The "else" branch stops the
stub at `ip_ep[1] + 1.5 = 44.000`, i.e. **0.100 mm above the pad edge**.
Vias `(108.500, 45.000)` and `(109.300, 44.500)` therefore drop a B.Cu
stub that lands in the thermal-relief gap between the via and the pad —
copper reaching nothing on the layer it was drawn on.

The block's own comment at line 1391 (*"Place inside EP pad bounds to
avoid dead-end issues"*) is the intent. The chosen number `+1.5` misses
that intent by 0.1 mm.

**Stub C — VBUS F.Cu (90.950, 61.000)** is the top end of the U4 TVS
VBUS bridge:

```python
# scripts/generate_pcb/routing.py:3383-3389 (in _usb_traces)
_tvs_vbus_via_y = 59.3
parts.append(_seg(90.95, _tvs_vbus_y, 90.95, _tvs_vbus_via_y,
                   "B.Cu", W_PWR, n_vbus))
parts.append(_via_net(90.95, _tvs_vbus_via_y, n_vbus,
                      size=VIA_STD, drill=VIA_STD_DRILL))
# F.Cu stub from via down to VBUS horizontal at y=61.0
parts.append(_seg(90.95, _tvs_vbus_via_y, 90.95, 61.0,
                   "F.Cu", W_PWR, n_vbus))
```

The horizontal that stub is supposed to meet is emitted in
`_power_traces()` at `routing.py:1232`:

```python
parts.append(_seg(vbus_fcu_start_x, vbus_fcu_y, ip_vbus_via_x, vbus_fcu_y,
                   "F.Cu", W_PWR_HIGH, n_vbus))
# → _seg(82.400, 61.000, 111.000, 61.000, "F.Cu", W_PWR_HIGH, n_vbus)
```

`(90.950, 61.000)` is the **middle** of that single 28.6-mm horizontal
segment (the endpoints of the horizontal are at x=82.400 and x=111.000).
The copper polygons overlap, so the connection is fabricated correctly,
but the checker only counts shared segment endpoints — it does not see
mid-segment T-junctions, and correctly reports "no shared endpoint,
no via, no pad, not inside a VBUS F.Cu zone".

## Why the gate is right

For stubs A and B the gate is right in the strong sense: an open circuit.
The two side thermal vias are meant to stitch the EP pad to the In1.Cu
GND plane through B.Cu; with the stub stopping 0.1 mm short of the pad,
the vias are grounded via their own barrels but they are **not** thermally
bonded to the EP on B.Cu. The EP still gets GND through (i) the centre
thermal via, whose stub does reach `ip_ep[1]`, and (ii) the In1.Cu zone
fill under the pad, so the board is not dead — but the two side vias are
performing no useful thermal function and the stubs themselves are
unterminated antennae. Nothing about the pad, via ODs or clearances gives
physical evidence that the gate is wrong here; the intent comment
("Place inside EP pad bounds") directly agrees with the gate.

For stub C the gate is a **narrow-scope false positive**: the copper is
electrically joined at fabrication through polygon overlap with the
horizontal VBUS F.Cu segment. `verify_net_connectivity` treats VBUS as
one component, DRC reports 0 unconnected pads, and running `pygerber`
over the F.Cu rasterises a single continuous polygon. The gate flags it
only because `dangling_ends()` (in `scripts/generate_net_explorer.py:135`)
counts junctions by shared endpoint coordinates and does not detect a
T that lands on the middle of another segment. The right way to make
this deterministic is to split the horizontal at the tap point, so the
junction becomes a shared endpoint the checker (and any KiCad viewer)
can see, rather than to add a waiver — silent T-junctions on the middle
of a wider trace are also a routing-code smell for the humans reviewing
the file.

## Proposed change

**Fix stubs A + B — extend all three EP thermal stubs to the pad
centre** (one law, no branch, matches the middle via already there):

```diff
--- a/scripts/generate_pcb/routing.py
+++ b/scripts/generate_pcb/routing.py
@@ -1403,15 +1403,14 @@
-    # Connect each thermal via to EP pad via a single vertical B.Cu stub.
-    # Each stub goes straight down into the EP pad area (all inside pad bounds).
-    # R9-HIGH-3 FIX (2026-04-11): the center thermal via at (110, 45) has its
-    # stub extended all the way to the EP centre (110, 42.5) so that the
-    # segment endpoint matches the EP pad centre in _PAD_POS_LOOKUP and the
-    # registrar tags EP as GND. Other thermal vias stop at y=ip_ep[1]+1.5 as
-    # before.
+    # Connect each thermal via to the EP pad with a vertical B.Cu stub
+    # that lands ON the EP pad centre (ip_ep[1]). One rule for all three
+    # vias — the previous split ("centre goes to pad centre, side vias
+    # stop at ip_ep[1]+1.5") left the two side stubs at y=44.0, which is
+    # 0.1 mm ABOVE the EP pad top edge (y=43.9). That produced dangling
+    # B.Cu copper caught by verify_dangling_copper.py, and it also broke
+    # the intended EP↔side-via thermal bond on B.Cu. Extending each stub
+    # into the pad centre restores the bond and lets the pad-net
+    # registrar tag EP as GND unconditionally.
     for tvx, tvy in _ip5306_therm_vias:
         parts.append(_via_net(tvx, tvy, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
-        # Center via (tvx = ip_ep[0]) goes all the way to EP centre (ip_ep[1]).
-        if abs(tvx - ip_ep[0]) < 0.01:
-            parts.append(_seg(tvx, tvy, tvx, ip_ep[1], "B.Cu", W_PWR, n_gnd))
-        else:
-            parts.append(_seg(tvx, tvy, tvx, ip_ep[1] + 1.5, "B.Cu", W_PWR, n_gnd))
+        parts.append(_seg(tvx, tvy, tvx, ip_ep[1], "B.Cu", W_PWR, n_gnd))
```

Effect on B.Cu stub geometry:

| Via              | Old endpoint (y) | New endpoint (y) | Effect                    |
|------------------|------------------|------------------|---------------------------|
| (108.500, 45.000)| 44.000 (0.1 out) | 42.500 (centre)  | now bonded to EP on B.Cu  |
| (110.000, 45.000)| 42.500           | 42.500 (unchanged)| unchanged                 |
| (109.300, 44.500)| 44.000 (0.1 out) | 42.500 (centre)  | now bonded to EP on B.Cu  |

Clearance check for the two extended stubs (W_PWR = 0.60, half-width 0.30):
- U2.5 KEY pad right edge x=107.850; extended stub at x=108.500 (left edge 108.200) → gap 0.350 mm ✓
- U2.6 BAT+ pad right edge x=107.850; same column → gap 0.350 mm ✓
- U2.7 LX pad right edge x=107.850; same column → gap 0.350 mm ✓
- Inside the EP pad both stubs share net GND → same-net copper merges, no clearance issue.

**Fix stub C — split the VBUS F.Cu horizontal at the U4 tap so the
junction becomes a shared endpoint:**

```diff
--- a/scripts/generate_pcb/routing.py
+++ b/scripts/generate_pcb/routing.py
@@ -1229,8 +1229,14 @@
-    # 4. F.Cu horizontal to IP5306 approach column
-    parts.append(_seg(vbus_fcu_start_x, vbus_fcu_y, ip_vbus_via_x, vbus_fcu_y,
-                       "F.Cu", W_PWR_HIGH, n_vbus))
+    # 4. F.Cu horizontal to IP5306 approach column. Split at x=90.95 so
+    #    the U4.5 VBUS F.Cu stub (emitted in _usb_traces, ends at
+    #    (90.95, 61.0)) meets a shared segment endpoint here instead of
+    #    a mid-segment T. Electrically identical; keeps
+    #    verify_dangling_copper green and makes the tap visible.
+    _u4_vbus_tap_x = 90.95
+    parts.append(_seg(vbus_fcu_start_x, vbus_fcu_y, _u4_vbus_tap_x, vbus_fcu_y,
+                       "F.Cu", W_PWR_HIGH, n_vbus))
+    parts.append(_seg(_u4_vbus_tap_x, vbus_fcu_y, ip_vbus_via_x, vbus_fcu_y,
+                       "F.Cu", W_PWR_HIGH, n_vbus))
```

The `90.95` constant is duplicated between `_power_traces()` (this split
point) and `_usb_traces()` (`_tvs_vbus_via_y`, `_seg(90.95, ..., 90.95, 61.0)`,
etc.) — pulling it into a shared constant `U4_X = 90.95` at module
scope would be cleaner and is worth a follow-up, but is outside the scope
of this red gate.

## Blast radius

- **`scripts/generate_pcb/routing.py`** — two hunks, both inside existing
  routing blocks; no new nets, no new components.
- **`hardware/kicad/esp32-emu-turbo.kicad_pcb`** — regenerated by
  `make generate-pcb`; two stub segments extend, one horizontal segment
  becomes two.
- **`hardware/kicad/.pcb_cache.json`** — auto-invalidated by SHA-256.
- **`release_jlcpcb/gerbers.zip`** — must be re-exported (`make
  export-gerbers-fast`). BOM and CPL unchanged (no component moves, no
  net-name changes, no rotations).
- **`website/static/net-explorer-data.json`** — regenerated by the
  `generate-pcb` target; `danglingEnds` becomes `[]`.
- **`software/main/board_config.h`** — no GPIO change → unchanged.
- **Docs** — unchanged; the fix is silent below the schematic layer.
- **Other verifiers** — the EP stub extensions land inside the EP pad
  (same net, same layer), so `verify_copper_clearance`,
  `verify_pad_distances`, `verify_net_class_widths` and
  `verify_datasheet_nets` are unaffected. `drc_native` may drop the
  three "dangling end" hints it was echoing.

## How the fix is proven

```
python3 scripts/verify_dangling_copper.py
# → Results: 0 dangling, 0 documented — STATUS: PASS
```

Full pipeline (after applying the diff, in a fresh implementation pass):

```
make generate-pcb                      # regenerate .kicad_pcb + net-explorer data
python3 scripts/verify_dangling_copper.py       # must exit 0
make verify-power-nets                           # must stay green
make verify-all                                  # must not add new reds
```

Regression guard suggestion (out of scope for this proposal, but worth
adding when the fix lands): a `tests/test_ip5306_thermal_bond.py` that
asserts every EP thermal via has a B.Cu segment on the same net whose
endpoint lies inside the EP pad, so the "stub stops short" class cannot
be reintroduced by a stray offset tweak.
