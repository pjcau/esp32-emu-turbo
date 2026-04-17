---
name: hardware-test-gen
model: claude-opus-4-7
description: Generate ESP-IDF Unity test firmware for prototype board validation. Run after PCB assembly to verify all GPIOs, buses, and peripherals work correctly.
disable-model-invocation: false
allowed-tools: Bash, Read, Grep, Glob
---

# Hardware Test Generator

Generates Unity test firmware from `board_config.h` for post-assembly prototype validation.

## Steps

### 1. Generate test file

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/generate_hw_tests.py
```

Reads `software/main/board_config.h` and generates `software/test/test_hardware.c` with 20 tests:
- 12 button idle-HIGH tests (BTN_L uses internal pull-up)
- LCD D0-D7 walking-1 short detection
- LCD CS/RST/DC/WR toggle test
- SD SPI bus init + CMD0 probe
- I2S PDM TX silence test
- USB Serial JTAG verification
- 3.3V power rail ADC sanity
- LED blink (visual, skipped in CI)
- PSRAM 1MB XOR pattern verify

### 2. Build and flash

```bash
# Option A: replace app_main temporarily
cd software
cp main/main.c main/main.c.bak
cp test/test_hardware.c main/main.c
idf.py build flash monitor
mv main/main.c.bak main/main.c

# Option B: use ESP-IDF test component (preferred)
idf.py -T test build flash monitor
```

### 3. Interpret results

USB-CDC serial output (115200 baud):
```
20 Tests 0 Failures 1 Ignored
OK
```

- **PASS**: GPIO/bus/peripheral verified working
- **FAIL**: hardware defect, assembly error, or wrong component
- **IGNORE**: test skipped (e.g., LED visual check)

## Key Files

- `scripts/generate_hw_tests.py` — test generator script
- `software/test/test_hardware.c` — generated test firmware
- `software/main/board_config.h` — GPIO pin definitions (input)
