# hardware-audit — Layer 2 domain-by-domain checks (reference)

Moved out of SKILL.md 2026-07-26 (progressive disclosure). Read ONE
domain at a time while auditing it — not the whole file.

## Step 1 — Power chain audit (manual)

Trace: USB-C → IP5306 → +5V → **U3 SY8089 buck** → +3.3V → ESP32

Read and cross-check:
- `scripts/generate_schematics/sheets/power_supply.py` — schematic
- `scripts/generate_pcb/routing/` — PCB routing (`_power_traces`)
- `hardware/datasheet_specs.py` — IP5306, SY8089 pinouts
- `hardware/datasheets/U2_IP5306_*.pdf` + `U3_SY8089AAAC_C78988.pdf`
- `software/main/board_config.h` — power management notes

Check:
- L1 inductor placement and LX trace width (≥ 0.76 mm for 2.1 A boost)
- VBAT sense resistor divider (if present)
- Every bypass cap has short path to its pin pair
- **EN RC network — FIXED 2026-07-31 (R25-CRIT-1)**: `R3` (10k, EN → +3V3)
  and `C31` (100nF, EN → GND) sit on the EN trace right of `U1.3`
  (`routing/_shared.py` R3_POS/C31_POS). `C3` is a plain +3V3 decoupling
  cap, unrelated to EN. `EN` carries `U1.3`, `SW15.1`, `R3.1`, `C31.1`.
  The WROOM-1 does *not* integrate an EN pull-up (settled in `74c196e`).
  Gated by `verify_strapping_pins` (`test_en_rc_delay`) — verify, don't
  re-raise the old "EN has no RC" baseline (it was true until 2026-07-31)
- U3 buck loop: `C1` (C_IN) tight to U3 IN/GND, `C30` (C_OUT) tight to L2's
  output pad, `BUCK_LX` node kept small. **`C2` no longer exists** — the
  22 µF tantalum was deleted because a 1 MHz buck needs a low-ESR MLCC
- Bulk caps (C19 on the IP5306 +5V rail, C30 on the buck output) on the
  correct rail side of their regulators
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
- `scripts/generate_pcb/routing/display.py::_display_traces` (B.Cu routing)
- `hardware/datasheets/U1_ESP32-S3-WROOM-1_*.pdf` (GPIO → LCD pins)

Check:
- LCD_D0-D7 length skew ≤ 20 mm (acceptable for 20 MHz 8080)
- LCD_WR / LCD_DC / LCD_CS all on GPIO capable of 40+ MHz. **`LCD_RD` is not
  a net and reaches no GPIO** — FPC pin 12 is hard-tied to +3V3 (read strobe
  disabled, the display is write-only)
- Backlight — **R25-HIGH-1 FIXED 2026-07-31**: FPC pin 33 (LED-A) is fed
  from the **load-side +5V** (post-Q2, so it dies with SW16 OFF) through
  R27 (20R 1206) on net `LED_BLA` (~90 mA defined); LED-K (pins 34-36)
  to GND. Always-on while switched on, no PWM, no GPIO. One bench
  measurement of the actual panel current is still owed on first article.
  `LCD_BL`/`LCD_RD` remain retired gaps (ids 18/19) in
  `primitives.NET_LIST` — the real backlight net is named `LED_BLA`
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
- DAT1 (pad 8) is unused in SPI mode but MUST NOT be shorted to other
  nets. `verify_trace_through_pad.py` will catch any trace physically
  crossing it.
- Pad 9 is **Cd**, the socket's own card-detect contact — not DAT2, which
  is pad 1. A microSD card has eight contacts; the socket has nine pads.
  Do not carry SanDisk's nine-row pin tables onto this footprint: they are
  the full-size SD tables (see `scripts/vbench/models/card_microsd.py`).
- Card detect (if wired) uses dedicated GPIO + pull-up. On this board it
  is not wired at all — pad 9 is deliberately off-net since the R31-HIGH-2
  BTN_R reroute (the Cd blade is a switch to the grounded shell; no signal
  may share it).
- +3V3 supply has ≥ 1 µF decoupling within 5 mm of U6 VCC
- Level shifting: ESP32-S3 is 3.3 V native → no shifter needed
- NPTH positioning hole size matches datasheet (1.00 mm)

## Step 6 — Button audit (manual)

12 buttons + 1 menu combo diode D1 (BAT54C) + power switch SW16.

Check:
- Each button has pull-up + debounce cap (except BTN_L GPIO45: internal)
- Reset / Boot buttons (SW15, SW14) on EN and GPIO0
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

