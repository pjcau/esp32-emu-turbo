# Hardware Audit Bug Report

**Date**: 2026-04-09 | **Auditors**: 5x Opus agents (10 iterations)
**Scope**: Power, boot, display, audio, SD, buttons, USB, performance, integration, edge cases
**Status**: All CRITICAL/HIGH/MEDIUM fixed (9/9)

## CRITICAL (2) — Device-breaking, must fix

### BUG-C1: Audio — I2S standard mode fed to analog PAM8403 (no DAC)
- **Domain**: audio
- **Description**: Firmware `audio.c` uses `i2s_std` mode (serial digital). PAM8403 expects analog input. I2S_DOUT digital bitstream → PAM8403 INL/INR produces noise, not audio. BCLK/LRCK intentionally unrouted.
- **Impact**: No usable audio output
- **Fix**: Change `audio.c` to PDM TX mode (`i2s_pdm_tx_config_t`). ESP32-S3 PDM output on DOUT pin + existing RC filter (0.47uF cap + 20k bias) = analog approximation. **Firmware-only fix, no PCB change.**
- **Files**: `software/main/audio.c` (lines 37-52)

### BUG-C2: BTN_L (GPIO45) floating — firmware never enables internal pull-up
- **Domain**: buttons/firmware
- **Description**: R14 external pull-up is DNP (correct for VDD_SPI strapping). `board_config.h` comment says "firmware MUST enable internal pull-up". But `input.c` line 45 sets `pull_up_en = GPIO_PULLUP_DISABLE` for ALL buttons including BTN_L.
- **Impact**: L shoulder button reads random values. Non-functional for all SNES games using L/R.
- **Fix**: After GPIO config loop in `input_init()`, add: `gpio_set_pull_mode(BTN_L, GPIO_PULLUP_ONLY);`
- **Files**: `software/main/input.c` (line 42-48)

## HIGH (2) — Significant issues

### BUG-H1: Schematic GPIO table has wrong pin numbers
- **Domain**: documentation/schematic
- **Description**: `mcu.py` line 170 says "GPIO36=MOSI GPIO37=MISO" but config.py says GPIO44/GPIO43. GPIO35/36/37 are PSRAM! Line 178 says "GPIO35=L GPIO43=R" but should be GPIO45/GPIO3.
- **Impact**: Misleading schematic PDFs distributed with design
- **Fix**: Update `mcu.py` lines 170, 178 to match `config.py`
- **Files**: `scripts/generate_schematics/sheets/mcu.py`

### BUG-H2: Display schematic has stale LCD_RD=GPIO3, LCD_BL=GPIO45 labels
- **Domain**: documentation/schematic
- **Description**: `display.py` still wires LCD_RD→GPIO3 and LCD_BL→GPIO45 as GPIO signals. Actually they're tied to +3V3 on FPC. GPIO3=BTN_R, GPIO45=BTN_L in reality.
- **Impact**: Confusing schematic review
- **Fix**: Update `display.py` to remove GPIO references for LCD_RD/LCD_BL
- **Files**: `scripts/generate_schematics/sheets/display.py`

## MEDIUM (5) — Worth fixing

### BUG-M1: LCD backlight has no current-limiting resistor
- **Domain**: display
- **Description**: LCD_BL (FPC pin 33) connected directly to +3V3. No series resistor. Some bare panels have internal limiting, some don't.
- **Impact**: Possible LED overdrive/damage on certain panels
- **Fix**: Verify panel spec or add 1-10ohm series resistor
- **Files**: `scripts/generate_pcb/routing.py` (lines 1707-1736)

### BUG-M2: AMS1117 thermal margin tight during charge+play
- **Domain**: power
- **Description**: At 600-700mA (ESP32+SD+display during USB charging), dissipation = 1.19W, junction temp ~132C > 125C max.
- **Impact**: Possible thermal shutdown during simultaneous gaming+charging
- **Fix**: Add thermal vias under AMS1117 or consider switching regulator for v2
- **Files**: `scripts/generate_schematics/sheets/power_supply.py`

### BUG-M3: No WiFi antenna keepout zone
- **Domain**: performance
- **Description**: GND zone on inner layers extends under ESP32 antenna area. Espressif recommends 15mm keepout.
- **Impact**: Degraded WiFi/BLE range (irrelevant if WiFi not used in emulator)
- **Fix**: Add copper keepout on all layers near antenna if WiFi planned
- **Files**: `scripts/generate_pcb/board.py`

### BUG-M4: USB shield directly tied to GND (no RC filter)
- **Domain**: usb
- **Description**: Shield pins → GND without 1M+4.7nF filter. May inject noise into GND plane.
- **Impact**: Possible audio noise from USB ground loop
- **Fix**: Optional RC filter on shield connection
- **Files**: `hardware/datasheet_specs.py`

### BUG-M5: SD card SPI lines lack pull-up resistors
- **Domain**: sd
- **Description**: TF-01A is bare slot (no module pull-ups). SD spec requires pull-ups on CMD/DAT0/DAT3/CLK.
- **Impact**: Some SD card brands may fail to initialize
- **Fix**: Enable ESP32 internal pull-ups in firmware before SD init, or add external 10k
- **Files**: `scripts/generate_schematics/sheets/sd_card.py`, `software/main/sdcard.c`

## LOW (8) — Minor/cosmetic

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

- USB-C CC pull-downs (5.1k) ✓
- IP5306 caps (22uF+10uF output) ✓
- AMS1117 caps (10uF in, 22uF out) ✓
- ESP32 decoupling (2x100nF on VDD) ✓
- PSRAM pins (GPIO33-37) not used externally ✓
- Flash pins (GPIO27-32) not exposed ✓
- All strapping pins correctly handled ✓
- EN pin RC circuit (10k+100nF) ✓
- USB ESD protection (USBLC6-2SC6) ✓
- USB 22ohm series resistors ✓
- USB D+/D- length matched ✓
- GPIO count: 33/45 used, no overlaps ✓
- PAM8403 power/SHDN/decoupling ✓
- FPC pin reversal mapping ✓
- Interface mode IM[2:0]=011 (8080 8-bit) ✓
