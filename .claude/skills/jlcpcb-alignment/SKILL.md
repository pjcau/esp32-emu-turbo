---
name: jlcpcb-alignment
description: Verify JLCPCB pick-and-place alignment for all bottom-side ICs and connectors. Checks CPL rotation, position corrections, and pin-to-net assignments. Use before any JLCPCB PCBA order or after changing CPL/rotation/position parameters.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# JLCPCB Batch Alignment Verification

Runs three verification passes on all 7 bottom-side ICs/connectors to ensure the JLCPCB pick-and-place machine will correctly align every component.

## Components Verified

| Ref | Package | Pins | Key Risk |
|-----|---------|------|----------|
| U1 | ESP32-S3-WROOM-1 | 41 | +3.62mm Y position correction |
| U2 | IP5306 ESOP-8 | 9 | Exposed pad, asymmetric |
| U3 | AMS1117 SOT-223 | 4 | Tab pad, asymmetric |
| U5 | PAM8403 SOP-16 | 16 | 90deg pre-rotation + override |
| J1 | USB-C 16-pin | 16 | -1.3mm Y position correction |
| J4 | FPC 40-pin | 42 | -2.66mm X position correction |
| U6 | Micro SD TF-01A | 13 | Asymmetric shield pads |

## Steps

### 1. Run the batch alignment tests

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -c "
import sys
sys.path.insert(0, 'scripts')
from verify_dfm_v2 import test_batch_pin_alignment, test_batch_pin_net_assignment, PASS, FAIL
test_batch_pin_alignment()
test_batch_pin_net_assignment()
print(f'\nResults: {PASS} passed, {FAIL} failed')
sys.exit(1 if FAIL else 0)
"
```

This runs three test categories:
- **CPL rotation alignment** (7 tests): verifies `rotate(cpl_rot) -> mirror -> translate` matches `rotate(kicad_rot) -> mirror -> translate` for every pin. Max pin error must be < 0.1mm.
- **CPL position corrections** (7 tests): verifies `cpl_pos == board_pos + correction` for each component. Catches wrong/missing corrections.
- **Pin net assignments** (7 tests): verifies every routed pin's net in the PCB file matches the routing module's expected net. Catches pin swaps from rotation/mirror errors.

### 2. Interpret results

- **All PASS**: Safe to order JLCPCB PCBA.
- **Rotation FAIL**: The CPL rotation for that component is wrong. Fix in `scripts/generate_pcb/jlcpcb_export.py`:
  - `_JLCPCB_ROT_OVERRIDES` for per-ref overrides
  - `_JLCPCB_ROT_CORRECTIONS` for per-footprint pattern corrections
- **Position FAIL**: The CPL position correction is wrong. Fix in `_JLCPCB_POS_CORRECTIONS`.
- **Net FAIL**: Pin assignments don't match routing. This usually means a rotation or mirror bug in the PCB generation.

### 3. After fixing, re-verify

```bash
make verify-fast   # Full DFM suite (64 tests, ~1.5s)
```

## Algorithm Details

The test uses the **rotate -> mirror -> translate** convention (matching `get_pads()` and `routing._compute_pads()`):

1. Get raw footprint pads from `footprints.FOOTPRINTS[name][0]("B")`
2. For each pin, compute reference position: `rotate(kicad_rot) -> mirror_X -> translate(board_pos)`
3. Compute JLCPCB model position: `rotate(cpl_rot) -> mirror_X -> translate(board_pos)`
4. Per-pin error = Euclidean distance between positions
5. Max error < 0.1mm -> PASS

Using board_pos (not CPL pos) for translation isolates the rotation check from position corrections.

## Key Files

- `scripts/verify_dfm_v2.py` — `test_batch_pin_alignment()` and `test_batch_pin_net_assignment()`
- `scripts/generate_pcb/jlcpcb_export.py` — rotation/position corrections
- `scripts/generate_pcb/footprints.py` — pad definitions (ground truth model)
- `scripts/generate_pcb/routing.py` — `_compute_pads()` (PCB file convention)
- `release_jlcpcb/cpl.csv` — CPL data sent to JLCPCB
