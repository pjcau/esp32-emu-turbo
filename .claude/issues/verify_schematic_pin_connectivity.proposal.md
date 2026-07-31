# verify_schematic_pin_connectivity — proposal

**Gate:** `python3 scripts/verify_schematic_pin_connectivity.py`
**Failure:** `02-mcu.kicad_sch — 59 pins, 4 floating` (SW15 pin 1/2, SW14 pin 1/2)
**Verdict:** documentation defect on the schematic side — the copper is right,
the drawing is not. This is NOT a real open reset/boot circuit.

## 1. Root cause

`scripts/generate_schematics/sheets/mcu.py:90` and `:102` place the two push
buttons and then draw stub wires at `y ± 3.81`, i.e. VERTICAL above and below
the symbol origin:

```python
# scripts/generate_schematics/sheets/mcu.py:87-94  (SW15)
sw_rst_x = c_en_x           # = 149.76
sw_rst_y = c_en_y + 18      # = 164.98
self.sym("SW_Push", "SW15", "RESET", sw_rst_x, sw_rst_y, ["1", "2"])
self.wire(sw_rst_x, sw_rst_y - 3.81, sw_rst_x, c_en_y + 3.81)   # goes UP
self.gnd(sw_rst_x, sw_rst_y + 8)
self.wire(sw_rst_x, sw_rst_y + 3.81, sw_rst_x, sw_rst_y + 8)     # goes DOWN
```

```python
# scripts/generate_schematics/sheets/mcu.py:100-106  (SW14)
sw_boot_x = c_en_x - 30     # = 119.76
sw_boot_y = c_en_y + 55     # = 201.98
self.sym("SW_Push", "SW14", "BOOT", sw_boot_x, sw_boot_y, ["1", "2"])
self.glabel("BTN_SELECT", sw_boot_x, sw_boot_y - 8, 0, "bidirectional")
self.wire(sw_boot_x, sw_boot_y - 3.81, sw_boot_x, sw_boot_y - 8)  # goes UP
self.gnd(sw_boot_x, sw_boot_y + 8)
self.wire(sw_boot_x, sw_boot_y + 3.81, sw_boot_x, sw_boot_y + 8)  # goes DOWN
```

But `SW_Push`'s pins are HORIZONTAL, not vertical, and offset by `±5.08` — not
`±3.81` (the R/C offset the code was clearly copy-adapted from):

```
scripts/generate_schematics/lib_symbols.py:133
  (pin passive line (at -5.08 0   0) (length 2.54) (name "1") (number "1"))
scripts/generate_schematics/lib_symbols.py:134
  (pin passive line (at  5.08 0 180) (length 2.54) (name "2") (number "2"))
```

So the four floating anchors the checker reports are exactly the untouched
horizontal pins:

| ref     | pin | expected coord (from lib) | wire actually drawn at |
|---------|-----|---------------------------|------------------------|
| SW15  | 1   | (149.76 - 5.08, 164.98) = **(144.68, 164.98)** | (149.76, 161.17) |
| SW15  | 2   | (149.76 + 5.08, 164.98) = **(154.84, 164.98)** | (149.76, 168.79) |
| SW14 | 1   | (119.76 - 5.08, 201.98) = **(114.68, 201.98)** | (119.76, 198.17) |
| SW14 | 2   | (119.76 + 5.08, 201.98) = **(124.84, 201.98)** | (119.76, 205.79) |

The wires land ~5 mm below/above the pins, on nothing. Confirmed against
`hardware/kicad/02-mcu.kicad_sch:142-151` — the generated file matches the
Python 1-for-1.

Reference — the CORRECT pattern used elsewhere for the same symbol:

```python
# scripts/generate_schematics/sheets/power_supply.py:585,594-595  (SW16 — passes)
self.sym("SW_Push", "SW16", "SS-12D00G3", sw_x, sw_y, ["1", "2"])
self.glabel("BAT+", sw_x - 12, sw_y, 180, "input")
self.wire(sw_x - 5.08, sw_y, sw_x - 12, sw_y)   # horizontal, x - 5.08 → hits pin 1
```

## 2. Why the gate is right

The gate reports the physical truth of the schematic file. Cross-checked
against three independent sources:

1. **`hardware/kicad/02-mcu.kicad_sch:142-151`** — dumped raw, the `SW15`
   and `SW14` symbol tuples have zero wire endpoints, no labels and no
   junctions coinciding with `x ± 5.08, y`. No mystery: the pins are
   electrically dangling in the schematic drawing.

2. **PCB copper (`scripts/pcb_cache.py::load_cache`)** — the netlist inferred
   from the .kicad_pcb assigns the switches these nets, from
   `hardware/kicad/.pcb_cache.json`:

   ```
   SW15  pad 1 → net 53 (EN)      pad 2 → net 0 (—)
           pad 3 → net  1 (GND)     pad 4 → net 1 (GND)
   SW14 pad 1 → net  0 (—)       pad 2 → net 36 (BTN_SELECT)
           pad 3 → net  1 (GND)     pad 4 → net 1 (GND)
   ```

   So the COPPER is right. The 4-leg tactile footprints have pads 1↔2 and 3↔4
   internally shorted, and the design lands one leg of each pair — SW15
   bridges EN↔GND, SW14 bridges BTN_SELECT↔GND. GPIO0 = BTN_SELECT per
   `software/main/board_config.h:74` (`#define BTN_SELECT GPIO_NUM_0`), so
   SW14 does pull GPIO0 to GND — the ESP32 download-mode strapping — as
   intended. The `SW14` label in the schematic and the `BTN_SELECT`
   glabel attached to it are consistent: the physical select button IS the
   boot button.

3. **KiCad ERC** — would raise `pin_not_connected` on all four pins, but the
   checker header (`scripts/verify_schematic_pin_connectivity.py:9`) already
   describes this exact failure mode as the reason the gate exists: ERC ranks
   it a warning and this repo's `erc_check.py` doesn't fail the build on it.

`verify_strapping_pins.py` does not catch this because it validates
component-level facts (R3, C3, GPIO0 = BTN_SELECT, RC delay ≥ 45 kΩ · 100 nF)
— it never walks the schematic graph, so a symbol with zero connections looks
identical to a correctly wired one. `verify_schematic_pcb_sync.py` only
compares reference designator sets (SW15/SW14 are present on both sides,
so it passes trivially at the ref level and never inspects nets).

## 3. Proposed change

Minimal edit — rotate the two switches 90° so their pins line up with the
existing vertical stub wires, and stretch those stubs from `±3.81` to `±5.08`.
`sheet_base.SchematicSheet.sym()` already accepts an `angle=` kwarg
(`sheet_base.py:110`) and is used the same way for the C caps in this sheet
(`mcu.py:117`).

Rotation direction matters for pin-number correctness (pin 1 must sit on the
same net in schematic as pad 1 does on the PCB): SW15 needs pin 1 at TOP
(EN side), SW14 needs pin 2 at TOP (BTN_SELECT side). One is `angle=270`,
the other `angle=90` — the reviewer regenerates once and swaps the value if
they landed reversed; the connectivity gate will not detect the swap, but
`verify_schematic_pcb_sync.py` and a manual net inspection in eeschema will.

```diff
--- a/scripts/generate_schematics/sheets/mcu.py
+++ b/scripts/generate_schematics/sheets/mcu.py
@@ -87,10 +87,12 @@
         # --- RESET button (EN to GND, active-low) ---
         sw_rst_x = c_en_x
         sw_rst_y = c_en_y + 18
-        self.sym("SW_Push", "SW15", "RESET", sw_rst_x, sw_rst_y, ["1", "2"])
-        self.wire(sw_rst_x, sw_rst_y - 3.81, sw_rst_x, c_en_y + 3.81)
+        # angle=270 rotates pin 1 (EN side, PCB pad 1 = net EN) to TOP.
+        self.sym("SW_Push", "SW15", "RESET", sw_rst_x, sw_rst_y,
+                 ["1", "2"], angle=270)
+        self.wire(sw_rst_x, sw_rst_y - 5.08, sw_rst_x, c_en_y + 3.81)
         self.gnd(sw_rst_x, sw_rst_y + 8)
-        self.wire(sw_rst_x, sw_rst_y + 3.81, sw_rst_x, sw_rst_y + 8)
+        self.wire(sw_rst_x, sw_rst_y + 5.08, sw_rst_x, sw_rst_y + 8)
         self.text("Reset (EN->GND)", sw_rst_x - 25, sw_rst_y, 1.5)

         # --- BOOT button (GPIO0 to GND, enter download mode) ---
@@ -99,10 +101,12 @@
         # headers, which live at y ~ MCU_Y - 35 .. MCU_Y + 12.
         sw_boot_x = c_en_x - 30
         sw_boot_y = c_en_y + 55
-        self.sym("SW_Push", "SW14", "BOOT", sw_boot_x, sw_boot_y, ["1", "2"])
+        # angle=90 rotates pin 2 (BTN_SELECT side, PCB pad 2 = net BTN_SELECT)
+        # to TOP so it lands on the existing BTN_SELECT glabel stub.
+        self.sym("SW_Push", "SW14", "BOOT", sw_boot_x, sw_boot_y,
+                 ["1", "2"], angle=90)
         self.glabel("BTN_SELECT", sw_boot_x, sw_boot_y - 8, 0, "bidirectional")
-        self.wire(sw_boot_x, sw_boot_y - 3.81, sw_boot_x, sw_boot_y - 8)
+        self.wire(sw_boot_x, sw_boot_y - 5.08, sw_boot_x, sw_boot_y - 8)
         self.gnd(sw_boot_x, sw_boot_y + 8)
-        self.wire(sw_boot_x, sw_boot_y + 3.81, sw_boot_x, sw_boot_y + 8)
+        self.wire(sw_boot_x, sw_boot_y + 5.08, sw_boot_x, sw_boot_y + 8)
```

Alternative (Option B): mirror the SW16 pattern instead — leave the
switches horizontal and redraw the RC / GND stubs left-to-right. Larger
diff (rewrites the C3-EN column and the GND drop for each button); no
functional advantage over Option A.

## 4. Blast radius

Only touches the schematic drawing.

- **`hardware/kicad/02-mcu.kicad_sch`** — regenerated: wire endpoints change,
  the two switch symbols pick up an `at … 90` / `at … 270` field, and the
  netlist derived from the schematic now includes the switches on EN, GND
  and BTN_SELECT (previously they contributed zero connections).
- **PCB copper (`hardware/kicad/esp32-emu-turbo.kicad_pcb`)** — not touched.
  Nets are set by `scripts/generate_pcb/routing.py`, not by importing the
  schematic netlist. `pcb_cache.json` invalidates only if the .kicad_pcb hash
  changes; it will not.
- **CPL, BOM, gerbers, `release_jlcpcb/`** — none changes. Reference set,
  values, footprints, positions and rotations are unchanged.
- **Firmware `software/main/board_config.h`** — none. GPIO0 = BTN_SELECT is
  unchanged; the boot-strapping logic that was already correct remains so.
- **`docs/`, net-explorer** — none, unless the .kicad_sch is embedded.
- **ERC** — four `pin_not_connected` warnings on SW15/SW14 drop off.
- **Sibling gates** — `verify_schematic_pcb_sync.py`, `verify_strapping_pins.py`,
  `verify_power_nets.py`, `make verify-all` remain green (they were green
  before too; this fix stops silently under-reporting).

Risk: pin 1 vs pin 2 assignment. If the chosen rotation puts pin 1 on GND and
pin 2 on EN (opposite of the PCB), the schematic-vs-PCB net map disagrees
even though the connectivity gate goes green. Reviewer verifies by opening
`02-mcu.kicad_sch` in eeschema and confirming: SW15.1 sits on the EN
column, SW14.2 sits on the BTN_SELECT glabel. If reversed, swap the two
`angle=` values.

## 5. How the fix is proven

```bash
# 1) regenerate the schematic
python3 scripts/generate_schematics/generate.py

# 2) primary gate — the one currently red — goes green
python3 scripts/verify_schematic_pin_connectivity.py
# expect: 02-mcu.kicad_sch  59 pins, 0 floating  (was: 4 floating)

# 3) sibling gates still pass, and the .kicad_pcb / CPL / BOM are untouched
python3 scripts/verify_schematic_pcb_sync.py
python3 scripts/verify_strapping_pins.py
git status hardware/kicad/esp32-emu-turbo.kicad_pcb release_jlcpcb/
# expect: no changes to the PCB or the release folder

# 4) full suite
make verify-all
# expect: verify_schematic_pin_connectivity moves from FAIL to PASS;
# no other check flips state.
```

Regression guard (recommended, separate follow-up): add a mutation test that
removes the `angle=` argument from either sym() call and asserts that
`verify_schematic_pin_connectivity.py` exits 1. The gate already exists; the
mutation test proves it discriminates.
