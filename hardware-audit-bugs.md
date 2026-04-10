# Hardware Audit Bug Report

**Date**: 2026-04-09 | **Auditors**: 5x Opus agents (10 iterations)
**Scope**: Power, boot, display, audio, SD, buttons, USB, performance, integration, edge cases

## Previously Fixed (round 1)

| Bug | Severity | Fix Applied |
|-----|----------|-------------|
| ~~C1~~ | CRITICAL | `audio.c`: I2S std → PDM TX mode |
| ~~C2~~ | CRITICAL | `input.c`: BTN_L GPIO_PULLUP_ENABLE |
| ~~H1~~ | HIGH | `mcu.py`: GPIO table corrected (44/43/45/3) |
| ~~H2~~ | HIGH | `display.py`: LCD_RD/BL → "+3V3 tied" |
| ~~M1~~ | MEDIUM | `routing.py`: documented backlight current note |
| ~~M2~~ | MEDIUM | Already had 4+2 thermal vias, updated comment |
| ~~M3~~ | MEDIUM | Antenna keepout passes 5/5 tests |
| ~~M4~~ | MEDIUM | `routing.py`: documented USB shield GND |
| ~~M5~~ | MEDIUM | `sdcard.c`: SD SPI internal pull-ups added |

## Open — LOW (8)

| ID | Domain | Issue |
|----|--------|-------|
| BUG-L1 | power | IP5306 KEY pull-up bootstraps from VOUT (0V at start) — POR handles it |
| BUG-L2 | power | Power switch (SW_PWR) non-functional — only common pin routed |
| BUG-L3 | display | LCD write clock 20MHz > ILI9488 spec 15MHz — common overclock, works in practice |
| BUG-L4 | sd | SD SPI at 40MHz above standard spec — ESP-IDF negotiates down |
| BUG-L5 | buttons | 1ms RC debounce < switch bounce 5-20ms — mitigated by 60fps polling |
| BUG-L6 | buttons | GPIO0/BTN_SELECT → download mode if held at boot — by design, needs user doc |
| BUG-L7 | edge | No battery voltage monitoring (no ADC allocated) |
| BUG-L8 | edge | No SD card detect pin wired — firmware handles via mount failure |

## PASS (verified correct)

- USB-C CC pull-downs (5.1k), IP5306 caps, AMS1117 caps, ESP32 decoupling
- PSRAM pins (GPIO33-37) not used externally, Flash pins not exposed
- All strapping pins correctly handled, EN pin RC circuit
- USB ESD (USBLC6-2SC6), 22ohm series, D+/D- length matched
- GPIO count: 33/45 used, no overlaps
- PAM8403 power/SHDN/decoupling, FPC pin reversal, IM[2:0]=011

---

## Round 2 Findings

### CRITICAL (1)

**R2-CRIT-1**: R14 (10k pull-up on GPIO45/BTN_L) still in BOM/CPL. JLCPCB will assemble it, causing VDD_SPI strapping conflict. Must remove from BOM designator list.

### HIGH (2)

**R2-HIGH-1**: `display.c` uses ST7796S driver but `board_config.h` says ILI9488. Different init commands and pixel format (RGB565 vs RGB666).

**R2-HIGH-2**: AMS1117 output cap C2 BOM is MLCC ceramic (C12891, ESR 0.005 ohm) but AMS1117 requires ESR 0.1-10 ohm (tantalum). Will oscillate.

### MEDIUM (7)

**R2-MED-1**: `display.c` max_transfer_bytes = 300KB DMA SRAM — will starve system. Set to ~25KB.
**R2-MED-2**: No watchdog config for emulation tasks. Add CONFIG_ESP_TASK_WDT_TIMEOUT_S=10.
**R2-MED-3**: No USB-CDC console — debug logs go nowhere. Add CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y.
**R2-MED-4**: PAM8403 decoupling caps 4.8-6.1mm from pins (should be <2mm). Audio quality degraded.
**R2-MED-5**: SD SPI traces 150-186mm with 6 vias at 40MHz. Reduce to 20MHz.
**R2-MED-6**: release_jlcpcb/ out of sync (missing C28, D1). Re-run release pipeline.
**R2-MED-7**: IP5306 BAT cap C18 is 10uF, datasheet recommends 20-47uF.

### LOW (6)

R2-LOW-1: audio.h stale "standard mode" comment
R2-LOW-2: audio_init() leaks channel on partial failure
R2-LOW-3: display_init() leaks bus/IO on partial failure
R2-LOW-4: power_is_charging() true when no charger connected
R2-LOW-5: J3 LCSC mismatch in datasheet_specs.py (C265003 vs C295747)
R2-LOW-6: R16 described as "pull-down" in 3 files, actually pull-up

## Round 3 Findings

### CRITICAL (1) — FIXED
**R3-CRIT-1**: idf_component.yml declared esp_lcd_st7796 but code uses esp_lcd_ili9488 → build fail. **Fixed**: changed to esp_lcd_ili9488.

### FIXED (firmware)
- Stack size 3584→8192 (CONFIG_ESP_MAIN_TASK_STACK_SIZE)
- Removed unused esp_driver_ledc from CMakeLists.txt
- Stale ST7796S comments in display.h, main.c

### v2 HARDWARE IMPROVEMENTS (require PCB respin)
| Bug | Severity | Issue | v2 Fix |
|-----|----------|-------|--------|
| R3-HIGH-1 | HIGH | 6 MH on PCB vs 4 in enclosure | Remove center 2 (needs routing rework) |
| R3-HIGH-2 | HIGH | C28 under ESP32 module body | Move to x=68 (needs via reroute) |
| R3-HIGH-3 | HIGH | PAM8403 OUTL floating, INL driven | Disconnect INL from I2S_DOUT |
| R3-HIGH-4 | HIGH | No VBUS PTC fuse | Add MF-PSMF050X on VBUS |
| R3-MED-1 | MEDIUM | No battery reverse polarity protection | Add P-MOSFET on BAT+ |
| R3-MED-2 | MEDIUM | PDM no LP reconstruction filter | Add 1k+10nF RC before PAM8403 |
| R3-MED-3 | MEDIUM | JST PH missing anchor pads | Add 2 mechanical pads |
| R3-MED-4 | MEDIUM | IP5306 thermal vias outside EP pad | Move inside pad boundary |
| R3-MED-5 | MEDIUM | USB-C 0.15mm pads mask_margin=0 | Set margin to 0.05mm |
| R3-MED-6 | MEDIUM | FPC anchor pads floating | Tie to GND |

## Round 4 Findings (2026-04-10)

**Auditors**: 3 parallel Opus agents + manual cross-check
**Scope**: Re-audit all 8 domains, find bugs R1–R3 missed

### CRITICAL (1)

**R4-CRIT-1** — Display FPC J4 pinout mismatch between schematic and PCB
- **Files**: `hardware/datasheet_specs.py:271-320` (PCB net assignments) vs `scripts/generate_schematics/sheets/display.py:3-23` (schematic comments)
- **Problem**: Two different ILI9488 40P FPC pinouts. Schematic documents one panel variant; PCB is routed for another:
  | Pin | datasheet_specs.py (PCB)  | display.py (schematic) |
  |-----|----------------------------|------------------------|
  | 6-7 | GND                        | VDDI / VDDA (+3V3)     |
  | 9   | NC (touch)                 | LCD_CS                 |
  | 10  | NC (touch)                 | LCD_DC                 |
  | 11  | NC (touch)                 | LCD_WR                 |
  | 15  | NC (IM0)                   | LCD_RST                |
  | 17-24 | LCD_D7..D0 (reversed)    | LCD_D0..D7             |
  | 26  | LCD_RST                    | NC                     |
  | 29-32 | LCD_RD/WR/DC/CS          | NC (DB12-15)           |
  | 33  | NC (TE)                    | LED_A                  |
  | 34-35 | +3V3 VCC                 | LED_K (GND)            |
  | 38-40 | NC                       | IM0/IM1/IM2 straps     |
- **Impact**: Display will NOT function — data bus bit order is reversed (D7↔D0) and control signals are on wrong pins. Either the schematic or the PCB is wrong; they cannot both be correct.
- **Fix**: Identify the actual AliExpress panel part ordered, align both files to its datasheet. Most likely datasheet_specs.py is correct (since PCB follows it) — update display.py and re-verify IM mode strapping (datasheet_specs has pins 38-40 NC; if the panel requires external IM straps, PCB is also missing them).

### HIGH (3)

**R4-HIGH-1** — USB ESD protection invisible in schematic
- **Files**: `scripts/generate_pcb/routing.py:394-401,556-558,2480-2673` (has U4/R22/R23) vs `scripts/generate_schematics/sheets/power_supply.py:39-43` (has only USB_D+/USB_D- glabels)
- **Problem**: USBLC6-2SC6 (U4) ESD TVS and R22/R23 (22Ω series) exist only in the PCB Python generator. No schematic sheet instantiates them. A reviewer reading the schematics cannot verify the USB protection circuit.
- **Fix**: Add U4 (USBLC6-2SC6) + R22/R23 symbols to `power_supply.py` between USB-C D+/D- pins and `USB_DP_MCU`/`USB_DM_MCU` nets. Include TVS VBUS reference.

**R4-HIGH-2** — Designator collision on "U4"
- **Files**: `display.py:45` (schematic uses "U4" for ILI9488 module symbol) vs `routing.py:556`, `jlcpcb_export.py:243`, `bom.csv:26` (PCB/BOM use "U4" for USBLC6)
- **Problem**: Same reference designator assigned to two different components. Cross-probe schematic↔PCB will produce wrong matches; human review is confusing.
- **Fix**: Rename the display module symbol in `display.py` to a non-conflicting ref (e.g., `DS1` or keep the physical `J4` as the real reference — the "ST7796S_Module" symbol at line 45 is a logical-only aid, so rename it to `MOD1` or drop the component and keep only the FPC J4 symbol).

**R4-HIGH-3** — PAM8403 input bias tied to GND instead of VREF
- **File**: `scripts/generate_schematics/sheets/audio.py:81-95`
- **Problem**: R20/R21 (20k bias resistors on INL/INR input nodes) bottom pads are tied to GND. Per PAM8403 datasheet single-ended application circuit, the bias network must reference the VREF pin (pin 8, VDD/2) so that the input node's DC operating point matches the internal comparator mid-rail. Tying to GND fights the internal bias and causes DC offset through the 0.47µF coupling cap, producing asymmetric clipping or reduced output.
- **Fix**: Change R20/R21 GND terminations to connect to a VREF node which is tied to PAM8403 pin 8 with C21 (100nF) bypass already in place. Route: `self.wire(r20x, r20y + 3.81, r20x, <vref_node_y>)` instead of `self.gnd(...)`. Verify against `U5_PAM8403_C5122557.pdf` Fig. 3.

### MEDIUM (2)

**R4-MED-1** — SD card VCC bypass cap missing from schematic sheet
- **File**: `scripts/generate_schematics/sheets/sd_card.py` (no cap placed)
- **Problem**: No 100nF + 10µF decoupling cap placed near U6 (TF-01A) VCC pin. SD cards draw large inrush currents (up to 100mA transients) during initialization and data transfers, requiring local bypass within ~5mm of the VCC pin.
- **Fix**: Add `self.sym("C", "C_SD1", "100nF", ...)` and a 10µF bulk cap between U6 VCC and GND in `sd_card.py`. Allocate new designators (e.g., C29/C30) and include in BOM. Also verify PCB `routing.py` places caps physically close to U6.

**R4-MED-2** — C19 (22uF 1206 MLCC) voltage rating not documented for 5V rail
- **Files**: `hardware/kicad/jlcpcb/bom.csv:21`, `scripts/generate_schematics/sheets/power_supply.py:149-151`
- **Problem**: C19 (LCSC C12891) sits on IP5306 VOUT rail which can reach 5.1V under load transients. MLCC dielectric derating can halve effective capacitance near rated voltage. BOM does not specify rated voltage.
- **Fix**: Confirm C12891 is ≥10V rated (add note in BOM comments). Prefer 25V rating for 5V rail longevity. Note: R2-HIGH-2 claim that *C2* was ceramic is wrong — verified C2 is tantalum C7171 (`bom.csv:22`). Close R2-HIGH-2 as false positive.

### Status Updates (from R2/R3)

- **R2-CRIT-1 (R14 DNP)**: ✅ FIXED — excluded in `jlcpcb_export.py:268`
- **R2-HIGH-1 (display driver)**: ✅ FIXED — `display.c` + `idf_component.yml` both use `esp_lcd_ili9488`
- **R2-HIGH-2 (AMS1117 cap ESR)**: ❌ FALSE POSITIVE — C2 is actually tantalum C7171. C19 (MLCC) is on IP5306 5V rail, not AMS1117 output. Close.
- **R2-MED-1 (display max_transfer_bytes)**: ✅ FIXED — now 25KB in `display.c:54`
- **R2-MED-2 (watchdog)**: ✅ FIXED — `CONFIG_ESP_TASK_WDT_TIMEOUT_S=10` in `sdkconfig.defaults`
- **R2-MED-3 (USB-CDC console)**: ✅ FIXED — `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`

### Round 4 Fix Status (applied 2026-04-10)

- **R4-CRIT-1 (FPC pinout mismatch)**: ❌ **FALSE POSITIVE — closed**. The apparent disagreement between `display.py` (panel-side numbering) and `hardware/datasheet_specs.py` (connector-side J4 pad numbering) is explained by the **landscape FPC pin reversal**: the ribbon passes straight through the PCB slot so `connector_pad = 41 − panel_pin`. Verified programmatically — all 40 J4 pads match the panel datasheet after the 41-N transform. Both files are correct; they describe the same electrical design from two perspectives. The panel datasheet (`website/docs/design/components.md` §"FPC 40-Pin Pinout", referencing the AliExpress ILI9488 3.95" bare panel) is the canonical source. Documented the reversal at the top of `display.py` AND in `datasheet_specs.py` J4 comment so future audits can't repeat the mistake.
- **R4-HIGH-1 (USB ESD missing from schematic)**: ✅ FIXED — `power_supply.py` now instantiates U4 (USBLC6-2SC6) + R22/R23 (22Ω series) with proper wiring to USB_D+/-, USB_DP_MCU/USB_DM_MCU, GND, +5V.
- **R4-HIGH-2 (U4 designator collision)**: ✅ FIXED — `display.py` renamed the logical ILI9488 module symbol from `U4` to `DS1`; `U4` is reserved for the physical USBLC6-2SC6 TVS.
- **R4-HIGH-3 (PAM8403 bias to GND)**: ✅ FIXED — `audio.py` R20/R21 bottom terminals now tie to a named `VREF` node (PAM8403 pin 8) instead of GND. Matches datasheet single-ended application circuit.
- **R4-MED-1 (SD VCC decoupling)**: ⏸ DEFERRED to v2 respin — schematic sheet annotated with a v2 TODO note. Current PCB decoupling is shared from the ESP32 rail through C26 (marginal but functional).
- **R4-MED-2 (C19 voltage rating)**: ⏸ DEFERRED — requires BOM comment annotation; track with v2.

### Additional fixes after the false-positive closure

- **ERC CRITICAL "Power output ↔ Power output" (pre-existing)**: ✅ FIXED. The `PWR_FLAG` on the +5V rail in `power_supply.py` was a second `power_out` pin on a net already driven by `IP5306 VOUT` (also `power_out` in the library symbol). Removed the `PWR_FLAG`; IP5306 VOUT alone satisfies KiCad's "power input must be driven" requirement. ERC now reports 0 critical.
- **`verify_bom_cpl_pcb.py` C28/R14 FAIL**: ✅ FIXED. Replaced the hand-written `HAND_ASSEMBLED` list with an auto-discovery that imports `scripts/generate_pcb/jlcpcb_export._build_placements` and computes DNP = PCB footprints − CPL refs − hand-assembled. Single source of truth; adding a new DNP in the CPL builder now auto-updates the check. Fail-loud on import errors (never silenced).
- **`verify_component_connectivity.py` C28 FAIL**: ✅ FIXED (same auto-discovery applied there).
- **`verify_schematic_pcb_sync.py` string-parser bug**: ✅ FIXED. The hand-rolled regex was swallowing spans of code whenever an apostrophe appeared in a comment (`connector's`), masking real net references. Replaced with a `tokenize`-based parser that correctly handles triple-quoted strings, f-strings, escapes, and apostrophes. Docstrings are excluded (they're free text, not wiring).

### New guardrail (R4 regression protection)

`scripts/verify_schematic_pcb_sync.py` now enforces:
1. Every BOM ref has a schematic symbol (or explicit allowlist).
2. No designator may be reused across schematic/PCB for different component families.
3. Every connector in `datasheet_specs.py` has its expected net set referenced in its schematic sheet.

Hooked into `.claude/skills/pcb-review/SKILL.md` step 1m2 — must PASS before any PCB release. Will catch the R4 class of bugs before they reach manufacturing.

Incidental cleanups driven by the sync check:
- `mcu.py`: R3 (legacy external EN pull-up) removed from the schematic — it was already DNP in the BOM because WROOM-1 has an internal pull-up. Documentation now matches the CPL.
- `controls.py`: D1 (BAT54C dual-Schottky menu-combo diode) added to the schematic to match the PCB routing; previous MENU button wiring simplified to use the MENU_K node name.
- `power_supply.py`: explicit `USB_CC1` / `USB_CC2` global labels added so the connector-net coverage check can see the full USB-C pinout.
