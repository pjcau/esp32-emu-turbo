---
description: Complete JLCPCB release pipeline — verify → gerbers → BOM/CPL → render → git commit. Composes /full-release (or /release-prep for quick-path).
---

# Release PCB (lifecycle phase: Release)

Produce a production-ready JLCPCB manufacturing package. Never skip steps.

## Full release (recommended)

```
/full-release
```

This runs the complete pipeline:
1. `/generate` — regenerate from Python sources
2. `/verify` — 115 DFM + 9 DFA + 26 JLCPCB tests
3. `/drc-native` — KiCad native DRC
4. `/render` — SVG layers + animation
5. `/pcba-render` — photorealistic 3D PCBA (top, bottom, iso, detail)
6. Export gerbers via `kicad-cli` + zone fill
7. Generate BOM.csv + CPL.csv with JLCPCB formatting
8. Copy all artifacts to `release_jlcpcb/`
9. Update individual gerber files in `release_jlcpcb/gerbers/`
10. Commit + push with version tag

## Quick release (no renders)

```
/release-prep
```

Same as above but skips rendering steps (~30s vs ~3min).

## Manual release (advanced)

```
/release
```

Prepare release package without auto-commit. Use when you want to review artifacts before pushing.

## Pre-release checklist

Before running any release command, verify:

- [ ] `git status` is clean (or only expected WIP)
- [ ] `/verify-pcb` passes with 0 failures
- [ ] `memory/dfm-state.md` reflects current baseline
- [ ] No unresolved TODOs in `hardware-audit-bugs.md`
- [ ] `website/docs/` is synced with source-of-truth (`/doc`)

## Post-release

- Verify `release_jlcpcb/gerbers.zip` opens correctly
- Upload to JLCPCB and confirm DFM passes
- Tag the commit with the release version
- Update `website/docs/manufacturing.md` if changed

## Critical rules

- NEVER commit `release_jlcpcb/` changes separately from PCB changes — they must move together.
- EVERY commit that touches `hardware/kicad/` or `scripts/generate_pcb/` MUST update `release_jlcpcb/`.
- Check with `git diff --stat` before committing.
