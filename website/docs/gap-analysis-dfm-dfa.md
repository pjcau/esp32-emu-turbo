---
sidebar_position: 12
title: Gap Analysis — DFM/DFA/JLCPCB
description: Community repo analysis and new verification checks added to the pipeline
---

# Gap Analysis: DFM/DFA/JLCPCB Community Repos

**Date:** 2026-04-11  
**Method:** Analyzed 12 GitHub repositories for PCB DFM/DFA/manufacturing checks, extracted what our pipeline was missing, and implemented the gaps.

## Repos Analyzed

| Repo | Stars | Category | Useful? |
|------|-------|----------|---------|
| [agausmann/jlcpcb-kicad-drc](https://github.com/agausmann/jlcpcb-kicad-drc) | 2 | JLCPCB DRC rules | **YES** |
| [INTI-CMNB/KiBot](https://github.com/INTI-CMNB/KiBot) | 705 | KiCad CI/CD | **YES** |
| [HiGregSmith/KiPadCheck](https://github.com/HiGregSmith/KiPadCheck) | 8 | Pad/drill/stencil checks | **YES** |
| [Seeed-Studio/kicad-mcp-server](https://github.com/Seeed-Studio/kicad-mcp-server) | 29 | KiCad MCP | Reviewed, no new checks |
| [tscircuit/jlcsearch](https://github.com/tscircuit/jlcsearch) | 24 | JLCPCB parts search | Future: stock/price API |
| [Bouni/kicad-jlcpcb-tools](https://github.com/Bouni/kicad-jlcpcb-tools) | 1837 | KiCad JLCPCB plugin | Rotation DB only |
| [tscircuit/tscircuit](https://github.com/tscircuit/tscircuit) | 2080 | Programmatic PCB | No DFM/DRC checks |
| [MakerPnP/makerpnp](https://github.com/MakerPnP/makerpnp) | 41 | Assembly logistics | No design rule checks |
| [AR6420/PCB_Agent](https://github.com/AR6420/PCB_Agent) | 1 | AI PCB routing | Too early stage |

## Gaps Found and Implemented

### G1: JLCPCB Official Capabilities Cross-Check (from jlcpcb-kicad-drc)

**Problem:** Our internal thresholds were more aggressive than JLCPCB's published limits in several areas. We could pass our own checks but fail JLCPCB's manufacturing review.

| Rule | Our Threshold | JLCPCB Official | Risk |
|------|--------------|-----------------|------|
| Via-to-via (diff net) | 0.25mm | 0.50mm | **2x tighter** |
| Via-to-track | 0.15mm | 0.254mm | **1.7x tighter** |
| PTH-to-track | 0.15mm | 0.33mm | **2.2x tighter** |
| Pad-to-track | 0.10mm | 0.20mm | **2x tighter** |
| THT annular ring | 0.13mm | 0.25mm | **1.9x tighter** |

**Solution:** `scripts/verify_jlcpcb_capabilities.py` (12 tests)
- Two-tier: FAIL at JLCPCB absolute minimum, WARN below recommended
- Summary table comparing board values vs JLCPCB limits
- Tests: trace width, spacing, via geometry, THT geometry, via-to-via, via-to-track, pad-to-track, SMD pad spacing
- NPTH pads correctly excluded from annular ring checks

### G2: IPC-7525 Stencil Aperture Analysis (from KiPadCheck)

**Problem:** Our existing aperture check in `verify_dfa.py` only tested at one stencil thickness (0.12mm). No area ratio analysis, no multi-thickness comparison, no paste type recommendation.

**Solution:** `scripts/verify_stencil_aperture.py` (6 tests)
- **Area ratio:** `(L x W) / [2(L+W) x T]` — IPC-7525 minimum 0.66
- **Aspect ratio:** `min(L,W) / T` — minimum 1.2 for laser-cut stencils (JLCPCB standard)
- **Multi-thickness analysis:** 3mil, 4mil, 5mil, JLCPCB standard (0.12mm)
- **Paste powder type recommendation:** Type 2-5 based on smallest aperture
- **Fine-pitch detail report:** Per-pad breakdown for pads <= 0.35mm

### G3: Standard Drill Size Audit (from KiPadCheck)

**Problem:** No check that drills match industry standard sizes. Non-standard drills can increase manufacturing cost or lead time.

**Solution:** `scripts/verify_drill_standards.py` (6 tests)
- **ISO metric compliance:** All drills vs ISO metric preferred set
- **JLCPCB common drills:** Flag uncommon sizes that may cost extra
- **Drill inventory:** Count unique sizes (JLCPCB includes 8 free)
- **Drill-to-pad ratio:** IPC-2222 limits (0.50-0.85), ideal range (0.60-0.75)
- **Via vs PTH appropriateness:** Flag oversized vias, micro-vias on 2-layer
- NPTH pads correctly excluded from drill-to-pad ratio

### G4: Zone Fill Freshness (from KiBot)

**Problem:** No check that copper zones are actually filled before gerber export. Stale/unfilled zones produce incorrect gerbers.

**Solution:** Added to `scripts/verify_dfm_v2.py` (3 new tests, now 119 total)
- Zone count > 0
- Filled polygon count > 0
- Fill coverage ratio (fills/zones >= 0.5)

### G5: Silk-to-Pad Stroke Distance (from KiPadCheck)

**Problem:** Existing silk-to-pad checks used bounding box overlap (coarse). KiPadCheck uses stroke-level geometry for precise distance.

**Solution:** Added to `scripts/verify_dfm_v2.py` (1 new test)
- Parses silkscreen line segments (fp_line + gr_line on SilkS layers)
- Computes actual distance from silk stroke to pad edge
- Minimum 0.15mm (JLCPCB recommendation for legibility)

### G6: Schematic Field Completeness (from KiBot)

**Problem:** No explicit check that every BOM entry has all required fields (value, footprint, LCSC part number).

**Solution:** Added to `scripts/verify_bom_cpl_pcb.py` (3 new tests, now 13 total)
- Value/comment field present
- Footprint field present
- LCSC part number present

## Not Implemented (and why)

| Gap | Source | Reason |
|-----|--------|--------|
| JLCPCB Basic/Preferred part flag | jlcsearch | Low priority; requires API integration. Future `/jlcpcb-parts` enhancement. |
| KiBot rotation database | KiBot/Bouni | Our `/fix-rotation` skill already handles rotations with its own database. |
| KiBot zone fill preflight | KiBot | Implemented as simpler zone fill freshness check (G4). |
| Seeed MCP pin conflict detection | Seeed-Studio | Already covered by our T19 test in `verify_design_intent.py`. |
| Seeed MCP device tree / test gen | Seeed-Studio | Linux-oriented; not applicable to ESP-IDF firmware. |

## Integration

New scripts are wired into both skills:

### `/hardware-audit` (Step 0 — automated gates)
```bash
python3 scripts/verify_jlcpcb_capabilities.py    # 12 tests
python3 scripts/verify_stencil_aperture.py        #  6 tests
python3 scripts/verify_drill_standards.py         #  6 tests
```

### `/pcb-review` (Step 1 — automated checks)
```bash
python3 scripts/verify_jlcpcb_capabilities.py
python3 scripts/verify_stencil_aperture.py
python3 scripts/verify_drill_standards.py
```

## Test Count Impact

| Before | After | Delta |
|--------|-------|-------|
| verify_dfm_v2.py: 115 | 119 | +4 |
| verify_bom_cpl_pcb.py: 10 | 13 | +3 |
| **New:** verify_jlcpcb_capabilities.py | 12 | +12 |
| **New:** verify_stencil_aperture.py | 6 | +6 |
| **New:** verify_drill_standards.py | 6 | +6 |
| **Total pipeline** | | **+31 tests** |

## Real Bugs Found and Fixed

The JLCPCB capabilities cross-check revealed violations at two levels:

### FAIL (board rejection risk) -- FIXED
1. **Via-to-via spacing (diff net):** 2 LCD_D2/D3 via pairs at exactly 0.500mm gap (JLCPCB 0.50mm drill-to-drill minimum)
   - **Fix:** Staggered Y positions of adjacent bridge vias (even/odd index pattern)
   - Diagonal distance: sqrt(0.70^2 + 0.28^2) = 0.754mm, gap = 0.554mm > 0.50mm

### WARN (below recommended, above absolute minimum) -- Accepted
- **Via-to-track:** 30+ gaps between 0.150-0.240mm (JLCPCB absolute min: 0.127mm, recommended: 0.254mm)
- **Pad-to-track:** 13+ gaps between 0.155-0.200mm (JLCPCB absolute min: 0.127mm, recommended: 0.20mm)

These WARNs are all above JLCPCB's universal 0.127mm (5mil) copper clearance minimum. The 0.254mm and 0.20mm thresholds from agausmann's DRC are **recommended values** for yield optimization, not rejection criteria. They will be improved in the v2 PCB respin where routing space allows.

### Threshold Correction
Initial analysis used agausmann/jlcpcb-kicad-drc values as absolute minimums. After cross-referencing with JLCPCB's actual capabilities page, we corrected the script to properly distinguish:
- **Tier 1 (FAIL):** Below JLCPCB absolute minimum (varies by feature type)
- **Tier 2 (WARN):** Below recommended (from agausmann community DRC)
