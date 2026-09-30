---
id: workflow-guide
title: Agent & Skill Workflow Guide
sidebar_position: 1
---

# Agent & Skill Workflow Guide

How to use the 6 agents, 46 skills, and 6 lifecycle commands to design, verify, fix, and release the ESP32 Emu Turbo PCB.

---

## Architecture Overview

![Agent architecture: the user, the team-lead, the three worker agents and their sync points](/img/diagrams/agents.svg)

---

## When to Use What

### Decision Tree

![Which command to run for each need, and the pipeline it starts](/img/diagrams/decision-tree.svg)

---

## Scenario 1 — New PCB from Scratch

![New PCB from scratch: bootstrap, design, generate, verify with a fix loop, sync firmware, release](/img/diagrams/wf-new-pcb.svg)

### When to invoke the team-lead agent

Use `/team-lead` (or just describe a complex task) when changes span **multiple domains**:
- "Add a new audio amplifier" → team-lead dispatches pcb-engineer (footprint + routing) + software-dev (I2S driver) + cad-engineer (speaker cutout)
- "Change the display from SPI to parallel" → all three agents need updates

---

## Scenario 2 — Fix a DFM Issue

After JLCPCB DFM report or `verify_dfm_v2.py` failure:

![Fix a DFM issue: from the report or /verify to /dfm-fix, regenerate, re-verify, guard test, release-prep](/img/diagrams/wf-dfm-fix.svg)

### Key: the fix cycle

![The fix cycle: verify, fix, regenerate, re-verify, then add a guard and release](/img/diagrams/fix-cycle.svg)

---

## Scenario 3 — Pre-Release Verification

Full verification sweep before ordering from JLCPCB:

![Pre-release verification: the eight skills /verify-pcb composes](/img/diagrams/wf-pre-release.svg)

### Hard gates (must pass for release)

| Gate | Script | What it catches |
|---|---|---|
| Fab shorts | `verify_trace_through_pad.py` | Trace over unnetted pad |
| Trace crossings | `verify_trace_crossings.py` | Same-layer different-net overlap |
| Copper clearance | `verify_copper_clearance.py` | < 0.10mm copper gap (Shapely) |
| Net connectivity | `verify_net_connectivity.py` | Fragmented copper per net |

---

## Scenario 4 — Release to JLCPCB

![Release to JLCPCB: the nine steps /release-pcb runs through /full-release](/img/diagrams/wf-release.svg)

After release:
1. Upload `release_jlcpcb/gerbers.zip` to [jlcpcb.com](https://jlcpcb.com/)
2. Upload `bom.csv` + `cpl.csv` for SMT assembly
3. Verify 3D viewer alignment for bottom-side components
4. Order 5x PCBs, 4-layer, 1.6mm, ENIG, SMT both sides

---

## Scenario 5 — Hardware Audit (Deep Review)

![Hardware audit: Layer 1 automated gates, then Layer 2 domain-by-domain review, output hardware-audit-bugs.md](/img/diagrams/wf-hardware-audit.svg)

---

## Scenario 6 — GPIO / Component Change

When you change a GPIO assignment or add/remove a component:

![GPIO or component change: edit config.py, /pcb-to-firmware, /generate-pcb, /verify-pcb, /firmware-sync](/img/diagrams/wf-gpio-change.svg)

---

## Scenario 7 — Enclosure Update

After PCB board outline or component position changes:

![Enclosure update: design, render, export](/img/diagrams/wf-enclosure.svg)

---

## Quick Reference — Skill Categories

### Design Phase (create from scratch)

| Skill | What it does |
|---|---|
| `/pcb-schematic` | Define GPIO nets, generate .kicad_sch sheets |
| `/pcb-board` | Set board outline, layers, mounting holes |
| `/pcb-components` | Place all component footprints |
| `/pcb-routing` | Route traces, vias, copper zones |
| `/pcb-library` | Query footprint pad info |

### Generate Phase (build artifacts)

| Skill | What it does |
|---|---|
| `/generate` | Python scripts -> .kicad_pcb + BOM + CPL + gerbers |
| `/check` | DRC + 3D render + gerbers + DFM quick check |
| `/render` | SVG layer views + animation GIF |
| `/pcba-render` | 13 photorealistic 3D PCBA views (raytracer) |

### Verify Phase (find problems)

| Skill | What it does |
|---|---|
| `/verify` | 124 DFM + 9 DFA + 24 JLCPCB + connectivity |
| `/drc-native` | KiCad DRC with smart filtering + baseline delta |
| `/drc-audit` | Full electrical classification (shorts, unconnected, dangling) |
| `/pcb-review` | 8-domain 100-point scored review |
| `/datasheet-verify` | 267 pin-to-net checks vs component datasheets |
| `/design-intent` | 357 cross-source adversary (GPIO, power, signal chains) |
| `/pad-analysis` | Pad spacing distance table |
| `/jlcpcb-alignment` | IC/connector rotation + position vs CPL |
| `/jlcpcb-validate` | 24 JLCPCB-specific manufacturing rules |
| `/dfm-test` | DFM regression guard test generator |
| `/pcb-optimize` | 5-module 100-point layout optimization score |

### Fix Phase (resolve issues)

| Skill | What it does |
|---|---|
| `/dfm-fix` | Fix DFM violations from report + add guard test |
| `/fix-rotation` | Fix CPL rotation for JLCPCB assembly |
| `/jlcpcb-check` | Check 3D alignment for a specific component |
| `/jlcpcb-parts` | Check BOM stock + find alternative LCSC parts |

### Release Phase (ship to fab)

| Skill | What it does |
|---|---|
| `/release-prep` | Quick: generate + verify + gerbers + sync release_jlcpcb/ |
| `/release` | Manual: prepare release without auto-commit |
| `/full-release` | Complete: all verify + renders + gerbers + commit + tag |

### Audit Phase (deep review)

| Skill | What it does |
|---|---|
| `/hardware-audit` | Layer 1 (22 automated gates) + Layer 2 (8-domain prose) |
| `/electrical-review` | Strapping + decoupling + power sequence + SPICE |

### Firmware / Docs

| Skill | What it does |
|---|---|
| `/pcb-to-firmware` | Propagate PCB changes to board_config.h + docs |
| `/firmware-build` | Build/flash ESP-IDF firmware via Docker |
| `/firmware-sync` | Verify GPIO match between config.py and board_config.h |
| `/hardware-test-gen` | Regenerate/build/run the bring-up firmware from `board_config.h` |
| `/doc` | Audit docs vs source-of-truth, fix outdated values |
| `/website-dev` | Build/deploy Docusaurus site |

### Audit & Meta

| Skill | What it does |
|---|---|
| `/hardware-audit` | Layer 1 automated gates + Layer 2 domain-by-domain prose review |
| `/electrical-review` | Strapping + decoupling + power sequence + SPICE |
| `/isolation-check` | Every conductor connected where intended, isolated everywhere else |
| `/external-dfm` | KiBot + Tracespace DFM analysis via Docker |
| `/first-article-check` | Pre-payment 3D-preview orientation check + photo-vs-render on arrival |
| `/pipeline-resume` | Resume an interrupted release pipeline |
| `/create-skill` | Author a new skill for this project |
| `/user-feedback` | Record user preferences and distribute them |
| `/memory-maintenance` | Audit and condense the persistent project memory |

### CAD

| Skill | What it does |
|---|---|
| `/enclosure-design` | OpenSCAD parametric enclosure design |
| `/enclosure-render` | Render enclosure PNG views via Docker |
| `/enclosure-export` | Export STL for 3D printing |

---

## Lifecycle Commands (composed workflows)

| Command | Composes | Use when |
|---|---|---|
| `/design-pcb` | schematic -> board -> components -> routing | New PCB or major redesign |
| `/generate-pcb` | generate -> check | After any design change |
| `/verify-pcb` | verify -> drc -> audit -> pad -> jlcpcb -> datasheet -> intent -> review | Before release |
| `/fix-pcb` | dfm-fix -> fix-rotation -> jlcpcb-check -> jlcpcb-parts | After verify failures |
| `/release-pcb` | full-release (verify + render + gerbers + commit) | Ship to JLCPCB |
| `/bootstrap-new-pcb` | scaffold new project | Starting fresh |

---

## Source of Truth Hierarchy

![Source of truth hierarchy: config.py down to the generated .kicad_pcb and .kicad_sch](/img/diagrams/wf-source-of-truth.svg)

**Rule**: changes flow DOWN this hierarchy. Never edit `.kicad_pcb` directly. Never let `board_config.h` drive `config.py`. Use `/pcb-to-firmware` to propagate changes downward.

---

## Hooks (Auto-Triggers)

These run automatically — no manual invocation needed:

| When | What happens |
|---|---|
| Every prompt | Skill suggestions based on keywords |
| Before any Edit/Write | Blocks direct .kicad_pcb edits |
| After `generate_pcb` or `release` | Reminds to run `verify_dfa.py` |
| After any PCB file edit | Reminds to run DFA verification |
| Before context compaction | Saves session backup |
| After Claude stops responding | Auto-runs DFM if PCB files changed |

---

## Agent Coordination Examples

### Example 1: "Add battery voltage monitoring"

```
User -> team-lead:
  "Add battery voltage ADC reading to the design"

team-lead dispatches:
  1. pcb-engineer: add R divider on BAT+ → GPIO (ADC2 channel)
     -> /pcb-schematic (add R divider to power sheet)
     -> /pcb-components (place 2x 0805 resistors)
     -> /pcb-routing (route divider to ESP32 ADC pin)
     -> /generate + /verify

  2. software-dev: add ADC reading to firmware
     -> /pcb-to-firmware (sync new GPIO)
     -> edit power.c (add adc_oneshot_read)
     -> /firmware-build (verify compilation)

  3. cad-engineer: no changes needed (no new external component)
```

### Example 2: "The display doesn't work"

```
User -> /hardware-audit

Layer 1 gates run → all PASS
Layer 2 Step 3 (Display) investigates:
  - LCD_D0-D7 routing vs J4 FPC pinout
  - LCD_WR clock frequency vs ILI9488 datasheet
  - Backlight current path
  - FPC connector orientation

Finding: LCD_RD tied to wrong voltage → fix in routing.py
  -> /dfm-fix
  -> /generate-pcb
  -> /verify-pcb
  -> /release-pcb
```

### Example 3: "JLCPCB says my gerbers have DFM issues"

```
User uploads JLCDFM report PDF

1. Read the report (OCR if needed)
2. Categorize findings:
   - Trace spacing → /dfm-fix
   - Pin alignment → /fix-rotation or /jlcpcb-check
   - Parts stock → /jlcpcb-parts check
   - Silk overlap → move gr_text in board.py
3. /generate-pcb (regen)
4. /verify-pcb (confirm fix)
5. /release-pcb (new gerbers)
6. Re-upload to JLCDFM and confirm
```
