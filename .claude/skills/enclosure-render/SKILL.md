---
name: enclosure-render
model: claude-sonnet-5
description: Render OpenSCAD enclosure views to PNG via Docker (13 views incl. inside-shell, boss section and cross-sections)
disable-model-invocation: true
allowed-tools: Bash, Read, Glob
argument-hint: [all|front|back|top|ports|exploded|cross-section|cross-section-yz|fit-check|top-inside|top-inside-bare|bottom-inside|pcb]
---

# Enclosure Rendering Pipeline

Render the OpenSCAD enclosure model to PNG via the `openscad` Docker service
(`openscad/openscad:dev` — NOT `2021.01`). Paths are relative to the repo
root; the container maps `hardware/enclosure` → `/project` and
`website/static/img/renders` → `/output`.

**Argument** (optional): a view name, default `all`.

## Render all views

```bash
make render-enclosure        # = ./scripts/render-enclosure.sh (builds the image if needed)
```

13 views at 1920×1080 → `website/static/img/renders/enclosure/enclosure-<view>.png`.
Outputs are written with `--user $(id -u)` — a root-owned leftover from an
older run makes OpenSCAD fail with "Can't open file for export": delete it
(`find website/static/img/renders -user root -delete`) and re-run.

| View | Part | Camera (center / rot / dist) | Shows |
|------|------|------------------------------|-------|
| `front` | assembly | 0,0,12.5 / 25,0,340 / 500 | front 3/4 |
| `back` | assembly | 0,0,12.5 / 205,0,200 / 500 | back as physically turned around (L/R mirrored) |
| `top` | assembly | 0,0,12.5 / 0,0,0 / 430 | plan view of the front face |
| `ports` | assembly | 0,0,12 / 90,0,0 / 300 | bottom edge: USB-C, SD, power |
| `exploded` | exploded | 0,0,20 / 55,0,330 / 600 | shells, PCB, panel, caps, levers |
| `cross-section` | cross_section | 0,-10,13 / 60,0,0 / 300 | XZ at Y=0: battery, module, PCB, panel + riser, cap stack |
| `cross-section-yz` | cross_section_yz | 53,0,14 / 70,0,90 / 180 | YZ through the Y button: pocket, tail fold, well |
| `fit-check` | fit_check | 0,0,10 / 35,0,340 / 420 | bottom shell + translucent PCB + battery + levers |
| `top-inside` | top_inside | 0,0,5 / 35,0,20 / 420 | display frame, bosses, guide wells, panel + caps in place |
| `top-inside-bare` | top_inside_bare | 0,0,5 / 35,0,20 / 420 | same without panel/caps: insert sockets, gussets, LED pipes |
| `bottom-inside` | bottom_inside | 0,0,8 / 35,0,20 / 420 | pocket, columns, ribs, lever hinges (no PCB) |
| `boss-section` | boss_section | 70,30.5,20 / 70,0,0 / 60 | one top boss cut open: insert socket + relief (print geometry) |
| `pcb` | pcb | 0,0,1 / 25,0,340 / 300 | PCB model only |

## Render a single view

```bash
docker compose run --rm --user "$(id -u):$(id -g)" openscad \
    -o /output/enclosure/enclosure-top-inside.png \
    --imgsize 1920,1080 --camera 0,0,5,35,0,20,420 \
    -D 'part="top_inside"' /project/enclosure.scad
```

Camera format: `center_x,center_y,center_z,rot_x,rot_y,rot_z,distance`.
`--user` keeps the output files owned by you instead of root.

## What to look at after a change

- `top-inside`: the glass sitting between the Select and Y caps, the tail
  fold on the D-pad side, the extension board before the slot; nothing
  green/orange over a button.
- `top-inside-bare`: four grey bosses with the brass inserts seated, the
  frame walls and +X stubs, LED holes through the Menu well ring.
- `bottom-inside`: no speaker body is drawn — the seat ring marks where the
  28 mm driver drops in.
- `bottom-inside`: lever nubs under the switches, hinge blocks clear of the
  pocket border, columns' necks.
- `cross-section`: 7.0 mm between PCB top and ceiling; cap stems reaching the
  switches; battery under the module with clearance.
- Console output: `ECHO: "V2.1 stack: body_d=26.6 top_int=7 btn_stem_h=1.1
  btn_cap_h=7.9 glass_cx=0.75 disp_x=3.725 lever_nub_h=11.1"` — any other
  numbers mean a constant moved.

Renders are pictures; the numeric truth is `make verify-enclosure-sync`,
`make verify-enclosure-requirements` and `make verify-enclosure-collision`.
Run those first. Labels in particular: the requirements gate (R9) exports
the glyphs and checks each sits beside its own button — do not judge them
from a thumbnail.

## Key files

- `scripts/render-enclosure.sh` — view table (edit here to add a view)
- `hardware/enclosure/enclosure.scad` — `part` selector at the bottom
- `docker-compose.yml` → `openscad` service; `docker/openscad/`
- `website/docs/design/enclosure.md` — embeds every view; add the image when adding a view
