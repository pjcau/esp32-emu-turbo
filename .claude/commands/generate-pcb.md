---
description: Regenerate .kicad_pcb and .kicad_sch from Python sources, then run quick DFM/DFA verification. Composes /generate → /check.
---

# Generate PCB (lifecycle phase: Generate)

Regenerate all KiCad files from the Python generator pipeline and run quick verification.

## Steps

1. **Regenerate schematics**
   ```bash
   python3 -m scripts.generate_schematics hardware/kicad
   ```
   Emits 7 sheets (01-power-supply, 02-mcu, 03-display, 04-audio, 05-sd-card, 06-controls, + root).

2. **Regenerate PCB** — `/generate`
   ```bash
   python3 -m scripts.generate_pcb hardware/kicad
   ```
   Emits `hardware/kicad/esp32-emu-turbo.kicad_pcb` with all footprints, traces, vias, zones.

3. **Quick check** — `/check`
   Runs DFM quick-check + 3D alignment + gerber sanity in one pass (~5s with local kicad-cli).

## After generation

- On pass → `/verify-pcb` for full verification, or `/release-pcb` for final release.
- On fail → `/fix-pcb` with the failing rule reference.

## When to use

- After any edit to `scripts/generate_schematics/*.py` or `scripts/generate_pcb/*.py`
- Before committing any PCB change
- Before `/release-pcb`

## Critical rules

- Never commit stale `.kicad_pcb` that doesn't match current Python sources — run this command first.
- If schematics regeneration touches existing `.kicad_sch`, docs may also be out of sync → run `/doc`.
