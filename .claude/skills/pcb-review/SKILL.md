---
name: pcb-review
description: Comprehensive PCB design review — 8 domains, 100-point scoring, JLCPCB DFM rules, datasheet pin verification
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# PCB Design Review

Comprehensive design review of the PCB layout, analyzing 8 key domains like a senior PCB engineer would. Produces a scored report with actionable improvement suggestions.

## Sources

- JLCPCB manufacturing rules: `.claude/skills/pcb-review/review-checklist.md`
- JLCPCB blog best practices: trace angles, 3W rule, decoupling, impedance control, stackup
- Component datasheets: `hardware/datasheets/`
- DFM reference: `.claude/skills/dfm-fix/dfm-reference.md`

## Steps

### 1. Run automated checks

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/pcb_review.py
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_polarity.py
python3 scripts/verify_dfa.py
python3 scripts/validate_jlcpcb.py
```

### 2. Manual review against checklist

Read `review-checklist.md` and verify each domain:

| # | Domain (points) | Key checks |
|---|-----------------|------------|
| 1 | Power Integrity (15) | Trace widths for current, decoupling caps near ICs, GND/power planes |
| 2 | Signal Integrity (15) | Bus matching, USB diff pair, 3W rule, 45° traces, impedance |
| 3 | Thermal (10) | Thermal vias, EP pad connections, copper area, IC spacing |
| 4 | JLCPCB DFM (20) | Trace/pad/via spacing, mask bridge, copper-to-edge, fiducials, `validate_jlcpcb.py` |
| 5 | EMI/EMC (10) | GND plane continuity, return paths, decoupling strategy |
| 6 | Component Polarity (15) | Pin-1 vs datasheet, LED polarity, CPL rotation, BOM-CPL match |
| 7 | Mechanical (10) | Mounting holes, connector access, NPTH sizes, board outline |
| 8 | Documentation (5) | LCSC parts, gerbers, silkscreen, assembly variants |

### 3. Datasheet physical verification

```bash
python3 scripts/verify_datasheet.py
```

Automated cross-check of PCB vs datasheets (29 tests):
- Pin count per component (ICs, connectors, passives, switches)
- Pad pitch matches datasheet (0.5mm FPC, 1.27mm SOIC, 2.0mm JST, etc.)
- Pad span / body dimensions (catches wrong package, e.g. SOP-16 vs SOIC-16W)
- NPTH positioning hole count and drill size
- THT drill sizes (JST, USB shield tabs)
- Datasheet PDF presence in `hardware/datasheets/`

### 3b. Manual datasheet verification (Domain 6)

For each IC/connector, read the datasheet from `hardware/datasheets/` and verify:
- Pin 1 location matches footprint orientation
- Net assignments match datasheet pinout
- CPL rotation produces correct JLCPCB placement
- Passive component values match typical application circuit

### 4. Current capacity check (Domain 1)

Verify power trace widths against current requirements:
- VBUS/BAT+: up to 2.1A (IP5306 charger) → need ≥0.76mm (30mil)
- +5V: up to 1A → need ≥0.25mm (10mil)
- +3V3: up to 0.5A → need ≥0.13mm (5mil)
- LX (inductor): up to 2.1A pulsed → need ≥0.76mm (30mil)

### 5. Generate report

Format findings as:

```
## PCB Design Review Report

| # | Domain | Score | Key Finding |
|---|--------|-------|-------------|
| 1 | Power Integrity | ?/15 | ... |
| 2 | Signal Integrity | ?/15 | ... |
| 3 | Thermal | ?/10 | ... |
| 4 | JLCPCB DFM | ?/20 | ... |
| 5 | EMI/EMC | ?/10 | ... |
| 6 | Component Polarity | ?/15 | ... |
| 7 | Mechanical | ?/10 | ... |
| 8 | Documentation | ?/5 | ... |
| **TOTAL** | | **?/100** | ... |

### Top 5 Priority Fixes
1. ...
2. ...
```

### 6. Fix and re-verify

After making changes:
```bash
python3 -m scripts.generate_pcb hardware/kicad
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_polarity.py
python3 scripts/validate_jlcpcb.py
```

## Key Files

- `.claude/skills/pcb-review/review-checklist.md` — Full scoring criteria + JLCPCB rules reference
- `hardware/datasheets/` — Component datasheets for pin verification
- `scripts/pcb_review.py` — Automated review script
- `scripts/verify_dfm_v2.py` — DFM verification (114 tests)
- `scripts/verify_polarity.py` — Polarity/pin assignment tests
- `scripts/verify_dfa.py` — Assembly verification (9 tests)
- `scripts/verify_datasheet.py` — Datasheet vs PCB physical verification (29 tests)
- `scripts/validate_jlcpcb.py` — JLCPCB manufacturing validation (22 tests)
- `scripts/generate_pcb/routing.py` — Trace routing
- `scripts/generate_pcb/board.py` — Component placement
- `scripts/generate_pcb/jlcpcb_export.py` — CPL/BOM export
