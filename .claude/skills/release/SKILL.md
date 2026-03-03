---
name: release
description: Prepare a complete JLCPCB release package with version notes
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: <version> (e.g. v1.9)
---

# Prepare JLCPCB Release Package

Create a production-ready release package for JLCPCB manufacturing.

**Argument**: Version tag (e.g., `v1.9`).

## Steps

### 1. Run full generation pipeline

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

### 2. Zone fill + gerber export (fast: local kicad-cli + Docker zone fill)

```bash
./scripts/export-gerbers-fast.sh
```

Or via full Docker:
```bash
docker compose run --rm --entrypoint python3 kicad-pcb /scripts/kicad_fill_zones.py "/project/esp32-emu-turbo.kicad_pcb"
docker compose run --rm kicad-pcb pcb export gerbers --output /gerbers/ --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" --subtract-soldermask --use-drill-file-origin "/project/esp32-emu-turbo.kicad_pcb"
docker compose run --rm kicad-pcb pcb export drill --output /gerbers/ --format excellon --drill-origin plot --excellon-units mm --generate-map --map-format gerberx2 "/project/esp32-emu-turbo.kicad_pcb"
```

### 3. Run all verification

```bash
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_dfa.py
python3 scripts/drc_check.py
python3 scripts/test_pcb_connectivity.py
python3 scripts/verify_schematic_pcb.py
```

**ALL tests must pass before proceeding (64 DFM + 9 DFA + DRC + connectivity + schematic sync).** If any fail, fix the issues first.

The DFM suite includes batch JLCPCB alignment checks (rotation, position correction, and pin-net assignment for all 7 bottom-side ICs/connectors).

### 4. Copy to release_jlcpcb/

```bash
cp hardware/kicad/jlcpcb/bom.csv release_jlcpcb/bom.csv
cp hardware/kicad/jlcpcb/cpl.csv release_jlcpcb/cpl.csv
rm -rf release_jlcpcb/gerbers
cp -r hardware/kicad/gerbers release_jlcpcb/gerbers
cd hardware/kicad/gerbers && zip -j ../../release_jlcpcb/gerbers.zip *.gtl *.g1 *.g2 *.gbl *.gto *.gbo *.gts *.gbs *.gtp *.gbp *.gm1 *.drl *.gbrjob 2>/dev/null
```

### 5. Update release README

Edit `release_jlcpcb/README.md`:
- Add version header with date
- List all changes since last version
- Include verification results summary
- Include component count and cost estimate

### 6. Create git commit

Stage and commit all release files:
```bash
git add release_jlcpcb/ hardware/kicad/esp32-emu-turbo.kicad_pcb
git commit -m "Update release_jlcpcb/ to $VERSION with [summary of changes]"
```

### 7. Print JLCPCB upload instructions

After release is ready, print:
- Go to https://cart.jlcpcb.com/quote
- Upload `release_jlcpcb/gerbers.zip`
- Select 4-layer, 1.6mm, ENIG/HASL
- Enable PCBA: upload `bom.csv` and `cpl.csv`
- Verify 3D viewer alignment for all components
- Check component count matches BOM (21 unique parts, 64 placements)

## Key Files

- `release_jlcpcb/README.md` — Release notes
- `release_jlcpcb/gerbers.zip` — Gerber package
- `release_jlcpcb/bom.csv` — Bill of Materials
- `release_jlcpcb/cpl.csv` — Component Placement List
- `release_jlcpcb/gerbers/` — Individual gerber files
