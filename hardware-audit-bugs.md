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
