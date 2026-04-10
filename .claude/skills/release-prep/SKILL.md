---
name: release-prep
description: Quick release pipeline — generate, verify, export gerbers, copy to release folder (no git commit)
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Release Prep — Quick Pipeline

Fast release preparation without git commit or version notes. Use `/release` for full versioned releases.

## Pipeline

### 1. Generate PCB

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

### 2. Quick DFM check

```bash
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_trace_through_pad.py
```

If any test FAILS, stop and report. Do NOT continue to gerber export with failing tests.

`verify_trace_through_pad.py` is a hard gate against the v3.3 regression
class: a netted trace physically running through an unnetted pad creates
a real short on the fabricated board that DFM and DRC do not both catch
when pad net assignments are missing. Any failure here means a missing
entry in `scripts/generate_pcb/routing.py::_PAD_NETS`.

### 3. Export gerbers (local kicad-cli + Docker zone fill)

```bash
./scripts/export-gerbers-fast.sh
```

If Docker/OrbStack is not available, skip this step and note it in the summary.

### 4. Copy to release folder

```bash
cp hardware/kicad/jlcpcb/bom.csv release_jlcpcb/bom.csv
cp hardware/kicad/jlcpcb/cpl.csv release_jlcpcb/cpl.csv
rm -rf release_jlcpcb/gerbers
cp -r hardware/kicad/gerbers release_jlcpcb/gerbers
cp hardware/kicad/jlcpcb/gerbers.zip release_jlcpcb/gerbers.zip 2>/dev/null || true
```

### 5. DFA verification (assembly checks)

```bash
python3 scripts/verify_dfa.py
```

If any test FAILS, stop and report. Assembly issues must be fixed before release.

### 6. Summary

| Step | Status | Detail |
|------|--------|--------|
| PCB generation | OK/FAIL | — |
| DFM tests (64) | X/Y pass | list failures |
| DFA tests (9) | X/Y pass | list failures |
| Gerber export | OK/SKIP | OrbStack required |
| Release copy | OK/FAIL | — |

**Next steps**: If all OK, use `/release <version>` to create a versioned release with git commit.

## Key Files

- `release_jlcpcb/` — Output directory
- `release_jlcpcb/bom.csv` — Bill of Materials
- `release_jlcpcb/cpl.csv` — Component Placement List
- `release_jlcpcb/gerbers/` — Gerber files
