---
name: dfm-fix
model: claude-opus-4-7
description: Analyze a DFM report and fix all issues in the PCB generation scripts
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, WebFetch, WebSearch
argument-hint: <path-to-dfm-report> (PDF, CSV, or text file)
---

# DFM Report Analysis & Fix

Analyze a DFM report (from JLCPCB or other manufacturer) and systematically fix all issues.

**Argument**: Path to the DFM report file (PDF, CSV, text, or image screenshot).

## Steps

### 1. Read the DFM report

Read the file provided as argument: `$ARGUMENTS`

If it's a PDF, read it with the Read tool (supports PDF).
If it's an image/screenshot, read it with the Read tool (supports images).
If it's a CSV or text file, read it normally.

### 2. Categorize issues

Parse and categorize all DFM issues into:

| Category | Severity | Example |
|----------|----------|---------|
| **Silkscreen-to-pad** | DANGER | Text overlapping SMD pads |
| **Silkscreen-to-hole** | DANGER | Text overlapping drill holes |
| **Soldermask bridge** | DANGER | Mask gap between close pads too small |
| **Trace clearance** | ERROR | Traces too close together |
| **Via annular ring** | ERROR | Via ring too small for manufacturing |
| **Component spacing** | WARNING | Components too close for pick-and-place |
| **Rotation mismatch** | WARNING | 3D model doesn't align with pads |

Print a summary table with counts per category.

### 3. Map issues to source files

For each issue, identify which source file controls it:

| Issue Type | Source File | Function/Section |
|------------|-----------|------------------|
| Silkscreen text layer | `scripts/generate_pcb/board.py` | `_component_placeholders()` |
| Silkscreen labels | `scripts/generate_pcb/board.py` | `_silkscreen_labels()` |
| Mounting hole text | `scripts/generate_pcb/primitives.py` | `mounting_hole()` |
| Component positions | `scripts/generate_pcb/board.py` | `_component_placeholders()` |
| Component spacing | `scripts/generate_pcb/board.py` | placement coordinates |
| Trace clearance | `scripts/generate_pcb/routing.py` | trace segments |
| Via sizes | `scripts/generate_pcb/routing.py` | `_via_net()` calls |
| Soldermask | `scripts/generate_pcb/footprints.py` | pad definitions |
| CPL rotation | `scripts/generate_pcb/jlcpcb_export.py` | `_JLCPCB_ROT_OVERRIDES` |
| CPL position | `scripts/generate_pcb/jlcpcb_export.py` | `_JLCPCB_POS_CORRECTIONS` |

### 4. Fix each issue

For each issue, in order of severity (DANGER first):
1. Read the relevant source file
2. Identify the exact code that needs to change
3. Apply the fix
4. Explain what was changed and why

### 5. Regenerate and verify

After all fixes:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
python3 scripts/verify_dfm_v2.py
```

### 6. Add regression guard test

For each fix, add a test to `scripts/verify_dfm_v2.py` to prevent recurrence.
See `/dfm-test` skill for details on adding guard tests.

### 7. Summary report

Print a final report:

| # | Issue | Severity | Fix Applied | File Changed |
|---|-------|----------|-------------|-------------|
| 1 | ... | DANGER | Moved text to Fab | board.py |
| 2 | ... | WARNING | Increased spacing | board.py |

## Reference: DFM issue patterns from previous fixes

See `dfm-reference.md` in this skill directory for known issue patterns and their solutions.

## Key Files

- `scripts/generate_pcb/board.py` — Component placement, silkscreen labels, text layers
- `scripts/generate_pcb/routing.py` — Trace routing, via sizes
- `scripts/generate_pcb/footprints.py` — Footprint pad/mask definitions
- `scripts/generate_pcb/primitives.py` — Mounting holes, board elements
- `scripts/generate_pcb/jlcpcb_export.py` — CPL rotation/position corrections
- `scripts/verify_dfm_v2.py` — Verification tests (update after fixes)
