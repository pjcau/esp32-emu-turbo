---
name: hardware-audit
model: claude-opus-5
description: Deep electrical/functional audit of the ESP32 Emu Turbo hardware design. Finds bugs that prevent power-on, component operation, or emulator functionality. Cross-checks schematics, PCB, datasheets, and firmware via automated gates + manual domain-by-domain review.
disable-model-invocation: false
allowed-tools: Bash, Read, Edit, Grep, Glob, Agent, Write
---

# Hardware Functional Audit

Iterative deep-dive to find electrical, connectivity, and functional bugs
that would prevent the device from working.

## Audit Philosophy

This audit has two layers and BOTH must run:

1. **Layer 1 — Automated gates (Step 0)**: objective geometric, electrical,
   and cross-source checks. An LLM cannot find a 0.02 mm trace-through-pad
   overlap by reading schematics, so this layer runs real scripts against
   the parsed `.kicad_pcb` cache. All gates must PASS before Layer 2.
2. **Layer 2 — Domain-by-domain reasoning (Steps 1-8)**: prose review of
   each functional domain using datasheets, schematic generators, and
   firmware source. This is what an LLM does well: spotting logical
   inconsistencies, wrong component selection, pinout mismatches, boot
   sequence issues, and ambiguities between documentation and code.

Historical context: prior rounds of this audit (R1-R4) relied only on
Layer 2 and never caught the v3.3 trace-through-pad regression from
commit 775e9fd — because the bugs lived in cache geometry, not prose.
Layer 1 was added in 2026-04-10 to close that gap.

## Step 0 — Automated gates (HARD BLOCK if any fail)

Run the full gate suite. If ANY of these fail, STOP and fix before
attempting the manual domain review — a board with a geometric short,
a broken power chain, or a drifted schematic is not worth auditing in
prose.

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo

# ── Fab-short gate (MOST IMPORTANT) ──────────────────────────────
# Catches netted traces physically crossing unnetted pads (the v3.3
# regression class). Checks F.Cu and B.Cu.
python3 scripts/verify_trace_through_pad.py        # MUST be "1 passed, 0 failed"

# ── Trace-crossings gate (R9-CRIT-1 class) ──────────────────────
# Catches two traces on the SAME copper layer belonging to DIFFERENT
# nets whose capsules overlap — the physical-short class that
# verify_trace_through_pad.py does not see because it only checks
# trace-vs-pad. Missing this gate caused the R7/R8 BTN_START bridge
# to cross LCD_CS/DC/WR without anyone noticing.
python3 scripts/verify_trace_crossings.py          # MUST be "1 passed, 0 failed"

# ── Copper-clearance gate (R13 class) ───────────────────────────
# Shapely polygon-based check: for each copper layer, merges all
# features per net and measures min polygon distance between every
# different-net pair. Reports any gap < 0.10mm as DANGER and
# 0.10-0.15mm as WARN (JLCPCB preferred minimum, what JLCDFM uses
# as Warning threshold). Catches the 0.110-0.145mm track-to-pad
# gaps that KiCad DRC misses because .kicad_dru is tuned to the
# 0.09mm absolute minimum. JLCDFM measures mask-aperture-to-mask-
# aperture, subtracting ~0.05mm mask expansion per side, so a
# 0.110mm copper-edge gap becomes ~0.010mm on JLCDFM's view and
# gets flagged as Danger.
python3 scripts/verify_copper_clearance.py         # MUST be "0 DANGER"

# ── Per-net copper connectivity (R5-CRIT class) ─────────────────
# Walks the per-net copper graph and asserts every net forms a
# single connected component. Catches R5-CRIT-1..9 bugs where
# pad-net labels are correct but copper is fragmented (BAT+ L1.1
# isolated, VBUS decoupling floating, button pull-ups disconnected,
# SW_BOOT non-functional, etc). Missing this gate caused R5 bugs
# to ship undetected in v3.3.
python3 scripts/verify_net_connectivity.py         # MUST be "0 failed"

# ── DFM / DFA / JLCPCB manufacturing ─────────────────────────────
python3 scripts/verify_dfm_v2.py                   # 122 tests (incl zone fill + silk-to-pad)
python3 scripts/verify_dfa.py                      #   9 tests
python3 scripts/validate_jlcpcb.py                 #  24 tests
python3 scripts/verify_bom_cpl_pcb.py              #  12 checks (incl field completeness)
python3 scripts/verify_polarity.py                 #  48 tests

# ── JLCPCB official capabilities + stencil + drill ──────────────
python3 scripts/verify_jlcpcb_capabilities.py      #  12 tests (JLCPCB published limits)
python3 scripts/verify_stencil_aperture.py         #   6 tests (IPC-7525 stencil analysis)
python3 scripts/verify_drill_standards.py          #   6 tests (ISO metric + drill-to-pad ratio)

# ── Datasheet pinout + physical verification ─────────────────────
python3 scripts/verify_datasheet_nets.py           # 267 pin→net checks
python3 scripts/verify_datasheet.py                #  29 physical tests

# ── Cross-source consistency (schematic ↔ PCB ↔ firmware) ────────
python3 scripts/verify_design_intent.py            # 369 checks, T1-T22
python3 scripts/verify_schematic_pcb_sync.py       # R4 sync guard
python3 scripts/verify_netlist_diff.py             # schematic-PCB netlist diff
python3 scripts/generate_board_config.py --check   # config.py vs board_config.h

# ── Electrical review (power + boot) ─────────────────────────────
python3 scripts/verify_strapping_pins.py           #  12 tests
python3 scripts/verify_decoupling_adequacy.py      #  23 tests
python3 scripts/verify_power_sequence.py           #  29 tests
python3 scripts/verify_power_paths.py              #  19 tests

# ── KiCad native ERC + DRC ───────────────────────────────────────
python3 scripts/erc_check.py --run                 # schematic ERC
kicad-cli pcb drc \
  --output /tmp/drc_audit_report.json \
  --format json \
  --severity-all --units mm --all-track-errors \
  hardware/kicad/esp32-emu-turbo.kicad_pcb
# DRC: 0 shorting_items (real), 0 via_dangling, 0 unconnected_items
```

Gate summary to report back to the user:

| Gate | Expected | Actual | Status |
|------|----------|--------|--------|
| Fab shorts (`verify_trace_through_pad`) | 0 overlaps | ? | PASS/FAIL |
| Trace crossings (`verify_trace_crossings`) | 0 crossings | ? | PASS/FAIL |
| Copper clearance (`verify_copper_clearance`) | 0 DANGER | ? | PASS/FAIL |
| DFM (`verify_dfm_v2`) | 122/122 | ? | PASS/FAIL |
| DFA (`verify_dfa`) | 9/9 | ? | PASS/FAIL |
| Polarity (`verify_polarity`) | 48/48 | ? | PASS/FAIL |
| Datasheet nets (`verify_datasheet_nets`) | 267/267 | ? | PASS/FAIL |
| Datasheet physical (`verify_datasheet`) | 29/29 | ? | PASS/FAIL |
| Design intent (`verify_design_intent`) | 369/369 | ? | PASS/FAIL |
| R4 sync guard (`verify_schematic_pcb_sync`) | PASS | ? | PASS/FAIL |
| Netlist diff (`verify_netlist_diff`) | 4/4 | ? | PASS/FAIL |
| Strapping pins (`verify_strapping_pins`) | 12/12 | ? | PASS/FAIL |
| Decoupling adequacy (`verify_decoupling_adequacy`) | 23/23 | ? | PASS/FAIL |
| Power sequence (`verify_power_sequence`) | 29/29 | ? | PASS/FAIL |
| Power paths (`verify_power_paths`) | 19/19 | ? | PASS/FAIL |
| ERC (`erc_check`) | 0 critical | ? | PASS/FAIL |
| KiCad DRC | 0 shorts, 0 dangling | ? | PASS/FAIL |

**RULE**: If any gate fails, stop and write the failure into
`hardware-audit-bugs.md` as the first bug of the new round. Do not
proceed to Layer 2 prose review until Layer 1 is clean OR the user
explicitly asks for a prose-only review acknowledging the gate failure.

## Layer 2 — domain-by-domain review (Steps 1–8)

After Layer 1 is clean, audit each domain in prose. The per-domain
check lists (power chain, ESP32 boot, display, audio, SD, buttons,
USB, emulator performance) live in
`references/domain-checks.md` — read one domain at a time while
working it, then move to the next. Each list names the sources to
cross-check and the as-built limitations that must NOT be re-raised
(EN without RC, SW_PWR not in series, backlight R25-HIGH-1,
J4's 41−N pin reversal).

## Report format

Write findings to `hardware-audit-bugs.md` under a new section
`## Round N Findings (YYYY-MM-DD)`. Include:

```markdown
### Step 0 gates
| Gate | Result |
|------|--------|
| verify_trace_through_pad | ... |
| verify_dfm_v2 | ... |
...

### Domain findings
- **Power chain**: N findings
- **ESP32 boot**: N findings
- **Display**: N findings
- **Audio**: N findings
- **SD card**: N findings
- **Buttons**: N findings
- **USB**: N findings
- **Emulator performance**: N findings

### Bug list
#### R{N}-CRIT-{i} — {title}
- **Files**: ...
- **Problem**: ...
- **Root cause**: ...
- **Fix**: ...

#### R{N}-HIGH-{i} — ...
#### R{N}-MED-{i}  — ...
#### R{N}-LOW-{i}  — ...
```

Severity guide:
- **CRIT** — board will not power on, or a component will be destroyed
- **HIGH** — a functional block (display, audio, SD, USB) will not work
- **MED**  — intermittent failure or degraded performance
- **LOW**  — cosmetic, documentation, or not-yet-exercised feature

## Key Files

- `scripts/verify_trace_through_pad.py` — fab-short hard gate
- `scripts/verify_dfm_v2.py` — DFM (122 tests)
- `scripts/verify_datasheet_nets.py` — pin→net (267 checks)
- `scripts/verify_design_intent.py` — cross-source (369 checks)
- `scripts/verify_schematic_pcb_sync.py` — R4 sync guard
- `scripts/verify_strapping_pins.py` — ESP32 boot gate
- `scripts/verify_decoupling_adequacy.py` — per-IC cap check
- `scripts/verify_power_sequence.py` — power chain topology
- `scripts/verify_power_paths.py` — copper path tracing
- `scripts/erc_check.py` — KiCad native ERC
- `scripts/generate_schematics/sheets/` — schematic generator (all sheets)
- `scripts/generate_pcb/routing/` — PCB trace routing
- `hardware/datasheet_specs.py` — component pin→net single source of truth
- `software/main/board_config.h` — firmware GPIO config
- `hardware/datasheets/` — component datasheets
- `hardware-audit-bugs.md` — output: historical audit findings
