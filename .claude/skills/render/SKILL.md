---
name: render
model: claude-opus-4-7
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
# Generate + FILL + refresh Net Explorer, then render SVG/PNG/GIF
make render-pcb
```

**Use the make target — do not call the renderers directly.**
`generate_pcb` writes the `.kicad_pcb` with no `filled_polygon` (the fill
needs the `pcbnew` Python API, which `kicad-cli` does not expose), so a
render taken straight after a bare generate shows **a board with no copper
pours** — and those images ship to the website. `render-pcb` depends on
`pcb-filled` (`generate-pcb` → `scripts/fill-zones.sh` → Net Explorer
refresh), which is what makes the fill unskippable.

Two other symptoms of the same cause, in case you see them: the zone-fill
gate going red after a documentation-only action, and the pre-commit DFM
hook blocking a commit while citing zone fills that have nothing to do with
the change being committed.

If you must run a renderer by hand, fill first:

```bash
make pcb-filled
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
