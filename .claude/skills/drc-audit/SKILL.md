---
name: drc-audit
model: claude-opus-4-7
description: Full KiCad DRC audit — catches net shorts, unconnected pads, dangling vias, and clearance violations that custom scripts miss
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# DRC Audit — Full KiCad Native Electrical Check

Deep electrical verification using KiCad DRC that covers gaps in our custom DFM/DFA scripts.

## Why this exists

Our custom scripts (`verify_dfm_v2.py`, `verify_dfa.py`) check manufacturing rules but
**deliberately ignore** critical KiCad DRC categories:

| KiCad DRC category | Custom scripts | This skill |
|---------------------|---------------|------------|
| `shorting_items` | IGNORED | **CHECKED** |
| `unconnected_items` | IGNORED | **CHECKED** |
| `via_dangling` | IGNORED | **CHECKED** |
| `clearance` | IGNORED | **CHECKED** |
| `solder_mask_bridge` | IGNORED | **CHECKED** |
| `track_dangling` | IGNORED | **CHECKED** |
| `copper_edge_clearance` | ≤5 tolerated | **ANALYZED** |
| `hole_clearance` | ≤1 tolerated | **ANALYZED** |
| `silk_over_copper` | ≤2 tolerated | **ANALYZED** |

Additionally, `verify_dfm_v2.py` test 43 (trace-pad different-net) **auto-skips** when >90%
of pads have net=0, which is exactly the condition this skill detects.

## Steps

### 1. Run KiCad DRC

```bash
kicad-cli pcb drc \
  --output /tmp/drc_audit_report.json \
  --format json \
  --severity-all \
  --units mm \
  --all-track-errors \
  hardware/kicad/esp32-emu-turbo.kicad_pcb
```

### 2. Parse and classify ALL violations

```python
import json
from collections import Counter

with open('/tmp/drc_audit_report.json') as f:
    data = json.load(f)

violations = data.get('violations', [])
unconnected = data.get('unconnected_items', [])

# Count by type
types = Counter(v['type'] for v in violations)
```

Report every category — do NOT skip any.

### 3. Analyze shorting_items — real shorts vs pad-net assignment bugs

For each `shorting_items` violation, check if the description matches `"nets XXX and )"` (empty second net).

- `"nets XXX and )"` → **pad-net assignment bug** (pad has no net, trace touches it)
- `"nets XXX and YYY)"` → **REAL SHORT** (two different nets touching — critical)

Count separately:
```
Real net-vs-net shorts: X  ← CRITICAL, board will malfunction
Pad-net assignment bugs: Y ← Generator bug, needs _init_pads() fix
```

### 4. Root-cause pad-net assignment failures

If pad-net bugs are found:

```python
# Run routing to populate _PAD_NETS
from generate_pcb import routing
routing.generate_all_traces()
pad_nets = routing.get_pad_nets()

# Check which component refs have NO pad-net assignments
all_refs_with_nets = set(k[0] for k in pad_nets.keys())
# Compare against all component refs in the PCB
```

For each missing ref, check if it's in `routing.py:_init_pads()`. Missing refs are the root cause.

### 5. Analyze unconnected items

For each `unconnected_items` entry:
- Identify the net and component pads involved
- Determine if the break is caused by:
  - Missing trace segment (routing gap)
  - Missing via (layer transition)
  - Pad-net assignment failure (cascading from step 3)

### 6. Analyze clearance violations

For each `clearance` violation:
- Report exact position, gap vs required gap, and involved nets
- Flag any gap < 0.05mm as **CRITICAL** (near-zero clearance)
- Group by proximity to identify hot-spots

### 7. Analyze dangling vias

For each `via_dangling`:
- Report position and net
- Check if via has trace on both F.Cu and B.Cu sides
- Determine if via is orphaned or just missing continuation

### 8. Generate report

```
## DRC Audit Report

### Summary
| Category | Count | Severity |
|----------|-------|----------|
| Real net shorts | X | CRITICAL |
| Pad-net bugs | Y | HIGH (generator fix) |
| Unconnected items | Z | HIGH |
| Clearance violations | W | MEDIUM-HIGH |
| Dangling vias | V | MEDIUM |
| Solder mask bridge | S | LOW (cascading) |

### Real Net Shorts (CRITICAL)
[list each with position, nets involved]

### Pad-Net Assignment Failures
[list missing refs, root cause in _init_pads()]
[fix: add to passive_placements list]

### Unconnected Items
[group by net, identify break location]

### Clearance Violations
[list with gap values, flag <0.05mm]

### Dangling Vias
[list with position, suggest remove or connect]

### Action Items
1. [prioritized fixes]
```

### 9. Verify fix effectiveness

After applying fixes, re-run steps 1-2 and confirm:
- Real shorts: 0
- Pad-net bugs: 0
- Unconnected items: 0 (or justified exceptions)
- Clearance < 0.05mm: 0

## Key insight

**Never trust custom scripts alone.** KiCad DRC checks electrical connectivity
at the netlist level — something our geometry-based scripts cannot do. Run this
audit after every `generate_pcb` and before every `/release`.

## Files

- `hardware/kicad/esp32-emu-turbo.kicad_pcb` — PCB file to audit
- `scripts/generate_pcb/routing.py` — `_init_pads()` and `_PAD_NETS` (pad-net assignment)
- `scripts/generate_pcb/board.py` — `_inject_pad_net()` (net injection into KiCad file)
- `scripts/verify_dfm_v2.py` — Custom DFM (115 tests, misses electrical shorts)
- `scripts/verify_dfa.py` — Custom DFA (9 tests, misses electrical shorts)
