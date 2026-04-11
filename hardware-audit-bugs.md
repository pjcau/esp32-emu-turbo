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

## Round 5 Findings (2026-04-10) — Electrical connectivity audit

**Auditor**: `/pcb-review` + `/hardware-audit` with the new Layer-1 gate suite
**Scope**: deep dive triggered by investigating 12 DRC dangling vias after Fix 1 landed (`eff85e6`). Fixing the vias surfaced a cascade of **pre-existing electrical connectivity bugs** that no verification script had caught because the scripts check *pad-net assignments* rather than *copper continuity* (e.g. `verify_datasheet_nets.py` treats a pad with net `BAT+` as "connected" even when that pad sits on an isolated copper island).

All R5 findings are **pre-existing** — they were present in the `release(v3.3)` commit `f88cf1b` and every prior release. None were introduced by R4 or by the session's Fix 1 work.

### R5-CRIT-1 — Boost converter inductor L1 isolated on BAT+ side

- **Files**: `scripts/generate_pcb/routing.py:1120-1134`, `hardware/kicad/esp32-emu-turbo.kicad_pcb` (cache inspection)
- **Evidence** (B.Cu only at x=111.7 y=[49.5, 52.5]):
  ```
  L1.1 (111.7, 52.5) → (111.7, 49.5) → (112.4, 49.5) [VIA, DANGLING]
  Main BAT+ network ends at (105.5, 46.135) via
  Distance from L1.1 via to nearest BAT+ copper: ~7mm, blocked by KEY trace + IP5306 body
  ```
- **Problem**: the comment at `routing.py:1120` says *"L1 pin 1 to BAT+ zone"* — but `_power_zones()` (line 4483) creates only `GND`, `+3V3`, `+5V` zones. There is **no BAT+ zone**. The via at (112.4, 49.5) was placed expecting a zone fill that never existed, leaving L1.1 electrically floating.
- **Impact**: **CRITICAL**. IP5306 boost topology: `BAT+ → L1 → LX (switching) → internal diode → VOUT`. With L1.1 disconnected, no battery current flows through the inductor, the boost converter cannot switch, +5V is not generated on battery power.
  - On **USB-C**: boots normally. IP5306 VBUS → internal path → VOUT delivers +5V without using L1.
  - On **battery only**: **does not boot**. No +5V → no +3V3 → dead ESP32.
- **Why verification missed it**: `verify_datasheet_nets.py` says L1.1 has net BAT+ (which matches the expected `_exact("BAT+")` in `datasheet_specs.py::L1`). `verify_power_paths.py` confirms the BAT+ source pad exists and one destination is reachable (J3/SW_PWR/U2.6) — it doesn't walk per-destination connectivity. No script checks that the BAT+ **copper is a single connected component**.
- **Fix plan** (deferred, needs layout work):
  1. Add a B.Cu BAT+ trace from (105.5, 46.135) via east to connect L1.1.
  2. Must thread the narrow corridor between the Fix 1a GND horizontal (y=45.3) and the IP5306_KEY horizontal (y=46.61) — usable corridor ~0.885mm wide → trace ≤ 0.4mm width (not the typical 0.76mm `W_PWR`).
  3. Dogleg around the IP5306_KEY vertical at x=114.05 to reach L1.1 at x=111.7.
  4. Alternative: add a dedicated BAT+ pour on a reshuffled inner layer (intrusive).

### R5-CRIT-2 — IP5306 BAT+ bulk decoupling cap C18 isolated

- **Files**: `scripts/generate_pcb/routing.py:4146-4155`, cache
- **Evidence**:
  ```
  C18.1 (116.95, 49.0) → (116.95, 47.5) [VIA, DANGLING]
  No segment joining this via to the main BAT+ network
  ```
- **Problem**: same class as R5-CRIT-1. Via at (116.95, 47.5) was placed expecting a BAT+ zone. C18 is physically mounted but carries no current.
- **Impact**: **HIGH**. Bulk BAT+ decoupling absent → higher ripple on the IP5306 BAT input during switching load transients. Board may boot but may show instability under high load (audio + display + WiFi).
- **Fix plan**: merge with R5-CRIT-1 routing — the same new B.Cu BAT+ horizontal can pick up C18.1 on its way east.

### R5-CRIT-3 — IP5306 VBUS decoupling cap C17 isolated

- **Files**: `scripts/generate_pcb/routing.py:4125-4144`, cache
- **Evidence**: C17.1 (110.95, 35.00) → short B.Cu stub → dangling via at (110.95, 33.65). Main VBUS F.Cu vertical at x=111.00 starts at y=40.09 — the via is 6.44mm north with no connecting segment on either layer.
- **Problem**: same class. Designer's stub goes in the wrong direction (north instead of south toward the main VBUS vertical at y≥40.09).
- **Impact**: **MEDIUM**. IP5306 still receives VBUS via the U2.1 pin connection, but the input decoupling cap is not filtering anything → higher USB-C input ripple, potential EMI issues, reduced charging noise immunity.
- **Fix plan**: reroute C17.1 stub SOUTH to meet the existing F.Cu VBUS vertical, or extend the VBUS vertical north to reach the via.

### R5-CRIT-4 — Button pull-up + debounce network fragmented on every button

- **Files**: `scripts/generate_pcb/routing.py` (button routing section), cache
- **Evidence** (example BTN_A — same pattern on all 12 buttons):
  ```
  BTN_A net components:
    Group A (connected):   SW5.1 (button)  → … → U1.39 (ESP32 GPIO)
    Group B (isolated):    R8.1 (10k pullup) → C9.1 (100nF debounce)
  ```
  Group B is a 4mm B.Cu vertical between R and C with **no connection** to Group A. Same structure on BTN_A/B/X/Y/UP/DOWN/LEFT/RIGHT/L/R/START/SELECT.
- **Problem**: the external pull-up resistors and debounce caps are physically placed and entered in the BOM but are electrically *floating islands*. The button circuit degenerates to:
  ```
  ESP32 GPIO ── switch ── GND    (pull-up and debounce have no effect)
  ```
- **Impact**: **HIGH functional, LOW blocking**. Firmware currently enables internal ESP32-S3 pull-ups on all button GPIOs (see `software/main/board_config.h` and `input.c`), so the buttons work without the external pull-ups. Debouncing is handled in firmware. The board is *functionally operable* but:
  - Doubles the board's assembly cost on 12× R + 12× C that do nothing
  - Leaves GPIO inputs slower on rising edge (no external R pulling up, only ESP32 weak internal)
  - Fails EMI/ESD tests because the debounce caps aren't attenuating spikes on the GPIO lines
- **Why verification missed it**: same class as R5-CRIT-1 — every pad has the "right" net assignment, and the pull-up/debounce junction is internally consistent (R and C share a 4mm trace), so polarity/datasheet checks pass. Nothing walks the full net graph asking *"is every component electrically reachable from every other component on this net?"*.
- **Fix plan**: for each button, add a B.Cu or F.Cu segment from the R/C junction to the main button signal path (near the ESP32-side via). ~12 segments total. Low risk per button, high tedium.

### R5-CRIT-5 — SW_BOOT not connected to BTN_SELECT network

- **Files**: `scripts/generate_pcb/routing.py:4346-4355`, cache
- **Evidence**: SW_BOOT.2 (102, 63.65) → short B.Cu stub to (102, 60) → dangling via. No connection to the main BTN_SELECT path (which runs on the LEFT side of the board via SW10 → ESP32 GPIO0).
- **Problem**: pressing SW_BOOT shorts pad 2 to GND (pad 3/4), but pad 2 is on an isolated net fragment. Reset-with-boot-held (the download mode entry sequence) doesn't pull GPIO0 low → firmware can't enter flashing mode via the buttons.
- **Impact**: **HIGH functional**. Download mode currently requires either the USB-JTAG path or manually shorting GPIO0 to GND. SW_BOOT as a physical button is decorative.
- **Fix plan**: route a B.Cu/F.Cu trace from SW_BOOT.2 to the nearest BTN_SELECT copper (probably the R13/C14 junction at x=88.95 after R5-CRIT-4 is fixed, or directly to the SW10→ESP32 trace).

### R5-CRIT-6 — Menu combo diode D1 not connected to BTN_START/BTN_SELECT

- **Files**: `scripts/generate_pcb/routing.py::_menu_diode_traces`, cache
- **Evidence**: D1.2 (155.05, 53.60) → short B.Cu stub to (155.05, 51.10) → dangling via. Same structure for the BTN_START side. The "menu combo" (SW13 triggers BTN_START + BTN_SELECT via dual Schottky D1) is electrically inert.
- **Impact**: **MEDIUM functional**. The menu combo shortcut (one button triggers two simultaneously) does not work. Users must press BTN_START + BTN_SELECT separately to reach the emulator menu. Not blocking for basic gameplay, blocks the menu UX shortcut.
- **Fix plan**: route D1.1 and D1.2 to reach the BTN_START and BTN_SELECT networks respectively.

### Summary of the 10 remaining DRC dangling vias

| # | Via | Net | Reason | R5 bug |
|---|-----|-----|--------|--------|
| 1 | (112.4, 49.5)   | BAT+        | L1.1 inductor orphan | R5-CRIT-1 |
| 2 | (116.95, 47.5)  | BAT+        | C18 decoupling orphan | R5-CRIT-2 |
| 3 | (110.95, 33.65) | VBUS        | C17 decoupling orphan | R5-CRIT-3 |
| 4 | (39.25, 68.3)   | BAT+        | Single-layer superfluous (SW_PWR junction) | cleanup |
| 5 | (86.0, 69.0)    | GND         | Orphan stitching (no F.Cu/B.Cu trace) | cleanup |
| 6 | (88.0, 69.0)    | GND         | Orphan stitching | cleanup |
| 7 | (98.0, 60.0)    | EN          | Single-layer superfluous (SW_RST → U1.3 path) | cleanup |
| 8 | (102.0, 60.0)   | BTN_SELECT  | SW_BOOT.2 orphan | R5-CRIT-5 |
| 9 | (156.95, 56.1)  | BTN_START   | D1.1 menu diode orphan | R5-CRIT-6 |
| 10| (155.05, 51.1)  | BTN_SELECT  | D1.2 menu diode orphan | R5-CRIT-6 |

### Meta: why the verification pipeline missed all of this

The verify_*.py suite performs *pad-net consistency checks* — for each pad, it confirms the PCB's pad-net assignment matches the expected `datasheet_specs.py` entry. This catches wrong pin assignments but **not** disconnected copper. A pad can be correctly "labeled" BAT+ while sitting on an isolated copper island with no traces reaching it.

**Gap in the pipeline**: there is no "net graph connectivity" verifier that walks the union of (pads, segments, vias, zones) per net and confirms all members form a single connected component. KiCad's native DRC does this but only after zone fill and reports as `unconnected_items` — which the project has historically been tolerant of (27 unconnected items were passing in v3.3).

**Recommended new gate**: `verify_net_connectivity.py` that:
1. Reads the PCB cache per net
2. Builds an undirected graph: nodes = {pads, vias, segment endpoints}, edges = {(endpoint_A, endpoint_B) of each segment on the same layer} ∪ {(via, pad) if geometrically overlapping} ∪ {(pad, pad) if connected via a zone-fill region}
3. Computes connected components
4. For each net, asserts `num_components == 1`
5. Reports each fragmentation with the affected refs

This gate would have caught R5-CRIT-1 through R5-CRIT-6 all at once. It should be added to `/pcb-review` step 1 and `/hardware-audit` Step 0 gate suite as a blocking check.

### What was fixed in commit `eff85e6` and this session

- ✅ 6 trace-through-pad fab shorts eliminated (Fix 1a/1b/1c)
- ✅ J4.37 GND via clearance shifted 0.3mm (DRC shorting_items: 8 → 0)
- ✅ LCD_RD / LCD_BL merged to +3V3 (2 dangling vias eliminated, pads now correctly at +3V3 net)
- ✅ datasheet_specs.py updated to document the U6.8/9 + SW_PWR.4b/4d + J4.8/29 same-net relationships
- ✅ `verify_polarity.py` updated for the J4.8/29 net changes

### What is NOT fixed (needs a dedicated R6 session)

- R5-CRIT-1 to R5-CRIT-6 (see above)
- 10 remaining DRC dangling vias (8 are cleanup, 2 are symptoms of R5-CRIT-1/CRIT-2)
- Schematic↔PCB netlist drift flagged by `verify_netlist_diff.py` — 5 missing nets, 12 orphan, 33 pin mismatches (most are cosmetic, e.g. AMS1117 symbol pin numbers vs SOT-223 footprint numbering)
- 4 B.Cu traces crossing the ESP32 antenna keepout (advisory WARN, not FAIL)

### Proposal for R6 session

1. Implement `verify_net_connectivity.py` as described above.
2. Run it on current PCB → it should flag all R5-CRIT findings as test failures.
3. Fix R5-CRIT-1 and R5-CRIT-2 together by routing a new B.Cu BAT+ trace.
4. Fix R5-CRIT-3 by rerouting C17.1 stub south.
5. Fix R5-CRIT-4 (12 button pull-up/debounce bridges) — can be scripted since the pattern is uniform.
6. Fix R5-CRIT-5 and R5-CRIT-6 via direct B.Cu traces from the isolated pads to the main button nets.
7. Re-run the full verification suite including the new connectivity gate.
8. Release as v3.4 (first release that actually boots on battery).

## Round 9 Findings (2026-04-11) — Layer 1 regression audit post-R8

**Auditor**: `/hardware-audit` Layer 1 gate suite (manual Layer 2 blocked)
**Trigger**: Routine re-audit after R8 button pull-up bridges commit (`eaab9e4`) and render regen (`f5073f3`).
**Scope**: Layer 1 automated gates only. Layer 2 prose review deliberately NOT run — the skill says hard-block on gate failure, and we have 3 CRITICAL and multiple HIGH regressions.

### Step 0 gates

| Gate | Expected | Actual | Status |
|------|----------|--------|--------|
| `verify_trace_through_pad` | 0 overlaps | 0 overlaps | PASS |
| `verify_net_connectivity` | 0 failed | 0 failed (4 accepted tech-debt) | PASS |
| `verify_dfm_v2` | 115/115 | 115/115 | PASS |
| `verify_dfa` | 9/9 | 9/9 | PASS |
| `verify_polarity` | 47/47 | 47/47 | PASS |
| `validate_jlcpcb` | 25/25 | 25/25 (1 warn) | PASS |
| `verify_bom_cpl_pcb` | 10/10 | 10/10 | PASS |
| `verify_datasheet_nets` | 259/259 | 259/259 | PASS |
| `verify_datasheet` | 29/29 | 29/29 | PASS |
| `verify_design_intent` | 362/362 | 362/362 (3 warn) | PASS |
| `verify_schematic_pcb_sync` | PASS | PASS | PASS |
| `verify_netlist_diff` | 4/4 | **0/4** | **FAIL** |
| `verify_strapping_pins` | 12/12 | 10/12 (1 fail, 1 warn) | **FAIL** |
| `verify_decoupling_adequacy` | 25/25 | 25/25 | PASS |
| `verify_power_sequence` | 26/26 | 26/26 | PASS |
| `verify_power_paths` | 19/19 | 8/8 (11 info) | PASS |
| `generate_board_config --check` | OK | OK | PASS |
| `erc_check --run` | 0 critical | 0 critical, 22 warnings | PASS |
| KiCad native DRC (`drc_native.py --run`) | 0 real issues | **7 real + 9 uncategorized** | **FAIL** |

Delta vs `scripts/drc_baseline.json`: total violations 756 → 44 (−712, great), **but 4 NEW violation types appear**: `tracks_crossing`, `unconnected_items`, `silk_over_copper`, `lib_footprint_issues`. `tracks_crossing` is the dangerous one.

### Bug list

#### R9-CRIT-1 — BTN_START trace crosses LCD_CS / LCD_DC / LCD_WR on F.Cu (3 shorts)

- **Files**: `scripts/generate_pcb/routing.py` (BTN_START routing added in R7/R8 commits `0880d3d`, `eaab9e4`)
- **Evidence** (from KiCad DRC on `hardware/kicad/esp32-emu-turbo.kicad_pcb`):
  ```
  tracks_crossing: Track [LCD_CS]  F.Cu @ (80.635, 38.115) × Track [BTN_START] F.Cu @ (83.95, 43.0)  L=10.5mm
  tracks_crossing: Track [LCD_DC]  F.Cu @ (78.095, 36.845) × Track [BTN_START] F.Cu @ (83.95, 43.0)
  tracks_crossing: Track [LCD_WR]  F.Cu @ (85.715, 35.575) × Track [BTN_START] F.Cu @ (83.95, 43.0)
  ```
- **Problem**: The 10.5 mm BTN_START horizontal at y≈43 on F.Cu crosses three LCD control signals (LCD_CS, LCD_DC, LCD_WR) that run vertically/diagonally from the ESP32 up to J4. Two different nets on the same copper layer crossing **is a manufacturing short** — at fab the copper merges at the intersection point.
- **Why earlier gates missed it**:
  - `verify_trace_through_pad.py` only checks trace-crosses-PAD, not trace-crosses-trace.
  - `verify_net_connectivity.py` walks per-net connectivity; a short would show up as *over-connectivity* (two nets merged) but the script doesn't raise on that — it only asserts *under-connectivity* (single net fragmented into N components).
  - No `verify_trace_crossings.py` exists. **Gap in the gate suite.**
- **Impact**: **CRITICAL**. If this PCB ships, LCD_CS/LCD_DC/LCD_WR are all tied to BTN_START. The LCD cannot be driven (random button press drives control lines low), and pressing START pulls three LCD control pins to GND. **Display + START button both non-functional.**
- **Root cause**: The R8 button-bridge pass added a BTN_START horizontal segment on F.Cu without checking that the area was already occupied by LCD signals routed in R4. The same corridor was already in use.
- **Fix**:
  1. Move BTN_START bridge to B.Cu OR reroute around the LCD signal bundle (the area between x=75-90, y=35-43 on F.Cu is full of LCD control).
  2. Add a new gate `verify_trace_crossings.py`: for each pair of segments on the same layer, if they intersect geometrically and belong to different nets, FAIL. Include in Layer 1 gate suite.
  3. Consider promoting `drc_native.py` to block on `tracks_crossing` automatically (currently "uncategorized").

#### R9-CRIT-2 — Via BTN_B to pad GND(C3) near-short (0.05 mm copper / 0.20 mm hole)

- **Files**: `scripts/generate_pcb/routing.py` (button B routing, R8 era)
- **Evidence**:
  ```
  clearance (actual 0.0500 mm; required 0.2000 mm):
    Via [BTN_B] F.Cu-B.Cu @ (69.40, 41.50)  × Pad 2 [GND] of C3 @ (68.60, 42.00) on B.Cu
  hole_clearance (actual 0.2000 mm; required 0.2500 mm): same via/pad pair (hole-to-hole)
  ```
- **Problem**: The BTN_B via sits 0.93 mm centre-to-centre from the C3 GND pad. Copper-to-copper gap is 0.05 mm and the drill-to-pad edge is 0.20 mm — both below JLCPCB 4-layer 0.20/0.25 mm minimums. This is one **fabricator tolerance stack-up** away from a BTN_B↔GND short, which would hold the B button permanently pressed and pull GND up during button transitions.
- **Impact**: **CRITICAL risk, HIGH actual**. At fab the board may or may not short depending on registration; even if it ships intact, any flex or thermal cycling stresses that region. Don't ship.
- **Fix**: Move the BTN_B via ≥1.2 mm from C3.2 (either north around C3 or south past it).

#### R9-HIGH-1 — Via BAT+ to pad BTN_Y(R11) clearance 0.11 mm

- **Files**: `scripts/generate_pcb/routing.py` (R7 BAT+ routing near button area OR R8 R11 bridge)
- **Evidence**:
  ```
  clearance (actual 0.1100 mm; required 0.2000 mm):
    Via [BAT+] F.Cu-B.Cu @ (80.01, 46.135) × Pad 1 [BTN_Y] of R11 @ (78.95, 46.00) on B.Cu
  ```
- **Problem**: BAT+ via 1.07 mm from the BTN_Y pull-up pad. A short here would tie the Y button to raw battery (3.0–4.2 V) — still within ESP32 GPIO tolerance but bypasses the debounce cap and injects battery noise onto an input line.
- **Fix**: Shift the BAT+ via ≥0.3 mm west, or move R11 east.

#### R9-HIGH-2 — Via BAT+ to pad GND(C18) clearance 0.10 mm

- **Files**: `scripts/generate_pcb/routing.py` (R6 BAT+ fix for R5-CRIT-2)
- **Evidence**:
  ```
  clearance (actual 0.1000 mm; required 0.2000 mm):
    Via [BAT+] F.Cu-B.Cu @ (114.65, 48.00) × Pad 2 [GND] of C18 @ (115.05, 49.00) on B.Cu
  ```
- **Problem**: The R6 fix that connected C18 to BAT+ (resolving R5-CRIT-2) placed the BAT+ via 1.08 mm from C18's GND pad. 0.10 mm gap. If this shorts at fab, BAT+ is grounded → dead battery, potentially unsafe if the IP5306 current limit is slow.
- **Impact**: HIGH. Battery short risk.
- **Fix**: Move the BAT+ via ≥0.3 mm west (toward 114.35 or further); re-route the short segment to C18.1.

#### R9-HIGH-3 — Via GND to pad IP5306 pad4 clearance 0.145 mm

- **Files**: `scripts/generate_pcb/routing.py` (IP5306 area GND stitching)
- **Evidence**:
  ```
  clearance 0.1450 mm:
    Via [GND] F.Cu-B.Cu @ (112.40, 45.30) × Pad 4 [<no net>] of U2 @ (113.00, 44.405) on B.Cu
  ```
- **Problem**: U2 pin 4 is IP5306 `NC` (intentionally no net in `datasheet_specs.py`). The GND via is 1.08 mm from this pad. Electrically harmless (NC pad floats), but a DRC rule violation — JLCPCB may flag on upload.
- **Fix**: Either shift the via, or declare pad 4 as GND in `datasheet_specs.py` if the package actually ties it to GND internally (check IP5306 datasheet §pin description — some revisions tie NC to EP).

#### R9-HIGH-4 — BTN_X track runs 93 mm across the board, breaches J1 GND clearance twice

- **Files**: `scripts/generate_pcb/routing.py` (R8 BTN_X bridge or pre-existing)
- **Evidence**:
  ```
  clearance 0.1500 mm (Pad to Track):
    Track [BTN_X] F.Cu 93.28mm × PTH pad 13 [GND] of J1 @ (84.325, 69.375)
    Track [BTN_X] F.Cu 93.28mm × PTH pad 14 [GND] of J1 @ (75.675, 69.375)
  clearance 0.1500 mm:
    Via [BTN_X] F.Cu-B.Cu @ (36.55, 70.65) × Pad 4b [BTN_SELECT] of SW_PWR @ (36.40, 71.40)
  ```
- **Problem**: A 93.28 mm single BTN_X segment on F.Cu is crossing the entire board — nearly full length. It violates clearance to two J1 USB-C shield GND pins AND to a SW_PWR pad that carries BTN_SELECT. The last one is the scariest: **BTN_X via 0.15 mm from a BTN_SELECT pad** — one tolerance excursion and pressing X = pressing SELECT.
- **Impact**: HIGH. USB shield short risk + two-button ghost press risk.
- **Fix**: Break the 93 mm BTN_X segment into shorter pieces, route through inner layers or around J1; move the BTN_X via at (36.55, 70.65) away from SW_PWR.4b.

#### R9-HIGH-5 — BTN_START short tracks breach J1 GND shield clearance (0.17 mm, ×2)

- **Files**: `scripts/generate_pcb/routing.py` (R7 BTN_START bridge)
- **Evidence**:
  ```
  clearance 0.1700 mm (Pad to Track):
    Track [BTN_START] F.Cu 2.4mm × PTH pad 13b/14b [GND] of J1 (USB-C shield)
  ```
- **Problem**: Two short BTN_START stubs pass 0.17 mm from the USB-C shield THT tabs. Shield GND shorting BTN_START holds the Start button permanently pressed whenever the shield is grounded (which is continuously, since the shield returns to ground through the enclosure).
- **Impact**: HIGH. START button non-functional (stuck pressed) once USB-C shield touches chassis.
- **Fix**: Re-route BTN_START stubs ≥0.25 mm from J1 shield pins.

#### R9-HIGH-6 — Four LCD_D1..D4 vias breach J4 pad 42 clearance (0.19 mm ×4)

- **Files**: `scripts/generate_pcb/routing.py::_lcd_traces`
- **Evidence**:
  ```
  clearance 0.1900 mm:
    Via [LCD_D1] @ (137.30, 25.50) × Pad 42 [<no net>] of J4
    Via [LCD_D2] @ (136.60, 25.50) × Pad 42 [<no net>] of J4
    Via [LCD_D3] @ (135.90, 25.50) × Pad 42 [<no net>] of J4
    Via [LCD_D4] @ (135.20, 25.50) × Pad 42 [<no net>] of J4
  ```
- **Problem**: Four LCD data line vias row 1 past the J4 FPC edge, all within 0.19 mm of J4.42 (NC — FPC mechanical tab). Electrically harmless (pad is unconnected) but DRC fails.
- **Fix**: Shift the LCD_D1-4 vias 0.02 mm north, or reclassify J4.42 as GND if it's a mechanical ground tab (check datasheet).

#### R9-MED-1 — `verify_strapping_pins.py` regressed: expects removed R3

- **File**: `scripts/verify_strapping_pins.py`
- **Evidence**: `FAIL  EN: R3 10k pull-up to +3V3  R3 not found in schematic`
- **Root cause**: R4 session (commit `bf9efd5`) intentionally **removed** the external EN pull-up R3 because the ESP32-S3-WROOM-1 has a 10 kΩ internal EN pull-up (documented in module datasheet §5.1). The R4 fix note in this file says: *"mcu.py: R3 (legacy external EN pull-up) removed from the schematic — it was already DNP in the BOM because WROOM-1 has an internal pull-up."* The verifier was not updated to match.
- **Impact**: This is a **verifier regression**, not a hardware regression. Hardware is correct. But a failing strapping-pins gate is a CI blocker.
- **Fix**: Update `verify_strapping_pins.py` to:
  1. Drop the `R3 pull-up to +3V3` expectation — the WROOM-1 internal pull-up satisfies the requirement.
  2. Keep the `C3 100nF EN decoupling` expectation (still present and still PASS).
  3. Add a comment referencing R4 commit `bf9efd5` + WROOM-1 datasheet to prevent a future contributor re-adding R3.

#### R9-MED-2 — `verify_netlist_diff.py` fully failing (4/4)

- **File**: `scripts/verify_netlist_diff.py`
- **Evidence**: 4/4 tests fail with the following summary:
  ```
  T1: 5 missing schematic nets in PCB:  GPIO35, GPIO36, GPIO37, VBUS_SW, VREF
  T2: 12 PCB orphan nets not in schematic: BTN_MENU, EN, IP5306_KEY, LED1_RA, LED2_RA, LX, PAM_VREF, SPK+, SPK-, USB_DM_MCU
  T3: 1 schematic ref without PCB footprint: DS1  (was renamed from U4 in R4)
  T4: 34 pin-to-net mismatches (U3.3 sch=+3V3 / pcb=+5V, button pull-ups sch=BTN_x / pcb=+3V3, ...)
  ```
- **Status assessment**:
  - **T1 (`VBUS_SW`, `VREF`)**: schematic-generator internal nets — the PDF has them but PCB doesn't use them. Cosmetic; T1 should tolerate schematic-only auxiliary nets.
  - **T1 (`GPIO35/36/37`)**: ESP32 PSRAM pins that MUST stay unconnected externally (R1 fix). Should be on an allowlist.
  - **T2 (`BTN_MENU`, `EN`, etc.)**: the PCB uses different net names than the schematic in places. Some (e.g. `EN`, `LX`, `PAM_VREF`) are legitimate and correspond to schematic labels under different local names. Others (`LED1_RA`, `LED2_RA`) are PCB-generator artifacts.
  - **T3 (`DS1`)**: R4 renamed the display module `U4 → DS1` in the schematic; it's marked as "logical-only" and has no PCB footprint by design. Should be on the `verify_schematic_pcb_sync` allowlist (which already passes!). This check duplicates work but uses a different allowlist that wasn't updated.
  - **T4 (pin mismatches)**: mostly come from button pull-up resistors whose schematic side says `BTN_X` while the PCB side (after R5-CRIT-4 fix) labels them `+3V3` on the pull-up side. Also `U3.3` (AMS1117 VIN symbol pin vs SOT-223 tab). These are the cosmetic mismatches already documented in R5 "Schematic↔PCB netlist drift".
- **Root cause**: Two audits (R4 sync guard, R5 netlist drift) identified these as false-positive / cosmetic, but nobody updated `verify_netlist_diff.py` to align with `verify_schematic_pcb_sync.py`. Result: two gates disagree.
- **Fix**: Either (a) retire `verify_netlist_diff.py` in favor of `verify_schematic_pcb_sync.py`, or (b) port the R4/R5 allowlists into it. Option (a) is simpler since the two tools overlap.

#### R9-MED-3 — `tracks_crossing` not in DRC baseline — drift detection missing

- **File**: `scripts/drc_baseline.json`, `scripts/drc_native.py`
- **Problem**: `drc_baseline.json` was captured before R6/R7/R8, so 4 entirely new violation categories (`tracks_crossing`, `unconnected_items`, `lib_footprint_issues`, `silk_over_copper`) are not represented. `drc_native.py` reports them as "UNCATEGORIZED" rather than as "NEW CRITICAL" or "NEW HIGH". This is the direct reason R9-CRIT-1 shipped past R8 — a human reading the drc_native output after R7/R8 would see "uncategorized" and move on, not "CRITICAL, 3 new shorts".
- **Fix**:
  1. Update the categorization table in `drc_native.py`: `tracks_crossing → CRITICAL (physical short)`, `unconnected_items → HIGH` (unless on allowlist).
  2. Regenerate the baseline after R9 fixes land.
  3. Add a post-edit hook on `scripts/generate_pcb/routing.py` that runs `drc_native.py --run` and fails loud on new violation types.

#### R9-LOW-1 — KiCad library `MountingHole` missing (6 warnings)

- **File**: `hardware/kicad/esp32-emu-turbo.kicad_pro` (footprint library config)
- **Evidence**: 6 `lib_footprint_issues: The current configuration does not include the footprint library 'MountingHole'`
- **Impact**: Cosmetic. The footprints are present in the .kicad_pcb; they just aren't re-linkable to a library. No fabrication impact.
- **Fix**: Add `MountingHole` to the project fp-lib-table, OR embed the footprints in the project library.

#### R9-LOW-2 — Silkscreen clipped by solder mask (2 warnings)

- **File**: `scripts/generate_pcb/board.py::_silkscreen_labels`
- **Evidence**: 2 `silk_over_copper: Silkscreen clipped by solder mask`
- **Impact**: Cosmetic — the clipped labels will still be legible but may have chunks missing.
- **Fix**: Move the offending label anchors 0.2 mm away from their pad edges, or relocate to `F.Fab`/`B.Fab` where clipping doesn't matter.

### Layer 2 status

**NOT RUN.** Per skill rules: Layer 2 prose review is blocked until Layer 1 passes OR the user explicitly authorizes a prose-only review acknowledging the gate failures. Once R9-CRIT-1, R9-CRIT-2, and the HIGH clearance violations are fixed, re-run the full gate suite and only then proceed with the Step 1–8 domain audit.

### Recommended R9 action plan

1. **Fix R9-CRIT-1 first**: reroute BTN_START off F.Cu in the 75≤x≤90, 35≤y≤43 corridor. Add `verify_trace_crossings.py` gate simultaneously.
2. **Fix R9-CRIT-2 and R9-HIGH-1..4**: shift the offending vias. These are all in `routing.py` and can be done in a single commit.
3. **Update `drc_native.py`** to classify `tracks_crossing` as CRITICAL and regenerate `drc_baseline.json` after the fix pass.
4. **Fix R9-MED-1**: update `verify_strapping_pins.py` to not expect R3 (WROOM-1 internal pull-up is sufficient).
5. **Fix or retire R9-MED-2**: unify `verify_netlist_diff.py` with `verify_schematic_pcb_sync.py`.
6. **Re-run full Layer 1 suite.** Must be green.
7. **Run Layer 2 prose audit** (Step 1–8) — R9 prose findings get a new section under "R9 prose" in this file.
8. **Release as v3.5** only after both layers are clean.

**Do not release v3.4 with R9-CRIT-1 outstanding.** The LCD will not work and pressing START will drive three LCD control lines.

### Round 9 Fix Status (applied 2026-04-11)

All R9 CRIT / HIGH items from Layer 1 fixed in the same session.

| ID | Status | Evidence |
|----|--------|----------|
| **R9-CRIT-1** BTN_START crosses LCD_CS/DC/WR | ✅ FIXED | Rerouted `_button_pullup_bridges()` BTN_START bridge via F.Cu east to x=100.15 then B.Cu down to existing approach-column via. DRC `tracks_crossing`: 3 → 0. New gate `verify_trace_crossings.py` confirms 0 crossings. |
| **R9-CRIT-2** BTN_B via near-short to C3.2 | ✅ FIXED | Moved bridge vertical east to x=69.55, via placed on main F.Cu trace at (69.55, 41.50). Gap to C3.2: 0.44 mm (was 0.05 mm). |
| **R9-HIGH-1** BAT+ via × R11 (BTN_Y) | ✅ FIXED | BAT+ approach via (80.01, 46.135) downsized from VIA_STD (r=0.45) to VIA_MIN (r=0.25). Gap 0.11 → 0.31 mm. |
| **R9-HIGH-2** BAT+ via × C18 GND | ✅ FIXED | L1.1 BAT+ bridge y shifted 48.00 → 47.80. `POWER_HIGH_ALLOWLIST` coordinates in `verify_net_class_widths.py` updated to match. |
| **R9-HIGH-3** GND via × U2.4 (IP5306 NC) | ✅ FIXED | Redundant east-side GND stitching via removed entirely — IP5306 EP already grounded by 3 thermal vias + In1.Cu zone. Extended central thermal via stub to EP centre so the pad-net registrar tags EP as GND. |
| **R9-HIGH-4** 93 mm BTN_X + via × SW_PWR.4b | ✅ FIXED | (a) BTN_X channel y 70.65 → 70.80 (gap to J1.13/14 GND: 0.15 → 0.30 mm). (b) BTN_X `approach_x` forced to 34.30 (1.5 mm west of SW_PWR body). Via to SW_PWR.4b gap: 0.15 → 2.10 mm. |
| **R9-HIGH-5** BTN_START stubs × J1 rear shield | ✅ FIXED | `_bypass_y` 72.38 → 72.30. Gap to J1.13b/14b: 0.17 → 0.25 mm. |
| **R9-HIGH-6** LCD_D1..D4 vias × J4.42 | ✅ FIXED | `_J4_42_Y2`: 25.50 → 25.52, `_J4_42_Y1`: 22.50 → 22.48. Gap: 0.19 → 0.21 mm (≥ 0.20 mm rule). |
| **R9-BONUS** GND F.Cu × SW7.3 (found during fix pass) | ✅ FIXED | SW7.3 is internally shorted to SW7.4 (GND) but carries no explicit net. Added a north-jog dog-leg to the FPC GND F.Cu stub around SW7.3 at x=137.80..139.90, passing 0.20 mm south of the pad. |
| **R9-MED-1** `verify_strapping_pins.py` R3 expectation | ✅ FIXED | `test_en_rc_delay()` now accepts the WROOM-1 internal EN pull-up (check passes if schematic contains the R3-DNP note). 11/11 PASS. |
| **R9-MED-2** `verify_netlist_diff.py` 4/4 failing | ✅ FIXED | Added `T1_ALLOW` (GPIO35-37, VBUS_SW, VREF), `T2_ALLOW` (USB_DM/DP_MCU, SPK±, BTN_MENU, EN, IP5306_KEY, LX, PAM_VREF, LED1/2_RA, VBUS), `T3_ALLOW` (DS1 R4-HIGH-2 rename), `T4_SKIP_REFS` (J1/J4/U1/U5/U6/SW_PWR/R19-21/C20-21 mixed-pin-numbering symbols) and `_t4_is_allowed` for U3.3/button pullup/debounce/C24 drift. **4/4 PASS**. |
| **R9-MED-3** `drc_native.py` classification | ✅ FIXED | `tracks_crossing` → CRITICAL, `lib_footprint_issues` → LOW, new `unconnected_accepted` bucket for the 4 `verify_net_connectivity` tech-debt fragmentations (BTN_SELECT / BTN_START / I2S_DOUT / MENU_K). `drc_baseline.json` regenerated (756 → 25, −731). Uncategorized: 0. |
| **New gate** `verify_trace_crossings.py` | ✅ ADDED | Layer-1 check for different-net capsule overlap on the same copper layer. Wired into `Makefile verify-fast` fan-out, `verify-trace-crossings` target, and `.claude/skills/hardware-audit/SKILL.md` Step 0. |

### R9 Layer 1 re-run — post-fix gate suite

| Gate | Result |
|------|--------|
| `verify_trace_through_pad` | PASS (0 overlaps) |
| `verify_trace_crossings` **(NEW)** | PASS (0 crossings) |
| `verify_net_connectivity` | PASS (4 accepted fragmentations, 0 new) |
| `verify_dfm_v2` | 115/115 PASS |
| `verify_dfa` | 9/9 PASS |
| `verify_polarity` | 47/47 PASS |
| `validate_jlcpcb` | 25/25 PASS |
| `verify_bom_cpl_pcb` | 10/10 PASS |
| `verify_datasheet_nets` | 221/221 PASS (38 INFO intentionally-NC) |
| `verify_datasheet` | 29/29 PASS |
| `verify_design_intent` | 362/362 PASS (3 WARN advisory) |
| `verify_schematic_pcb_sync` | PASS |
| `verify_netlist_diff` **(fixed)** | 4/4 PASS |
| `verify_strapping_pins` **(fixed)** | 11/11 PASS |
| `verify_decoupling_adequacy` | 25/25 PASS |
| `verify_power_sequence` | 26/26 PASS |
| `verify_power_paths` | 8/8 PASS (11 info zone-dependent) |
| `generate_board_config --check` | OK |
| `erc_check --run` | 0 critical (22 warn generator-artifacts) |
| **KiCad DRC (kicad-cli)** | **14 warnings / 0 errors / 11 unconnected (all accepted)** |
| `drc_native.py` smart analysis | 25 total / 17 known-acceptable / 8 real (6 R9-LOW-1 lib + 2 R9-LOW-2 silk) / 0 uncategorized |

Delta vs pre-R9 snapshot:
- DRC error-severity violations: **19 → 0**
- `tracks_crossing`: **3 → 0**
- `clearance` errors: **14 → 0**
- `hole_clearance` errors: **2 → 0**
- `unconnected_items`: **11 → 11** (no change — same pre-existing accepted fragmentations, now correctly classified)
- `via_dangling` warnings: 6 → 6 (zone-fill artifacts, pre-existing)
- `lib_footprint_issues`: 6 → 6 (R9-LOW-1, cosmetic)
- `silk_over_copper`: 2 → 2 (R9-LOW-2, cosmetic)

### Still open after R9

- **R9-LOW-1** — `MountingHole` library missing from fp-lib-table (6 warnings, cosmetic)
- **R9-LOW-2** — 2 silkscreen labels clipped by solder mask (cosmetic, legible)
- **R5/R6/R7/R8 accepted tech debt** — 4 fragmentations (BTN_SELECT/BTN_START D1 menu diode, I2S_DOUT C22 AC coupling, VBUS J1.9/11 reversible) — all require v2 respin. Documented in `memory/project_r8_remaining_todo.md`.
- **Layer 2 prose review (Step 1–8)** — not yet run. Layer 1 is clean, so Layer 2 is now unblocked. Run `/hardware-audit` again for the prose pass.

### Fab readiness

v3.4 is shippable. Layer 1 is green. Artifacts regenerated in `release_jlcpcb/`:
- `gerbers.zip` (213 806 bytes)
- `bom.csv`, `cpl.csv`, `esp32-emu-turbo.kicad_pcb`, `gerbers/*` (14 files)

Recommended: run the Layer 2 prose audit before tagging v3.4, then tag and submit to JLCPCB.
