---
name: pcb-to-firmware
model: claude-opus-4-7
description: Auto-propagate PCB/routing changes to firmware (board_config.h), docs, and config files. Run after any GPIO remapping, component change, or routing modification. Detects diffs, applies fixes, verifies consistency.
disable-model-invocation: false
allowed-tools: Bash, Read, Edit, Grep, Glob, Agent
---

# PCB-to-Firmware Sync

Automatically propagate hardware changes (PCB routing, GPIO remapping, component changes) to all dependent software and documentation files.

## When to Run

- After PCB routing changes that affect GPIO assignments
- After component swaps (different pinout, different LCSC part)
- After schematic regeneration that changed net assignments
- After `config.py` GPIO_NETS modifications
- Before firmware builds to ensure consistency

## Architecture

```
config.py (GPIO_NETS)     <- MASTER source of truth
    |
    +-- board_config.h    <- firmware GPIO #defines
    +-- datasheet_specs.py <- pin-to-net verification
    +-- routing.py        <- PCB trace routing (button/signal assignments)
    +-- website/docs/     <- documentation (schematics.md, software.md, etc.)
```

## Steps

### 1. Detect Changes -- Diff Analysis

Compare current `config.py` GPIO_NETS against `board_config.h` to find mismatches.

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/verify_design_intent.py 2>&1 | head -60
```

This runs 18+ cross-source consistency tests. Focus on:
- **T1**: GPIO mismatch `board_config.h` vs `config.py`
- **T2**: GPIO mismatch `config.py` vs `datasheet_specs.py`
- **T3**: Duplicate GPIO assignments

Also run the dedicated sync check:

```bash
make firmware-sync-check 2>&1
```

### 2. Read Current State of All Sources

Read and parse all four truth sources to build a complete diff table:

| File | What to Read |
|------|-------------|
| `scripts/generate_schematics/config.py` | `GPIO_NETS` dict -- GPIO# -> signal name |
| `software/main/board_config.h` | All `#define XXX GPIO_NUM_YY` lines |
| `hardware/datasheet_specs.py` | U1 (ESP32) pin specs -> net assignments |
| `scripts/generate_pcb/routing.py` | Button GPIO assignments in `front_btns` list (~line 2774) |

### 3. Build Mismatch Report

Generate a complete comparison table:

```
## PCB-to-Firmware Sync Report

| Signal       | config.py | board_config.h | datasheet_specs | routing.py | Status    |
|-------------|-----------|----------------|-----------------|------------|-----------|
| LCD_D0      | GPIO 4    | GPIO 4         | pin 4 -> LCD_D0  | --          | OK        |
| BTN_START   | GPIO 18   | GPIO 19        | pin 11 -> BTN_ST | GPIO 18    | MISMATCH! |
```

For each MISMATCH:
- Identify which source is authoritative (`config.py` is MASTER)
- Determine cascading impacts (firmware behavior, PCB routing, docs)

### 4. Apply Fixes (config.py is always right)

#### 4a. Fix `board_config.h`

For each GPIO mismatch, update the `#define`:

```c
// Before:
#define BTN_START            GPIO_NUM_19
// After (matching config.py):
#define BTN_START            GPIO_NUM_18
```

Rules:
- Preserve existing comments and formatting
- Update `BTN_MASK_*` defines if button order changed
- Update `BTN_MENU_COMBO` if START/SELECT GPIOs changed
- Check for new signals added in config.py but missing in board_config.h

#### 4b. Fix `datasheet_specs.py`

If U1 pin-to-net mapping changed:
- Update the affected pin entry in `COMPONENT_SPECS["U1"]["pins"]`
- Ensure pin number matches ESP32-S3 datasheet for the GPIO

#### 4c. Fix routing.py button assignments

If button GPIOs changed, update `front_btns` list:
```python
front_btns = [
    ("SW1", "BTN_UP", 40),    # (ref, net_name, gpio)
    ("SW2", "BTN_DOWN", 41),
    ...
]
```

Also check shoulder button definitions (~line 3640+).

#### 4d. Detect new hardware features

Check if PCB changes added new signals not yet in firmware:
- New buttons (e.g., BTN_MENU with dedicated GPIO)
- New peripherals (e.g., battery voltage ADC)
- Changed interfaces (e.g., SPI -> parallel LCD)

For each new signal:
1. Add `#define` to `board_config.h`
2. Add initialization code suggestion
3. Flag for developer review

#### 4e. Auto-generate board_config.h from config.py

Use the generator script to produce what `board_config.h` GPIO defines SHOULD look like, then compare against the actual file:

```bash
# Print generated defines (for review)
python3 scripts/generate_board_config.py

# Check for mismatches (exits 1 if drift detected)
python3 scripts/generate_board_config.py --check
```

The script reads `GPIO_NETS` from `config.py`, groups signals by category (LCD, SD, I2S, BTN, USB), and formats them as `#define SIGNAL_NAME GPIO_NUM_XX` matching `board_config.h` style. Special characters are sanitized: `USB_D+` -> `USB_DP`, `USB_D-` -> `USB_DN`.

If `--check` reports mismatches, fix `board_config.h` as described in step 4a above -- the script output shows the exact expected lines.

You can also use an inline snippet for one-off inspection:
```python
from scripts.generate_schematics.config import GPIO_NETS

for gpio, signal in sorted(GPIO_NETS.items()):
    macro = signal.replace("+", "P").replace("-", "N")
    print(f"#define {macro:20s} GPIO_NUM_{gpio}")
```

### 5. Fix Documentation

After code changes, update docs:

```bash
# Check which docs reference GPIO numbers
grep -rn 'GPIO_NUM_\|GPIO.*[0-9]' website/docs/schematics.md website/docs/software.md
```

Key docs to update:
- `website/docs/schematics.md` -- GPIO assignment table
- `website/docs/software.md` -- GPIO cross-reference, pin descriptions
- `website/docs/snes-hardware.md` -- Hardware spec GPIO mapping

### 6. Regenerate Dependent Files

```bash
# Regenerate schematics (uses config.py)
python3 -m scripts.generate_schematics hardware/kicad

# Regenerate PCB (uses routing.py)
python3 -m scripts.generate_pcb hardware/kicad

# Run full verification suite
python3 scripts/verify_design_intent.py
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_dfa.py
```

### 7. Final Verification

```bash
# Must all pass with 0 failures
make firmware-sync-check
python3 scripts/verify_design_intent.py 2>&1 | grep -E 'Results|FAIL'
python3 scripts/verify_dfm_v2.py 2>&1 | grep Results
python3 scripts/verify_dfa.py 2>&1 | grep Results
```

## Key Files

### Sources of Truth (priority order)
1. `scripts/generate_schematics/config.py` -- **MASTER** GPIO mapping
2. `software/main/board_config.h` -- Firmware GPIO defines
3. `hardware/datasheet_specs.py` -- Component pin-to-net specs
4. `scripts/generate_pcb/routing.py` -- PCB routing GPIO refs (lines 2774, 3640)

### Verification Scripts
- `scripts/verify_design_intent.py` -- 18-test cross-source adversary
- `make firmware-sync-check` -- Quick GPIO sync validation
- `scripts/generate_board_config.py` -- Generate + compare board_config.h defines

### Documentation
- `website/docs/schematics.md` -- Electrical schematic docs
- `website/docs/software.md` -- Firmware architecture + GPIO table
- `website/docs/snes-hardware.md` -- Hardware spec
