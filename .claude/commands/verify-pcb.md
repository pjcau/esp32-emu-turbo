---
description: Full PCB verification pipeline — DFM, DFA, DRC, pad analysis, JLCPCB rules, datasheet cross-check. Composes /verify → /drc-native → /drc-audit → /pcb-review → /datasheet-verify → /jlcpcb-validate.
---

# Verify PCB (lifecycle phase: Verify)

Run the full verification suite. All checks must pass before release.

## Steps

1. **DFM + DFA suite** — `/verify`
   - `python3 scripts/verify_dfm_v2.py` — 115 manufacturing tests (pad spacing, clearance, drill sizes, soldermask, silkscreen, copper pours, trace widths)
   - `python3 scripts/verify_dfa.py` — 9 assembly tests (component polarity, tombstone risk, solderability)

2. **Native DRC** — `/drc-native`
   - `kicad-cli pcb drc` with JLCPCB `.kicad_dru` rules.
   - Baseline-aware: fails only on new violations.

3. **Electrical audit** — `/drc-audit`
   - Shorts, unconnected pads, dangling vias, net continuity.

4. **Pad analysis** — `/pad-analysis`
   - Pad-to-pad spacing (net-aware), THT-to-SMD clearance.

5. **JLCPCB validation** — `/jlcpcb-validate`
   - Drill sizes, edge clearance, copper-to-edge, gerber file sanity.
   - 26 JLCPCB-specific rules.

6. **Alignment** — `/jlcpcb-alignment`
   - Batch pin alignment check for fine-pitch parts.

7. **Datasheet cross-check** — `/datasheet-verify`
   - Pinouts and physical dimensions against manufacturer datasheets.

8. **Design intent adversary** — `/design-intent`
   - 18-test cross-source adversary: verifies schematic intent matches PCB realization.

9. **Review scoring** — `/pcb-review`
   - 8-domain scored review (routing quality, layout, manufacturability, thermal, EMI, testability, mechanical, docs).

## Output

On full pass:
```
✓ 115 DFM tests passed
✓ 9 DFA tests passed
✓ 0 DRC violations (baseline)
✓ 26 JLCPCB rules passed
✓ Review score: ≥95/100
```

## When to use

- Before every commit that changes PCB files
- Before `/release-pcb`
- After `/fix-pcb` to confirm the fix

## Critical rules

- NEVER silence a failing test. If a test fails, either fix the underlying issue or update the baseline with documented justification.
- Follow the project rule: every fix must have a guard test.
