---
name: hardware-audit
model: claude-opus-4-7
description: Deep electrical/functional audit of the ESP32 Emu Turbo hardware design. Finds bugs that prevent power-on, component operation, or emulator functionality. Cross-checks schematics, PCB, datasheets, and firmware via automated gates + manual domain-by-domain review.
disable-model-invocation: false
allowed-tools: Bash, Read, Edit, Grep, Glob, Agent, Write
---

# Hardware Functional Audit

Iterative deep-dive to find electrical, connectivity, and functional bugs
that would prevent the device from working.

## Audit Philosophy

This audit has two layers and BOTH must run:

1. **Layer 1 — Automated gates (Step 0)**: objective geometric, electrical,
   and cross-source checks. An LLM cannot find a 0.02 mm trace-through-pad
   overlap by reading schematics, so this layer runs real scripts against
   the parsed `.kicad_pcb` cache. All gates must PASS before Layer 2.
2. **Layer 2 — Domain-by-domain reasoning (Steps 1-8)**: prose review of
   each functional domain using datasheets, schematic generators, and
   firmware source. This is what an LLM does well: spotting logical
   inconsistencies, wrong component selection, pinout mismatches, boot
   sequence issues, and ambiguities between documentation and code.

Historical context: prior rounds of this audit (R1-R4) relied only on
Layer 2 and never caught the v3.3 trace-through-pad regression from
commit 775e9fd — because the bugs lived in cache geometry, not prose.
Layer 1 was added in 2026-04-10 to close that gap.

## Step 0 — Automated gates (HARD BLOCK if any fail)

Run the full gate suite. If ANY of these fail, STOP and fix before
attempting the manual domain review — a board with a geometric short,
a broken power chain, or a drifted schematic is not worth auditing in
prose.

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo

# ── Fab-short gate (MOST IMPORTANT) ──────────────────────────────
# Catches netted traces physically crossing unnetted pads (the v3.3
# regression class). Checks F.Cu and B.Cu.
python3 scripts/verify_trace_through_pad.py        # MUST be "1 passed, 0 failed"

# ── Trace-crossings gate (R9-CRIT-1 class) ──────────────────────
# Catches two traces on the SAME copper layer belonging to DIFFERENT
# nets whose capsules overlap — the physical-short class that
# verify_trace_through_pad.py does not see because it only checks
# trace-vs-pad. Missing this gate caused the R7/R8 BTN_START bridge
# to cross LCD_CS/DC/WR without anyone noticing.
python3 scripts/verify_trace_crossings.py          # MUST be "1 passed, 0 failed"

# ── Copper-clearance gate (R13 class) ───────────────────────────
# Shapely polygon-based check: for each copper layer, merges all
# features per net and measures min polygon distance between every
# different-net pair. Reports any gap < 0.10mm as DANGER and
# 0.10-0.15mm as WARN (JLCPCB preferred minimum, what JLCDFM uses
# as Warning threshold). Catches the 0.110-0.145mm track-to-pad
# gaps that KiCad DRC misses because .kicad_dru is tuned to the
# 0.09mm absolute minimum. JLCDFM measures mask-aperture-to-mask-
# aperture, subtracting ~0.05mm mask expansion per side, so a
# 0.110mm copper-edge gap becomes ~0.010mm on JLCDFM's view and
# gets flagged as Danger.
python3 scripts/verify_copper_clearance.py         # MUST be "0 DANGER"

# ── Per-net copper connectivity (R5-CRIT class) ─────────────────
# Walks the per-net copper graph and asserts every net forms a
# single connected component. Catches R5-CRIT-1..9 bugs where
# pad-net labels are correct but copper is fragmented (BAT+ L1.1
# isolated, VBUS decoupling floating, button pull-ups disconnected,
# SW_BOOT non-functional, etc). Missing this gate caused R5 bugs
# to ship undetected in v3.3.
python3 scripts/verify_net_connectivity.py         # MUST be "0 failed"

# ── DFM / DFA / JLCPCB manufacturing ─────────────────────────────
python3 scripts/verify_dfm_v2.py                   # 119 tests (incl zone fill + silk-to-pad)
python3 scripts/verify_dfa.py                      #   9 tests
python3 scripts/validate_jlcpcb.py                 #  26 tests
python3 scripts/verify_bom_cpl_pcb.py              #  13 tests (incl field completeness)
python3 scripts/verify_polarity.py                 #  47 tests

# ── JLCPCB official capabilities + stencil + drill ──────────────
python3 scripts/verify_jlcpcb_capabilities.py      #  12 tests (JLCPCB published limits)
python3 scripts/verify_stencil_aperture.py         #   6 tests (IPC-7525 stencil analysis)
python3 scripts/verify_drill_standards.py          #   6 tests (ISO metric + drill-to-pad ratio)

# ── Datasheet pinout + physical verification ─────────────────────
python3 scripts/verify_datasheet_nets.py           # 259 pin→net checks
python3 scripts/verify_datasheet.py                #  29 physical tests

# ── Cross-source consistency (schematic ↔ PCB ↔ firmware) ────────
python3 scripts/verify_design_intent.py            # 362 checks, T1-T22
python3 scripts/verify_schematic_pcb_sync.py       # R4 sync guard
python3 scripts/verify_netlist_diff.py             # schematic-PCB netlist diff
python3 scripts/generate_board_config.py --check   # config.py vs board_config.h

# ── Electrical review (power + boot) ─────────────────────────────
python3 scripts/verify_strapping_pins.py           #  12 tests
python3 scripts/verify_decoupling_adequacy.py      #  25 tests
python3 scripts/verify_power_sequence.py           #  26 tests
python3 scripts/verify_power_paths.py              #  19 tests

# ── KiCad native ERC + DRC ───────────────────────────────────────
python3 scripts/erc_check.py --run                 # schematic ERC
kicad-cli pcb drc \
  --output /tmp/drc_audit_report.json \
  --format json \
  --severity-all --units mm --all-track-errors \
  hardware/kicad/esp32-emu-turbo.kicad_pcb
# DRC: 0 shorting_items (real), 0 via_dangling, 0 unconnected_items
```

Gate summary to report back to the user:

| Gate | Expected | Actual | Status |
|------|----------|--------|--------|
| Fab shorts (`verify_trace_through_pad`) | 0 overlaps | ? | PASS/FAIL |
| Trace crossings (`verify_trace_crossings`) | 0 crossings | ? | PASS/FAIL |
| Copper clearance (`verify_copper_clearance`) | 0 DANGER | ? | PASS/FAIL |
| DFM (`verify_dfm_v2`) | 115/115 | ? | PASS/FAIL |
| DFA (`verify_dfa`) | 9/9 | ? | PASS/FAIL |
| Polarity (`verify_polarity`) | 47/47 | ? | PASS/FAIL |
| Datasheet nets (`verify_datasheet_nets`) | 259/259 | ? | PASS/FAIL |
| Datasheet physical (`verify_datasheet`) | 29/29 | ? | PASS/FAIL |
| Design intent (`verify_design_intent`) | 362/362 | ? | PASS/FAIL |
| R4 sync guard (`verify_schematic_pcb_sync`) | PASS | ? | PASS/FAIL |
| Netlist diff (`verify_netlist_diff`) | 4/4 | ? | PASS/FAIL |
| Strapping pins (`verify_strapping_pins`) | 12/12 | ? | PASS/FAIL |
| Decoupling adequacy (`verify_decoupling_adequacy`) | 25/25 | ? | PASS/FAIL |
| Power sequence (`verify_power_sequence`) | 26/26 | ? | PASS/FAIL |
| Power paths (`verify_power_paths`) | 19/19 | ? | PASS/FAIL |
| ERC (`erc_check`) | 0 critical | ? | PASS/FAIL |
| KiCad DRC | 0 shorts, 0 dangling | ? | PASS/FAIL |

**RULE**: If any gate fails, stop and write the failure into
`hardware-audit-bugs.md` as the first bug of the new round. Do not
proceed to Layer 2 prose review until Layer 1 is clean OR the user
explicitly asks for a prose-only review acknowledging the gate failure.

## Step 1 — Power chain audit (manual)

Trace: USB-C → IP5306 → +5V → AMS1117 → +3.3V → ESP32

Read and cross-check:
- `scripts/generate_schematics/sheets/power.py` — schematic
- `scripts/generate_pcb/routing.py` — PCB routing (`_power_traces`)
- `hardware/datasheet_specs.py` — IP5306, AMS1117 pinouts
- `hardware/datasheets/U2_IP5306_*.pdf` + `U3_AMS1117_*.pdf`
- `software/main/board_config.h` — power management notes

Check:
- L1 inductor placement and LX trace width (≥ 0.76 mm for 2.1 A boost)
- VBAT sense resistor divider (if present)
- Every bypass cap has short path to its pin pair
- EN RC delay on ESP32 (R3 + C3 → τ ≥ 1 ms)
- Bulk caps (C19, C2) on correct rail side of regulators
- IP5306 KEY pin (enables boost mode)
- Thermal relief on regulator pads vs direct connection to inner plane

## Step 2 — ESP32 boot audit (manual)

Check strapping pins at boot time:
- GPIO0  (BTN_SELECT) — download mode when LOW at reset
- GPIO45 (BTN_L) — VDD_SPI selector: LOW = 3.3 V (PSRAM), HIGH = 1.8 V
- GPIO46 — download print disable
- GPIO3  — JTAG source select

Must verify R14 (BTN_L pull-up) is **skipped** in routing, because
external pull-up on GPIO45 forces VDD_SPI = 1.8 V and kills the Octal
PSRAM. Firmware enables internal pull-up post-boot. This is checked
automatically by `verify_strapping_pins.py` but the prose audit should
re-read the commit `9709bea` and confirm the logic still makes sense.

Also verify:
- Flash and PSRAM supply is +3V3 (not +1V8)
- `sdkconfig` PSRAM mode is Octal (not Quad)
- `CONFIG_SPIRAM_MODE_OCT=y`

## Step 3 — Display audit (manual)

Target: ILI9488 3.95" 320x480 8-bit 8080 parallel via 40P FPC.

**CRITICAL reading**: `hardware/datasheet_specs.py::COMPONENT_SPECS['J4']`
now documents the connector-pad ↔ panel-pin reversal
(`connector_pad = 41 - panel_pin`). R4-CRIT-1 was a false positive
against this reversal; do not re-raise it.

Cross-check:
- `scripts/generate_schematics/sheets/display.py` (docstring uses panel-side)
- `hardware/datasheet_specs.py::J4` (PCB uses connector-side)
- `scripts/generate_pcb/routing.py::_lcd_traces` (B.Cu routing)
- `hardware/datasheets/U1_ESP32-S3-WROOM-1_*.pdf` (GPIO → LCD pins)

Check:
- LCD_D0-D7 length skew ≤ 20 mm (acceptable for 20 MHz 8080)
- LCD_WR / LCD_RD / LCD_DC / LCD_CS all on GPIO capable of 40+ MHz
- Backlight (LED_A/LCD_BL) current path and any PWM series resistor
- FPC connector orientation vs enclosure cable routing

## Step 4 — Audio audit (manual)

Target: ESP32 I2S PDM → PAM8403 → 28 mm speaker.

PAM8403 is analog input; firmware must use PDM TX mode (not standard
I2S) so the ESP32 outputs a 1-bit sigma-delta stream that the cap C21
(PAM_VREF) + PAM8403 internal filter reconstruct into audio.

Check:
- `software/main/audio.c` uses `i2s_pdm_tx_config_t`, not standard I2S
- Only 1 signal line routed (I2S_DOUT), no BCLK/LRCK connected
- PAM_VREF cap (C21) on correct pin (VREF)
- Supply decoupling (C23-C25) close to VDD pins
- Speaker terminals SPK+ / SPK- polarity matches footprint
- Audio ground is coupled to digital ground at a single point near U5
  (`verify_ground_loops.py` warns but does not fail — advisory)

## Step 5 — SD card audit (manual)

Target: TF-01A micro SD slot, SPI 1-bit mode @ 25 MHz.

Check:
- SPI pins (CMD/DAT0/CLK/CS) on SPI-capable GPIO (U6 pads 2,3,5,7)
- DAT1 (pad 8) and DAT2 (pad 9) are unused in SPI mode but MUST NOT
  be shorted to other nets. `verify_trace_through_pad.py` will catch
  any trace physically crossing them.
- Card detect (if wired) uses dedicated GPIO + pull-up
- +3V3 supply has ≥ 1 µF decoupling within 5 mm of U6 VCC
- Level shifting: ESP32-S3 is 3.3 V native → no shifter needed
- NPTH positioning hole size matches datasheet (1.00 mm)

## Step 6 — Button audit (manual)

12 buttons + 1 menu combo diode D1 (BAT54C) + power switch SW_PWR.

Check:
- Each button has pull-up + debounce cap (except BTN_L GPIO45: internal)
- Reset / Boot buttons (SW_RST, SW_BOOT) on EN and GPIO0
- Menu combo (SW13 + D1) → MENU_K net → GPIO with internal pull-up
- No two buttons share a GPIO by accident (`verify_design_intent` T1-T3)
- Shoulder buttons (SW11, SW12) far enough from USB-C / FPC to clear
  the enclosure

## Step 7 — USB audit (manual)

Target: USB-C native (ESP32-S3 built-in FS USB) + CC pull-downs + ESD.

Check:
- USB_D+ / USB_D- differential pair geometry (`verify_usb_impedance.py`)
- ESD: USBLC6-2SC6 TVS (U4) on both data lines BEFORE series resistors
- Series 22 Ω resistors R22/R23 between TVS and ESP32
- CC1/CC2 via 5.1 kΩ pull-downs (R1/R2) for device role advertise
- VBUS on all 3 shield pads (J1.1, J1.5, J1.9)
- GND return path density under diff pair (`verify_usb_return_path.py`)
- USB shield THT tabs drilled 0.6 mm

## Step 8 — Emulator performance audit (manual)

Target: SNES @ 60 fps on ESP32-S3 240 MHz + Octal PSRAM.

Check:
- PSRAM mode is Octal (see Step 2)
- ROM loaded into PSRAM (not flash-XIP)
- Frame buffer in internal DRAM (fastest access)
- I2S PDM TX on DMA (no CPU loop)
- Parallel LCD bus uses LCD Camera peripheral or DMA
- WiFi is disabled during emulation (frees CPU + 3V3 headroom)
- Check `website/docs/software/snes-optimization.md` for current profile

## Report format

Write findings to `hardware-audit-bugs.md` under a new section
`## Round N Findings (YYYY-MM-DD)`. Include:

```markdown
### Step 0 gates
| Gate | Result |
|------|--------|
| verify_trace_through_pad | ... |
| verify_dfm_v2 | ... |
...

### Domain findings
- **Power chain**: N findings
- **ESP32 boot**: N findings
- **Display**: N findings
- **Audio**: N findings
- **SD card**: N findings
- **Buttons**: N findings
- **USB**: N findings
- **Emulator performance**: N findings

### Bug list
#### R{N}-CRIT-{i} — {title}
- **Files**: ...
- **Problem**: ...
- **Root cause**: ...
- **Fix**: ...

#### R{N}-HIGH-{i} — ...
#### R{N}-MED-{i}  — ...
#### R{N}-LOW-{i}  — ...
```

Severity guide:
- **CRIT** — board will not power on, or a component will be destroyed
- **HIGH** — a functional block (display, audio, SD, USB) will not work
- **MED**  — intermittent failure or degraded performance
- **LOW**  — cosmetic, documentation, or not-yet-exercised feature

## Key Files

- `scripts/verify_trace_through_pad.py` — fab-short hard gate
- `scripts/verify_dfm_v2.py` — DFM (115 tests)
- `scripts/verify_datasheet_nets.py` — pin→net (259 checks)
- `scripts/verify_design_intent.py` — cross-source (362 checks)
- `scripts/verify_schematic_pcb_sync.py` — R4 sync guard
- `scripts/verify_strapping_pins.py` — ESP32 boot gate
- `scripts/verify_decoupling_adequacy.py` — per-IC cap check
- `scripts/verify_power_sequence.py` — power chain topology
- `scripts/verify_power_paths.py` — copper path tracing
- `scripts/erc_check.py` — KiCad native ERC
- `scripts/generate_schematics/sheets/` — schematic generator (all sheets)
- `scripts/generate_pcb/routing.py` — PCB trace routing
- `hardware/datasheet_specs.py` — component pin→net single source of truth
- `software/main/board_config.h` — firmware GPIO config
- `hardware/datasheets/` — component datasheets
- `hardware-audit-bugs.md` — output: historical audit findings
