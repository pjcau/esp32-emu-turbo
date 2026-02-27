---
name: pad-analysis
description: Analyze pad-to-pad distances to detect spacing violations before DFM upload
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
argument-hint: [--threshold <mm>] (default 0.15)
---

# Pad Distance Analysis

Analyze PCB pad-to-pad and pad-to-via edge distances to detect spacing violations.

**Argument**: Optional threshold in mm (default 0.15). Example: `--threshold 0.20`

## CRITICAL: False Positive Filtering

The script reports ALL close pairs, but many are **intentional**:
- Traces connecting TO their target pad = same-net (OK)
- Vias adjacent to their connected pads = same-net (OK)
- Only **different-net** pairs with gap < threshold are real violations

Always filter results by net before acting on them.

## Steps

### 1. Run analysis

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/analyze_pad_distances.py $ARGUMENTS
```

If no arguments provided, use default threshold:
```bash
python3 scripts/analyze_pad_distances.py --threshold 0.15
```

### 2. Parse results

From the output, create a categorized table:

| Pair | Layer | Gap (mm) | Same Net? | Verdict |
|------|-------|----------|-----------|---------|
| U1:1 ↔ C3:1 | F.Cu | 0.08 | No | VIOLATION |
| J4:5 ↔ via | B.Cu | 0.00 | Yes | OK (intentional) |

### 3. Identify real violations only

Filter out same-net pairs. Focus on:
- **Different-net pairs with gap < 0.10mm** → DANGER (JLCPCB will reject)
- **Different-net pairs with gap 0.10-0.15mm** → WARNING (may trigger DFM alert)
- **Same-net pairs** → IGNORE (intentional connections)

### 4. Map violations to source

For each real violation, identify the fix location:

| Issue Type | Fix File | Fix Action |
|------------|----------|------------|
| Pad-to-pad too close | `scripts/generate_pcb/board.py` | Move component in `_component_placeholders()` |
| Via-to-pad too close | `scripts/generate_pcb/routing.py` | Move via position |
| Mounting hole clearance | `scripts/generate_pcb/board.py` | Increase hole-to-component gap |

### 5. Summary

Print a summary:
- Total pairs analyzed
- Pairs below threshold (all)
- Same-net pairs filtered out
- **Real violations remaining**
- Recommended fix priority

## Key Files

- `scripts/analyze_pad_distances.py` — Main analysis script
- `scripts/generate_pcb/board.py` — Component placement (fix positions here)
- `scripts/generate_pcb/routing.py` — Via/trace positions (fix routing here)
