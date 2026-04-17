---
name: external-dfm
model: claude-opus-4-7
description: Run external DFM analysis using KiBot (DRC/ERC/design report) and Tracespace (gerber validation) via Docker. Use after internal verify passes to get a second opinion from third-party tools.
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# External DFM Analysis (KiBot + Tracespace)

Run third-party CLI tools in Docker for independent PCB verification — a "second opinion" beyond the internal verify suite.

## What it checks

| Tool | Checks | Output |
|------|--------|--------|
| **KiBot DRC** | KiCad native DRC with zone fill | `external-dfm-output/esp32-emu-turbo-drc.json` |
| **KiBot ERC** | Electrical rule check on schematics | `external-dfm-output/esp32-emu-turbo-erc.json` |
| **KiBot Report** | Full design report (traces, vias, pads, Eurocircuits class) | `external-dfm-output/*report*.txt` |
| **KiBot BOM** | Independent BOM generation for cross-check | `external-dfm-output/bom-kibot.csv` |
| **Tracespace** | Gerber file parsing and structural validation | `external-dfm-output/tracespace.log` |
| **BOM Cross-ref** | Compare KiBot BOM vs JLCPCB BOM designators | Inline in output |

## Steps

### 1. Run external analysis

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
bash scripts/external-dfm.sh
```

This builds the Docker container (first run ~2-3 min, then cached) and runs all checks.

### 2. Review output files

If the script reports issues, inspect the detailed output:

```bash
# KiBot DRC violations (JSON)
cat hardware/kicad/external-dfm-output/esp32-emu-turbo-drc.json | python3 -m json.tool

# KiBot ERC violations (JSON)  
cat hardware/kicad/external-dfm-output/esp32-emu-turbo-erc.json | python3 -m json.tool

# Full design report
cat hardware/kicad/external-dfm-output/*report*.txt

# KiBot log (full output)
cat hardware/kicad/external-dfm-output/kibot.log
```

### 3. Interpret results

**DRC violations** — Compare against internal `verify_dfm_v2.py` results. New violations from KiBot that internal scripts missed are the most valuable findings.

**ERC violations** — Schematic-level issues (missing connections, power flags, pin conflicts). These are NOT checked by internal scripts.

**Design report** — Look for:
- Eurocircuits producibility class (target: 10F or better)
- Track width/spacing statistics
- Via/drill summary
- Pad count and types

**BOM mismatch** — Components present in schematic but missing from JLCPCB BOM (or vice versa).

## Key files

- `scripts/external-dfm.sh` — Runner script
- `hardware/kicad/external-dfm.kibot.yaml` — KiBot configuration
- `docker/kibot/Dockerfile` — Docker image definition
- `hardware/kicad/external-dfm-output/` — All output (gitignored)

## Makefile target

```bash
make external-dfm
```
