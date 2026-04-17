---
name: jlcpcb-validate
model: claude-opus-4-7
description: Run comprehensive JLCPCB DFM validation — drill rules, edge clearances, copper checks, NPTH, silkscreen, gerber completeness, and best practices. Use after PCB changes, before JLCPCB upload, or when investigating manufacturing rejections.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# JLCPCB DFM Validation

Comprehensive manufacturing rule validation against JLCPCB capabilities.
Complements `/verify` (88 DFM + 9 DFA tests) with additional JLCPCB-specific checks.

## Critical Rules

- Run this AFTER `/verify` passes — this is an additional validation layer
- All thresholds are from JLCPCB official documentation (see `dfm-reference.md`)
- Warnings are informational (best practices), failures are hard manufacturing limits

## Steps

### 1. Run JLCPCB validation

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/validate_jlcpcb.py
```

### 2. (Optional) Run full verification suite first

```bash
python3 scripts/verify_dfm_v2.py && python3 scripts/verify_dfa.py
```

### 3. Interpret results

The validation covers 20+ checks in 6 categories:

| Category | Tests | What it checks |
|----------|-------|----------------|
| **Drill & Hole Rules** | 8 | Drill increment (0.05mm), PTH/NPTH min/max, via aspect ratio, PTH annular ring |
| **Board & Edge Rules** | 3 | Outline closure, copper-to-edge (0.3mm), SMD-to-edge (0.3mm) |
| **Copper & Trace Rules** | 2 | Copper sliver detection (< 0.1mm), power trace width |
| **NPTH & Mounting Rules** | 3 | NPTH-to-copper clearance, paste on NPTH, mounting hole zones |
| **Silkscreen & Mask** | 1 | Character height >= 1.0mm |
| **Gerber & Manufacturing** | 1 | All 7 required layers present |
| **Best Practices** | 2+ | Decoupling cap distance, fine-pitch pad width |

### 4. If failures are found

1. Read the violation details in the output
2. Cross-reference with `dfm-reference.md` for JLCPCB limits
3. Fix in the generator (`scripts/generate_pcb/`)
4. Regenerate: `python3 -m scripts.generate_pcb hardware/kicad`
5. Re-run: `python3 scripts/validate_jlcpcb.py`

### 5. Full pre-upload checklist

For maximum confidence before JLCPCB upload, run all three:

```bash
python3 scripts/verify_dfm_v2.py && \
python3 scripts/verify_dfa.py && \
python3 scripts/validate_jlcpcb.py
```

All three must pass with 0 failures.

## Key Files

- `scripts/validate_jlcpcb.py` — This validation script (source of truth)
- `.claude/skills/dfm-fix/dfm-reference.md` — Comprehensive JLCPCB DFM rules reference
- `scripts/verify_dfm_v2.py` — Primary DFM test suite (88 tests)
- `scripts/verify_dfa.py` — DFA assembly tests (9 tests)
- `scripts/pcb_cache.py` — Shared PCB parse cache

## JLCPCB Quick Limits (from dfm-reference.md)

```
Trace width:     0.127mm (5 mil)     Via drill (2L):  0.3mm (0.2mm +$)
Trace spacing:   0.127mm (5 mil)     Via pad (2L):    0.6mm (0.45mm OK)
Annular ring:    0.075mm (abs min)    PTH drill:       0.15-6.3mm
Mask bridge:     0.1mm (multilayer)   NPTH drill:      0.5-6.3mm
Cu to edge:      0.3mm               Aspect ratio:    10:1 max
Trace to edge:   0.2mm               Drill increment: 0.05mm
```
