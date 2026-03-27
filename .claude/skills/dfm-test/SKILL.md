---
name: dfm-test
description: Run DFM guard tests and add new regression tests after fixing PCB issues
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

# DFM Guard Test Suite

Run DFM verification tests and manage regression guards for the PCB.

## When to Use

- After any PCB generation change (`scripts/generate_pcb/`) to verify no regressions
- After fixing a DFM issue, to add a new guard test preventing recurrence
- Before creating a JLCPCB release, as a pre-flight check

## Steps

### 1. Regenerate PCB (ensures tests run against latest code)

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

### 2. Run DFM test suite

```bash
python3 scripts/verify_dfm_v2.py
```

### 3. Interpret results

The test suite covers 43 DFM tests + 9 DFA tests:

**DFM tests (`verify_dfm_v2.py` — 43 tests):**

| # | Category | Tests | What it checks |
|---|----------|-------|----------------|
| 1-4 | CPL positions | 4 | J1, SW_PWR, U1, U5 position/rotation in JLCPCB CPL |
| 5-6 | Silkscreen | 2 | Reference/Value on Fab layer, mounting holes on Fab |
| 7-8 | Spacing | 2 | C1/C2-U3 gap >= 1.5mm, gr_text >= 6mm from holes |
| 9 | Via ring | 1 | Annular ring >= 0.075mm on all vias |
| 10 | Gerbers | 1 | gerbers.zip has >= 12 files |
| 11-12 | Footprints | 2 | U5 pin alignment analysis, SOP-16 aperture |
| 13-15 | KiCad DRC | 3 | copper_edge=0, hole_to_hole=0, silk issues=0 |
| 16 | Trace spacing | 1 | Parallel trace gap violations <= baseline |
| 17 | Via spacing | 1 | Via hole-to-hole gap >= 0.25mm |
| 18 | Display stagger | 1 | Bottom stagger traces use ESP32 pin midpoints |
| 19+ | Mounting/drill | 2+ | Mounting hole trace clearance, drill-trace clearance |
| 42 | Drill-trace | 1 | Drill doesn't cut different-net traces (JLCPCB) |
| 43 | Trace-pad net | 1 | Trace-pad different-net clearance check |

**DFA tests (`verify_dfa.py` — 9 tests):**

| # | Category | Tests | What it checks |
|---|----------|-------|----------------|
| 1-3 | BOM | 3 | File exists, component counts, part numbers |
| 4-6 | CPL | 3 | File exists, positions, rotations |
| 7-9 | Polarity | 3 | Polarity-sensitive components correct |

### 4. Add a new guard test (when fixing a DFM issue)

If you just fixed a DFM issue, add a regression guard test to `scripts/verify_dfm_v2.py`:

1. **Read the test file**:
   ```bash
   cat scripts/verify_dfm_v2.py
   ```

2. **Add a new test function** following the existing pattern:
   ```python
   def test_new_check():
       """Test N: Description of what this guards against."""
       print("\n── New Check ──")
       with open(PCB_FILE) as f:
           content = f.read()
       # ... parse and check ...
       check("Description", condition, f"detail={value}")
   ```

3. **Register it** in `__main__` block at the bottom.

4. **Update the test count** in this SKILL.md and in `.claude/skills/verify/SKILL.md`.

### 5. Existing helper functions

The test file provides reusable helpers:

| Function | Returns | Use for |
|----------|---------|---------|
| `read_cpl()` | `dict[ref → row]` | CPL position/rotation checks |
| `_parse_segments(content)` | `list[dict]` | Trace analysis (x1,y1,x2,y2,w,layer,net) |
| `_parse_vias(content)` | `list[dict]` | Via analysis (x,y,size,drill,net) |
| `_seg_min_dist(s1,s2)` | `float or None` | Edge-to-edge gap between parallel traces |
| `check(name, cond, detail)` | — | Register pass/fail result |

### 6. Baseline management

Some tests use baselines for inherent violations in dense areas:

- **Trace spacing baseline**: Tracks violations in dense routing areas (USB-C, pull-ups, ESP32 fan-out)
- **Drill-trace baseline**: Currently 71 (via drills near different-net traces)
- **Trace-pad baseline**: Currently 140 (traces near different-net pads)
  - If routing changes REDUCE violations, lower the baseline
  - If routing changes INCREASE violations, investigate the regression before raising baseline

## Key Files

- `scripts/verify_dfm_v2.py` — Test suite (source of truth)
- `scripts/generate_pcb/routing.py` — Trace routing (most DFM issues originate here)
- `scripts/generate_pcb/footprints.py` — Footprint pad/mask definitions
- `scripts/generate_pcb/board.py` — Component placement, silkscreen
- `scripts/generate_pcb/jlcpcb_export.py` — CPL rotation/position corrections
