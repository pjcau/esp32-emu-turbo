---
name: generate
description: Run the full PCB generation pipeline (generate + zone fill + gerbers + release package)
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Full PCB Generation Pipeline

Run the complete ESP32-emu-turbo PCB generation pipeline end-to-end.

## Steps

### 1. Generate PCB + BOM + CPL from Python specs

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

This generates:
- `hardware/kicad/esp32-emu-turbo.kicad_pcb` (PCB layout)
- `hardware/kicad/jlcpcb/bom.csv` (Bill of Materials)
- `hardware/kicad/jlcpcb/cpl.csv` (Component Placement List)

### 2. Fill zones via Docker (KiCad Python API)

```bash
docker compose run --rm --entrypoint python3 kicad-pcb /scripts/kicad_fill_zones.py "/project/esp32-emu-turbo.kicad_pcb"
```

This fills copper zones (In1.Cu=GND plane, In2.Cu=3V3/5V planes) and preserves orphan nets (USB_CC1/CC2).

### 3. Export Gerbers + drill files via Docker

```bash
docker compose run --rm kicad-pcb pcb export gerbers \
    --output /gerbers/ \
    --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
    --subtract-soldermask --use-drill-file-origin \
    "/project/esp32-emu-turbo.kicad_pcb"

docker compose run --rm kicad-pcb pcb export drill \
    --output /gerbers/ --format excellon --drill-origin plot \
    --excellon-units mm --generate-map --map-format gerberx2 \
    "/project/esp32-emu-turbo.kicad_pcb"
```

### 4. Create gerbers.zip for JLCPCB

```bash
cd hardware/kicad/gerbers
zip -j ../jlcpcb/gerbers.zip *.gtl *.g1 *.g2 *.gbl *.gto *.gbo *.gts *.gbs *.gtp *.gbp *.gm1 *.drl *.gbrjob 2>/dev/null
```

### 5. Copy to release_jlcpcb/

```bash
cp hardware/kicad/jlcpcb/bom.csv release_jlcpcb/bom.csv
cp hardware/kicad/jlcpcb/cpl.csv release_jlcpcb/cpl.csv
rm -rf release_jlcpcb/gerbers
cp -r hardware/kicad/gerbers release_jlcpcb/gerbers
cp hardware/kicad/jlcpcb/gerbers.zip release_jlcpcb/gerbers.zip
```

### 6. Run verification

After the pipeline completes, run the DFM verification:

```bash
python3 scripts/verify_dfm_v2.py
```

Report results as a summary table.

## Important Notes

- Always run from the project root: `/Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo`
- Zone fill MUST run before gerber export (internal copper planes would be empty otherwise)
- The kicad_fill_zones.py preserves orphan nets (USB_CC1, USB_CC2) that pcbnew would normally strip
- If Docker is not running, start it first with `docker compose build`

## Key Files

- Pipeline entry: `scripts/generate_pcb/__init__.py` → calls `generate_board()` + `export_cpl()`
- Board layout: `scripts/generate_pcb/board.py`
- Routing: `scripts/generate_pcb/routing.py`
- Footprints: `scripts/generate_pcb/footprints.py`
- JLCPCB export: `scripts/generate_pcb/jlcpcb_export.py`
- Zone fill: `scripts/kicad_fill_zones.py`
- Gerber export: `scripts/export-gerbers.sh`
