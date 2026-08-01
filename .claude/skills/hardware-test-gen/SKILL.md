---
name: hardware-test-gen
model: claude-opus-5
description: Regenerate, build and run the bring-up test firmware (software/bringup_test) for first power-on board validation. Run after PCB assembly to verify every GPIO, bus and peripheral, with machine-parseable serial telemetry.
disable-model-invocation: false
allowed-tools: Bash, Read, Grep, Glob
---

# Bring-Up Test Firmware (containment layer 5)

The bring-up firmware is the multimeter for a bench with no instruments:
57 checks over serial, one machine-parseable line each. It lives in
`software/bringup_test/` as a standalone ESP-IDF project — it compiles
the PRODUCTION drivers (`display.c`, `audio.c`, `sdcard.c` from
`software/main/`) rather than reimplementing them, so validation cannot
disagree with shipping firmware (the R10-LOW-2 lesson). Its
`main/bringup_test.c` is GENERATED from `board_config.h` by
`software/bringup_test/generate.py`; never edit the .c by hand.

Full protocol, per-check implication tables and serial format:
`website/docs/manufacturing/bring-up-protocol.md`.

## Steps

### 1. Regenerate after any GPIO change

```bash
make bringup-generate   # board_config.h -> main/bringup_test.c
make bringup-check      # staleness gate (also in verify-all as verify_bringup_fresh)
```

### 2. Build (Docker, ESP-IDF v5.4)

```bash
make bringup-build
```

Zero warnings under -Werror is the bar; the build has already caught
real defects (format truncation, a spinlock inside an
interrupts-disabled timing loop).

### 3. Flash and capture (board connected via USB)

```bash
make bringup-flash
```

Serial format — six ';'-separated fields per check, then a trailer:

```
BRINGUP;<seq>;<PASS|FAIL|SKIP>;<id>;<pins>;<detail>
BRINGUP-FAILED;<ids>
BRINGUP-SKIPPED;<ids>
BRINGUP-SUMMARY;total=57;pass=..;fail=..;skip=..;verdict=GREEN|RED
BRINGUP-END
```

FAIL lines append `implicates: <net or component>` — the line names the
copper to inspect, not just the symptom.

## What to know before reading a report

- **Six SKIPs are permanent board properties**, each with its reason on
  the line: no battery sense exists (no divider, no IP5306 I2C), +3V3 is
  not ADC-measurable on ESP32-S3 (covered instead by brownout-detector +
  load + temperature delta), LCD_RD is tied HIGH so the panel cannot be
  read back (bus/DMA proven, visual confirmation is the SKIP).
- **sd.cmd0 SKIPs conditionally** naming BOTH hypotheses (empty socket
  vs broken SD_MISO) — there is no card-detect on this board, so they
  are indistinguishable from firmware.
- **btn.<X>.rc are measurements, not polls**: each button node is driven
  low, released, and the 10k/100nF rise through VIH is timed (~1390 us
  expected; the microseconds are always printed). BTN_L (GPIO45, DNP
  pull) inverts: never rising is its PASS.
- **btn.isolation catches D1 fitted backwards** (the v4.3.1 failure
  class): drive each button net low, the other 11 must stay high.
- **A brownout mid-check is telemetry, not silence**: the dying check's
  id is kept in RTC_NOINIT memory and the next boot reports it next to
  reset=BROWNOUT.
- Strapping pins GPIO0/3/45 are tested after boot only — their reset
  state cannot be asserted from software; GPIO46 (LCD_WR) is the fourth
  strap (ROM log enable), benign, noted in board_config.h.

Before first power-on, run `/first-article-check` phase B (photos) — do
not power a board whose orientation sweep has not passed.

## History

The previous generator (`scripts/generate_hw_tests.py` →
`software/test/test_hardware.c`) was retired 2026-08-01: the generated
firmware called `i2s_channel_init_pdm_tx_channel()`, which does not
exist in ESP-IDF (production uses `i2s_channel_init_pdm_tx_mode`), so it
had never compiled — validation firmware that cannot build is a
blind spot wearing a green badge.
