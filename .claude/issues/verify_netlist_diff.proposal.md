# verify_netlist_diff — PROPOSAL

**Reproduced:** `python3 scripts/verify_netlist_diff.py` — T4 fails with 7
pin-to-net mismatches. T1 (schematic nets missing from PCB) currently
**passes** — the work-order's "plus a schematic net missing from the PCB"
does not reproduce at this HEAD.

**Triage of the 7 mismatches:**

| # | Mismatch | Kind |
|---|----------|------|
| 1 | `J3.1: sch='GND' pcb='BAT_IN'` | REAL miswire (group A) |
| 2 | `Q1.2: sch='GND' pcb='BAT_IN'` | REAL miswire (group A) |
| 3 | `U1.3: sch='+3V3' pcb='EN'`   | REAL miswire (group B) |
| 4 | `LED1.1: sch='LED1_RA' pcb='GND'` | naming/convention (group C) |
| 5 | `LED1.2: sch='GND' pcb='LED1_RA'` | naming/convention (group C) |
| 6 | `LED2.1: sch='LED2_RA' pcb='GND'` | naming/convention (group C) |
| 7 | `LED2.2: sch='GND' pcb='LED2_RA'` | naming/convention (group C) |

**3 real schematic wiring bugs, 4 numbering artefacts. Three independent
root causes, three independent fixes.**

---

## Root cause

### Group A — Q1 source shorted to GND through JST pin 2

File: `scripts/generate_schematics/sheets/power_supply.py:405-409`

```python
# Q1 pin 2 (Source) — connects to BAT_IN → J3.1
# Source exits to the right toward JST connector
self.wire(q1x + 5, q1y + 1.27, jst_plus_x, q1y + 1.27)
self.wire(jst_plus_x, q1y + 1.27, jst_plus_x, jst_plus_y)
self.label("BAT_IN", q1x + 6, q1y - 0.5)
```

With `q1y = jst_y = 92`, `jst_plus_y = jst_y - 1.27 = 90.73`, and
`jst_minus_y = jst_y + 1.27 = 93.27`:

- BAT54C symbol (repurposed for the SI2301 SOT-23-3) has pin 2 at
  symbol-Y `-1.27`, so world-Y `= q1y + 1.27 = 93.27`.
- JST_PH_2 pin 1 world-Y is 90.73, pin 2 world-Y is 93.27.

The horizontal segment at `y = 93.27` lands exactly on JST pin 2
(`jst_minus_y`, which is GND). The follow-up vertical then slides up
to JST pin 1 — welding GND, JST.1 (BAT_IN) and Q1.2 (Source) into one
node. `self.label("BAT_IN", …, q1y - 0.5)` is placed 1.77 mm ABOVE the
`y = 93.27` wire and does not attach to any wire, so it can't rename the
shorted net.

Netlist confirms it (`/tmp/esp32_emu_turbo_netlist.xml`):

```
<net code="… name="GND">
  … <node ref="J3" pin="1" pinfunction="+_1" …/>
      <node ref="J3" pin="2" pinfunction="-_2" …/>
      <node ref="Q1" pin="2" pinfunction="2_2" …/>
```

### Group B — U1.3 (EN) shorted to +3V3

File: `scripts/generate_schematics/sheets/mcu.py:55-70`

```python
en_y = MCU_Y - 33.02  # EN pin level
r_en_x = px_l - 25
r_en_y = MCU_Y - 45
self.v33(r_en_x, r_en_y - 8)                    # +3V3 symbol
self.wire(r_en_x, r_en_y - 8, r_en_x, en_y)     # +3V3 → en_y
self.wire(px_l, en_y, r_en_x, en_y)             # EN pin → same node
```

The comment says the module's internal 10 k EN pull-up removes the need
for R3, then draws a direct wire from a `+3V3` power symbol to the EN
net with no series resistor. The schematic net exported for U1.3 is
therefore `+3V3` (`net code="1" name="+3V3"` in the netlist), while the
PCB has EN as its own separate copper (SW_RST bridges EN→GND when
pressed). SW_RST on a schematic where EN is literally tied to +3V3
would short the rail to ground on every press — the drawing is
electrically wrong.

### Group C — LED symbol has anode/cathode pin numbers reversed vs footprint

File: `scripts/generate_schematics/lib_symbols.py:319-321`

```
(symbol "LED_1_1"
  (pin passive line (at -3.81 0 0)   … (name "A" …) (number "1" …))
  (pin passive line (at 3.81 0 180)  … (name "K" …) (number "2" …))
```

The symbol declares **pin 1 = A**, **pin 2 = K**. The LED_0805 footprint
in `scripts/generate_pcb/footprints.py:882` uses `passive_0805` on
`F.Cu`; `_led_traces()` in `scripts/generate_pcb/routing.py:5308-5356`
documents and wires it as **pad 1 = cathode**, **pad 2 = anode**
(NCD0805R1 / C84256 datasheet):

```
# Datasheet NCD0805R1 (C84256): pad 1 = cathode (-), pad 2 = anode (+)
```

Both sides wire the physical anode to `LED{n}_RA` (through R17/R18 to
+3V3) and the physical cathode to GND. Only the pin *numbers* differ.
KiCad's own `Device:LED` uses **pin 1 = K, pin 2 = A** (matching the
footprint) — this project's private symbol is the outlier.

---

## Why the gate is right

- **Groups A and B**: the netlist export directly shows the shorted
  nets. `J3.1 + J3.2 + Q1.2` share one net node on the schematic; on
  the PCB `J3.1` carries BAT_IN, `Q1.2` carries BAT_IN, `J3.2` carries
  GND — three copper regions the schematic no longer distinguishes.
  Same for `U1.3` — the EN pull-up path on the module cannot be
  represented by a hard schematic short to +3V3 (SW_RST would
  short-circuit the rail). These are exactly the "the two sides
  describe different circuits" bug class the `_T4_STRUCTURAL_EXCEPTIONS`
  docstring warns against re-suppressing.
- **Group C**: physically identical, numerically divergent. The gate is
  right that pin numbers don't line up; the fix is a *translation*,
  not a suppression, exactly like the existing entries in
  `SCH_PIN_TO_PCB_PADS` for J1/J4/U5/U6/SW*.

No datasheet or prototype observation contradicts the gate. No entry
should move into `_T4_STRUCTURAL_EXCEPTIONS`.

---

## Proposed change

### A — fix Q1 → J3.1 wire (edit `power_supply.py`)

Route the Q1 pin 2 → JST pin 1 wire via `jst_plus_y` instead of
`q1y + 1.27`, so the horizontal never crosses JST pin 2:

```python
# Q1 pin 2 (Source) — connects to BAT_IN → J3.1
# Route via jst_plus_y so the wire never crosses JST pin 2 (GND).
self.wire(q1x + 5, q1y + 1.27, q1x + 5, jst_plus_y)
self.wire(q1x + 5, jst_plus_y, jst_plus_x, jst_plus_y)
self.label("BAT_IN", q1x + 8, jst_plus_y - 1.5)   # place label ON the wire
```

The vertical jog leaves Q1 pin 2 (215, 93.27) → (215, 90.73), staying
clear of any other pin, and the horizontal at `y = 90.73` lands on JST
pin 1 (BAT_IN). Move the label to `jst_plus_y - 1.5` so it actually
touches the segment it names.

### B — remove the direct EN → +3V3 wire (edit `mcu.py`)

Delete the three lines that create the short. Rely on the module's
integrated 10 k EN pull-up (already documented in the surrounding
comment) and add a global label so `EN` appears as its own net in the
exported netlist:

```python
en_y = MCU_Y - 33.02  # EN pin level
# EN pull-up: internal to ESP32-S3-WROOM-1 (R3 = DNP). No external
# +3V3 tie — that would short 3V3 to GND every time SW_RST is pressed.
self.glabel("EN", px_l - 5, en_y, 180)
self.wire(px_l - 5, en_y, px_l, en_y)
# (drop `r_en_x`, `r_en_y`, and the "EN pull-up on-chip" annotation
# from that block; keep C3 and SW_RST wiring further down.)
```

Then remove `"EN"` from `T2_ALLOW` in `verify_netlist_diff.py:217-223`
— the schematic now emits the `EN` net so the T2 waiver is no longer
needed.

### C — declare the LED symbol/footprint pin swap (edit `verify_netlist_diff.py`)

Add a two-line map beside the existing translations (near line ~186):

```python
# LED1 / LED2 — generic LED symbol declares pin 1 = A / pin 2 = K,
# but the LED_0805 footprint (NCD0805R1 / C84256, wired per
# routing._led_traces) uses pad 1 = K / pad 2 = A. Physical wiring
# agrees on both sides; the pin numbers do not. A wrong entry here
# still fails T4, same guarantee as J1/J4/U5/U6.
_LED_MAP = {"1": ("2",), "2": ("1",)}
SCH_PIN_TO_PCB_PADS["LED1"] = _LED_MAP
SCH_PIN_TO_PCB_PADS["LED2"] = _LED_MAP
```

(Alternative, more invasive: renumber the LED symbol in
`lib_symbols.py` to pin 1 = K / pin 2 = A to match KiCad convention,
and swap the R/GND wires in `power_supply.py:614-624 / 632-638`. That
also fixes the underlying inconsistency but changes the schematic
drawing. **Not recommended for this pass** — the map is smaller and
follows the pattern already established in the file.)

---

## Blast radius

- **Group A** (`power_supply.py`): only the wire coordinates for the
  Q1→JST segment and one label position change. Two regenerated files:
  `hardware/kicad/sheets/01-power-supply.kicad_sch` (wire xy) and
  `hardware/kicad/esp32-emu-turbo.kicad_sch` (unchanged). PCB is
  **not** regenerated (routing.py already had the correct BAT_IN
  wiring — this fix aligns the schematic to the board). No BOM / CPL /
  gerber change. `release_jlcpcb/` not touched. `board_config.h` not
  touched.
- **Group B** (`mcu.py` + `verify_netlist_diff.py`): schematic sheet
  `02-mcu.kicad_sch` regenerated with the glabel; T2_ALLOW loses
  `"EN"`. No PCB change. No BOM/CPL/gerber. `board_config.h` already
  has no EN entry.
- **Group C** (`verify_netlist_diff.py` only): pure verifier edit; no
  hardware or firmware files touched. **Zero** manufacturing impact.

None of the three groups requires a new `make generate-pcb` beyond
regenerating the two schematic sheets that groups A and B modify — the
board file is already correct. Cross-agent sync points (`config.py` ↔
`board_config.h`, `board.py` ↔ `enclosure.scad`) are unaffected.

---

## How the fix is proven

Per-group:

```bash
# All three fixes applied → verifier green
python3 scripts/verify_netlist_diff.py     # expect 4/4 PASS
```

Full regression:

```bash
python3 scripts/generate_schematics/generate.py   # regen sheets after A + B
make verify-all                                  # T1-T4 pass, no new reds
```

**Mutation test that group C's map actually discriminates** (spot-check
that it isn't a rubber-stamp): temporarily swap the LED1 map to
`{"1": ("1",), "2": ("2",)}` and re-run — the gate must go red with 4
mismatches on LED1/LED2. Restore before merge.

**Mutation test for group A**: temporarily change the fixed y from
`jst_plus_y` back to `q1y + 1.27` — the gate must go red on
`Q1.2 / J3.1`. Restore.

**Mutation test for group B**: re-insert the `self.v33(...)` wire — the
gate must go red on `U1.3`. Restore.

If any of the three mutations fails to turn the gate red, the fix isn't
discriminating and should not be applied.
