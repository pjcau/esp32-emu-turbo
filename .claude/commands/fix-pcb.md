---
description: Fix DFM/DFA/DRC violations — rotation, JLCPCB alignment, parts sourcing, general DFM fixes. Composes /dfm-fix → /fix-rotation → /jlcpcb-check → /jlcpcb-parts.
---

# Fix PCB (lifecycle phase: Fix)

Apply targeted fixes to resolve verification failures. Always regenerate and re-verify after each fix.

## Skills by failure category

| Failure type | Skill | Fix strategy |
|---|---|---|
| Pad spacing, trace clearance, drill-to-trace | `/dfm-fix` | Shift vias/traces, adjust clearance, respect net-aware rules |
| Wrong rotation in CPL | `/fix-rotation` | Apply JLCPCB rotation delta to CPL footprint entries |
| 3D model misalignment, footprint mismatch | `/jlcpcb-check` | Validate 3D model vs footprint, correct origin offsets |
| LCSC part unavailable / wrong package | `/jlcpcb-parts` | Search LCSC catalog via EasyEDA API, swap BOM line |

## Fix-and-verify loop

```
1. Parse failing tests → identify root cause
2. Filter same-net false positives
3. Apply fix via appropriate skill
4. Regenerate: /generate-pcb
5. Verify: /verify-pcb
6. If still failing: loop back to step 1
7. If all pass: commit with guard test reference
```

## DFM fix priorities

From memory and past incidents:

1. **Same-net false positives** — filter before fixing anything (`analyze_pad_distances.py` does not auto-filter).
2. **Via-in-pad** — move via ≥1mm from pad center.
3. **FPC approach vias** — offset from pad edges, not centered.
4. **MH clearance** — 3.5mm pad needs ≥2mm to nearest SMD.
5. **Via-to-via** — hole-to-hole gap ≥0.25mm.
6. **Drill-to-trace** — ≥0.15mm from different-net traces.

## After fixing

Mandatory:
1. `/verify-pcb` — confirm fix
2. Update `memory/dfm-state.md` if a new pattern was discovered
3. Add a guard test in `scripts/verify_dfm_v2.py` if the fix prevents a new class of bug
4. Commit with reference to the failing test and the fix

## Critical rules

- NEVER commit a fix without regenerating and re-verifying.
- NEVER silence a test. If the test is wrong, fix the test with justification.
- Always check `memory/feedback_never_silence_errors.md` before touching a test assertion.
