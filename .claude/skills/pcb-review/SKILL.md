---
name: pcb-review
description: Comprehensive PCB design review — power, signal, thermal, EMI, manufacturability, mechanical
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, WebSearch
---

# PCB Design Review

Comprehensive design review of the PCB layout, analyzing 6 key domains like a senior PCB engineer would. Produces a scored report with actionable improvement suggestions.

## Steps

### 1. Run the automated review

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/pcb_review.py
```

### 2. Review findings

The script analyzes 6 domains (scored 1-10 each):

| Domain | What it checks |
|--------|---------------|
| Power Integrity | Decoupling caps near ICs, power trace widths, GND plane coverage |
| Signal Integrity | Bus trace length matching, parallel trace crosstalk, high-speed routing |
| Thermal | Power IC thermal relief, via count, copper area for heat spreading |
| Manufacturability | JLCPCB min trace/space, drill sizes, annular rings |
| EMI/EMC | Ground plane continuity, signal return paths, decoupling strategy |
| Mechanical | Mounting hole symmetry, connector accessibility, FPC strain relief |

### 3. Address priority items

Focus on the Top 5 improvements suggested by the review.

### 4. Re-run to verify

After making changes, regenerate and re-run:
```bash
python3 -m scripts.generate_pcb hardware/kicad
python3 scripts/pcb_review.py
```

## Summary Report Format

| Domain | Score | Key Finding |
|--------|-------|-------------|
| Power Integrity | ?/10 | ... |
| Signal Integrity | ?/10 | ... |
| Thermal | ?/10 | ... |
| Manufacturability | ?/10 | ... |
| EMI/EMC | ?/10 | ... |
| Mechanical | ?/10 | ... |
| **OVERALL** | **?/60** | ... |

## Key Files

- `scripts/pcb_review.py` — Automated review script
- `.claude/skills/pcb-review/review-checklist.md` — Detailed scoring criteria
- `scripts/drc_check.py` — Reuses parse_pcb() for PCB parsing
- `scripts/generate_pcb/board.py` — Component positions
- `scripts/generate_pcb/routing.py` — Trace routing constants
