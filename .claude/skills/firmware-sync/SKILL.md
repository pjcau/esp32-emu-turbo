---
name: firmware-sync
model: claude-opus-4-7
description: Verify GPIO pin assignments match between firmware (board_config.h) and schematic (config.py)
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# Firmware-PCB GPIO Sync Verification

Cross-reference GPIO pin assignments between the firmware source of truth and the schematic generator.

## Steps

### 1. Read schematic config (source of truth)

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
```

Read `scripts/generate_schematics/config.py` — this is the master GPIO mapping:
- LCD data bus: GPIO 4-11 (LCD_D0-D7)
- LCD control: GPIO 12 (CS), 13 (RST), 14 (DC), 46 (WR), 3 (RD), 45 (BL)
- Audio I2S: GPIO 15 (BCLK), 16 (LRCK), 17 (DOUT)
- SD SPI: GPIO 36 (MOSI), 37 (MISO), 38 (CLK), 39 (CS)
- Buttons: GPIO 40-42, 1, 2, 48, 47, 21, 18, 0, 35, 19
- Joystick: GPIO 20 (JOY_X), 44 (JOY_Y)

### 2. Read firmware board config

Read `software/main/board_config.h` — the firmware's GPIO definitions.

### 3. Compare pin assignments

For each signal, verify:
- GPIO number matches between config.py and board_config.h
- Pin name/comment matches the signal purpose
- No GPIO conflicts (same GPIO used for different signals)

### 4. Report mismatches

Print a comparison table:

```
Signal       | Schematic GPIO | Firmware GPIO | Status
-------------|---------------|---------------|-------
LCD_D0       | 4             | 4             | OK
LCD_D1       | 5             | 5             | OK
...
BTN_START    | 18            | 19            | MISMATCH!
```

### 5. Suggest fixes (optional)

If mismatches found:
- Determine which source is correct (schematic is source of truth)
- Suggest edits to `board_config.h` to match `config.py`
- Ask user before applying changes

## Key Files

- `scripts/generate_schematics/config.py` — Master GPIO mapping (source of truth)
- `software/main/board_config.h` — Firmware GPIO definitions
- `website/docs/snes-hardware.md` — Documentation (should also match)
