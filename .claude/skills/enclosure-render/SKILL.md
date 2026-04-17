---
name: enclosure-render
model: claude-haiku-4-5-20251001
description: Render OpenSCAD enclosure views to PNG via Docker
disable-model-invocation: true
allowed-tools: Bash, Read, Glob
argument-hint: [all|front|back|top|exploded|cross-section|fit-check|pcb]
---

# Enclosure Rendering Pipeline

Render the OpenSCAD enclosure model to high-resolution PNG images via Docker.

**Argument** (optional): View to render. `all` (default), or a specific view name.

## Prerequisites

Docker must be running. Build the OpenSCAD image if not already built:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
docker compose build openscad
```

## Render All Views

```bash
./scripts/render-enclosure.sh
# or via Makefile:
make render-enclosure
```

This renders 7 views at 1920x1080 resolution to `website/static/img/renders/`.

## Available Views

| View | Part | Camera | Description |
|------|------|--------|-------------|
| `front` | assembly | 25,0,340 | Front 3/4 view, assembled |
| `back` | assembly | 205,0,20 | Back 3/4 view, assembled |
| `top` | assembly | 90,0,0 | Top-down view |
| `exploded` | exploded | 55,0,330 | Exploded with all components |
| `cross-section` | cross_section | 55,0,0 | XZ plane cut showing Z-stack |
| `fit-check` | fit_check | 30,0,340 | Bottom shell open-top view |
| `pcb` | pcb | 25,0,340 | PCB model only |

## Render a Single View

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo

docker compose run --rm openscad \
    -o "/output/enclosure/enclosure-front.png" \
    --imgsize "1920,1080" \
    --camera "0,0,12.5,25,0,340,500" \
    -D 'part="assembly"' \
    /project/enclosure.scad
```

Camera format: `center_x,center_y,center_z,rot_x,rot_y,rot_z,distance`

## Render Individual Parts (for STL colored viewer)

```bash
# Top shell
docker compose run --rm openscad -o "/output/case_top.png" \
    --imgsize "1920,1080" --camera "0,0,12.5,25,0,340,500" \
    -D 'part="case_top"' /project/enclosure.scad

# Bottom shell
docker compose run --rm openscad -o "/output/case_bottom.png" \
    --imgsize "1920,1080" --camera "0,0,12.5,25,0,340,500" \
    -D 'part="case_bottom"' /project/enclosure.scad
```

Available individual parts: `case_top`, `case_bottom`, `part_display`, `part_dpad`, `part_btn_a`, `part_btn_b`, `part_btn_x`, `part_btn_y`, `part_start`, `part_menu`, `part_select`, `part_shoulder_l`, `part_shoulder_r`, `part_pcb`.

## Post-render Verification

```bash
ls -la website/static/img/renders/enclosure/enclosure-*.png
```

Expected 7 files: `enclosure-front.png`, `enclosure-back.png`, `enclosure-top.png`, `enclosure-exploded.png`, `enclosure-cross-section.png`, `enclosure-fit-check.png`, `enclosure-pcb.png`.

## Key Files

- `scripts/render-enclosure.sh` — Render orchestration script
- `hardware/enclosure/enclosure.scad` — Main enclosure source
- `hardware/enclosure/modules/*.scad` — Component modules
- `docker-compose.yml` — OpenSCAD Docker service definition
- `docker/openscad/` — OpenSCAD Docker image build context
- `website/static/img/renders/` — Output directory
