---
name: render
description: Run the Docker rendering pipeline (schematics, PCB, enclosure)
disable-model-invocation: true
allowed-tools: Bash, Read, Glob
argument-hint: [all|schematics|pcb|enclosure]
---

# Docker Rendering Pipeline

Render project assets via Docker containers.

**Argument** (optional): `all` (default), `schematics`, `pcb`, or `enclosure`.

## Prerequisites

Ensure Docker is running and images are built:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
docker compose build
```

## Render Commands

### Schematics (KiCad schematic → SVG/PDF)

```bash
# Generate schematics from Python specs
docker compose run --rm generate-sch

# Export to SVG
./scripts/render-schematics.sh
```

Output: `website/static/img/schematics/*.svg`

### PCB (layout visualization)

```bash
# Generate PCB from Python specs
python3 -m scripts.generate_pcb hardware/kicad

# Render SVG + PNG + animated GIF
python3 scripts/render_pcb_svg.py website/static/img/pcb
python3 scripts/render_pcb_animation.py website/static/img/pcb
```

Output: `website/static/img/pcb/`

### Enclosure (OpenSCAD → PNG)

```bash
./scripts/render-enclosure.sh
```

Output: `website/static/img/renders/` (7 views: front, back, top, exploded, cross-section, fit-check, pcb)

### All

```bash
make render-all
```

## Post-render

After rendering, check that outputs exist:

```bash
ls -la website/static/img/schematics/*.svg
ls -la website/static/img/pcb/*.svg
ls -la website/static/img/renders/*.png
```

## Key Files

- `scripts/render-all.sh` — Master orchestration
- `scripts/render-schematics.sh` — Schematic SVG export
- `scripts/render-enclosure.sh` — OpenSCAD rendering
- `scripts/render_pcb_svg.py` — PCB SVG visualization
- `scripts/render_pcb_animation.py` — PCB GIF animation
- `docker-compose.yml` — Docker service definitions
