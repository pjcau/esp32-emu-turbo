---
name: doc
description: Scan all documentation against source-of-truth files (config.py, board_config.h, routing.py, BOM, PCB) and report/fix outdated values. Use after PCB changes, GPIO remapping, BOM updates, or before releases.
disable-model-invocation: true
allowed-tools: Bash, Read, Edit, Grep, Glob, Agent
---

# Documentation Audit & Sync

Verify all documentation in `website/docs/` is up-to-date with the actual codebase, then fix any discrepancies.

## Critical Rules

- NEVER invent numbers — always read from source-of-truth files first
- Report ALL discrepancies before fixing anything
- Fix docs to match code, NEVER the reverse

## Steps

### 1. Collect Source-of-Truth Values

Read these files to build the ground truth:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
```

| Data | Source File | What to Extract |
|------|-----------|-----------------|
| GPIO pins | `scripts/generate_schematics/config.py` | GPIO_NETS dict (all 35 assignments) |
| Firmware pins | `software/main/board_config.h` | All `#define` GPIO numbers |
| Trace widths | `scripts/generate_pcb/routing.py` lines 32-36 | W_PWR, W_SIG, W_DATA, W_AUDIO |
| Board dims | `scripts/generate_pcb/config.py` | BOARD_W, BOARD_H |
| BOM | `hardware/kicad/jlcpcb/bom.csv` | Component count, refs |
| CPL | `hardware/kicad/jlcpcb/cpl.csv` | Placement count |
| DFM tests | `python3 scripts/verify_dfm_v2.py 2>&1 \| grep Results` | Test count |
| DFA tests | `python3 scripts/verify_dfa.py 2>&1 \| grep Results` | Test count |
| Collision grid | `python3 -c "from scripts.generate_pcb.collision import _SUPPRESSIONS; print(len(_SUPPRESSIONS))"` | Suppression count |
| Via count | `grep -c '(via ' hardware/kicad/esp32-emu-turbo.kicad_pcb` | Total vias |
| Via annular ring | `scripts/verify_dfm_v2.py` grep for ring threshold | Min ring value |
| Footprint count | `grep -c '(footprint ' hardware/kicad/esp32-emu-turbo.kicad_pcb` | Total footprints |

### 2. Audit Each Documentation File

Cross-reference extracted values against these docs:

#### 2a. `website/docs/schematics.md`
- GPIO pin assignments (lines ~154-165)
- Component count references
- Net name list

#### 2b. `website/docs/components.md`
- BOM table: component count, LCSC part numbers
- Cost estimates
- Compare against `hardware/kicad/jlcpcb/bom.csv`

#### 2c. `website/docs/manufacturing.md`
- DFM flagged component count
- Total component count
- DRC error count
- Board specs (layers, thickness)

#### 2d. `website/docs/verification.md`
- DFM test count (was 64, check current)
- DFA test count (should be 9)
- Trace width table (should match routing.py)
- Via drill/pad/annular ring specs
- Connectivity test results (44/44 nets)
- Via counts per signal

#### 2e. `website/docs/pcb.md`
- Board dimensions (160x75mm)
- Layer count (4)
- Trace width table (W_PWR, W_SIG, W_DATA, W_AUDIO)
- Via counts per net
- Footprint count
- Power net segment/via counts
- Collision/suppression references

#### 2f. `website/docs/software.md`
- GPIO cross-verification table
- Pin assignments must match board_config.h

#### 2g. `website/docs/claude-agents.md`
- Skills count per agent
- Test count references

### 3. Generate Report

Output a table:

```
## Documentation Audit Report

| File | Check | Status | Details |
|------|-------|--------|---------|
| schematics.md | GPIO pins | OK/OUTDATED | ... |
| components.md | BOM count | OK/OUTDATED | ... |
| ...           | ...       | ...          | ... |
```

### 4. Fix Outdated Docs

For each OUTDATED entry:
1. Show the old value and new value
2. Edit the file using the Edit tool
3. Mark as FIXED in the report

### 5. Final Verification

After fixes, re-run the audit to confirm all checks pass:

```bash
# Verify docs build correctly
cd website && npm run build 2>&1 | tail -5
```

## Key Files

### Source of Truth
- `scripts/generate_schematics/config.py` — GPIO assignments
- `software/main/board_config.h` — Firmware GPIO defines
- `scripts/generate_pcb/routing.py` — Trace widths, via sizes
- `scripts/generate_pcb/config.py` — Board dimensions
- `scripts/generate_pcb/collision.py` — Collision suppressions
- `hardware/kicad/jlcpcb/bom.csv` — BOM components
- `hardware/kicad/jlcpcb/cpl.csv` — CPL placements
- `scripts/verify_dfm_v2.py` — DFM test definitions
- `scripts/verify_dfa.py` — DFA test definitions

### Documentation
- `website/docs/schematics.md` — Electrical schematic docs
- `website/docs/components.md` — BOM with links
- `website/docs/manufacturing.md` — JLCPCB ordering guide
- `website/docs/verification.md` — Pre-production checks
- `website/docs/pcb.md` — PCB layout documentation
- `website/docs/software.md` — Firmware architecture
- `website/docs/claude-agents.md` — Agent/skill architecture
