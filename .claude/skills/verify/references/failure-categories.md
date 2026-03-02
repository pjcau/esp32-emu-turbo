# Verify Failure Categories

Quick reference for categorizing verification failures.
Adapted from osok/claude-code-startup test-runner failure categorization pattern.

## Failure Categories

| Category | Signs | Action |
|----------|-------|--------|
| **DFM violation** | Pad spacing, trace clearance, mask bridge | Fix in `scripts/generate_pcb/` Python scripts |
| **DFA violation** | Missing fiducials, wrong orientation, bad ref-des | Fix in `scripts/generate_pcb/` Python scripts |
| **DRC error** | Clearance, unconnected nets, short circuits | Fix routing/placement in Python scripts |
| **Script bug** | Python exception, parse error, missing import | Fix the failing script directly |
| **Regression** | Test that previously passed now fails | Check recent changes, revert if needed |
| **False positive** | Same-net overlap, intentional design choice | Add to known exceptions or adjust threshold |
| **Environment** | Docker not running, missing container, OrbStack issue | Check `docker context use orbstack` |
| **Stale cache** | Results don't match reality after PCB changes | Delete `.pcb_cache.json`, regenerate |

## Debug Process

1. **Read** the failure output carefully
2. **Categorize** using table above
3. **Locate** the root cause file:
   - DFM/DFA/DRC → `scripts/generate_pcb/*.py`
   - Script bug → the failing script itself
   - Environment → Docker/OrbStack config
4. **Fix** in the source Python script (never in .kicad_pcb directly)
5. **Regenerate** → `make generate-pcb`
6. **Re-verify** → `make verify-fast` or `make verify-all`
7. **Repeat** until all tests pass

## Common Fixes by Category

### DFM: Pad spacing too tight
```
→ Adjust component placement in placement.py (increase spacing)
→ Or adjust via positions in routing.py (offset from pads)
```

### DFA: Missing fiducial
```
→ Add fiducial in placement.py using place_fiducial()
```

### DRC: Unconnected net
```
→ Check routing.py for missing trace connection
→ Verify net names match between schematic and PCB
```

### Regression: Test broke after change
```
→ git diff to find what changed
→ Revert the specific change, re-verify
→ Apply fix differently to avoid regression
```

### False positive: Same-net flagged
```
→ Check if flagged pads share the same net
→ If yes, add to known exceptions in the test script
→ If no, it's a real violation — fix it
```
