---
name: enclosure-export
model: claude-sonnet-5
description: Export OpenSCAD enclosure parts to STL — viewer set (assembly coords) + print set (bed orientation) — and run the interference gate
disable-model-invocation: true
allowed-tools: Bash, Read, Glob
argument-hint: [all|viewer|print]
---

# Enclosure STL Export

One command, two outputs, one gate:

```bash
make export-enclosure-stl     # = ./scripts/export-enclosure-stl.sh, ~30 s
```

| Output | Where | Coordinates | Consumer |
|---|---|---|---|
| `viewer/assembly.stl`, `viewer/exploded.stl`, `viewer/parts/*.stl` | `3d_case/viewer/` — served by Docusaurus via `staticDirectories: ['static', '../3d_case']` | assembly (Z=0 back face) | `website/static/viewer.html` loads `viewer/...`; file names are hard-coded in its `ASSEMBLY_PARTS` list |
| `case_top.stl case_bottom.stl dpad.stl btn_{a,b,x,y}.stl start.stl menu.stl select.stl lever_{l,r}.stl battery_strap_x2.stl` | `3d_case/` (project root — the user's folder) | print orientation (flat face on the bed) | the slicer |

The script ends with `scripts/verify_enclosure_collision.py`: an STL set is
never produced from a model whose shells cut into the parts they enclose.
Before uploading to a print service run `make verify-enclosure-requirements`:
R12 is the same thin-wall scan Weerg runs (min 1.2 mm), R8 the named walls.

## Print orientation (built into the selectors)

| Part | Selector | Note |
|---|---|---|
| Top shell | `case_top_print` | front face down — the mirrored `case_top` is for the viewer only |
| Bottom shell | `case_bottom` | back face down; the two lever hinge rods are 9 mm bridges |
| Face caps | `part_dpad`, `part_btn_*`, `part_start/menu/select` | face down; stepped conical flange needs no support |
| L/R levers | `part_shoulder_l`, `part_shoulder_r` | face down; hook slot faces up |
| Battery straps (print 2) | `part_strap_print` | flat, pegs up |

## Export one part by hand

```bash
docker compose run --rm --user "$(id -u):$(id -g)" openscad \
    -o /output/case_top.stl -D 'part="case_top_print"' /project/enclosure.scad
# lands in website/static/img/renders/case_top.stl (the /output mount) — move it to 3d_case/ (no STL stays under website/)
```

## Print settings

- PLA/PETG shells, 0.2 mm layers, 20 % infill, **no supports**.
- Caps and levers 100 % infill, 0.12 mm layers; PETG or TPU for feel.
- Hardware: 4 × M2.5 heat-set inserts L 2.5 × OD 3.5 pressed into the top
  bosses from the PCB side; 4 × M2.5 × 20 from the back (a 25 mm screw
  would go through the roof — gate R6).
- Fit tolerances already in the model: 0.3 mm/side caps and panel pocket,
  0.3 mm alignment lip.

## Key files

- `scripts/export-enclosure-stl.sh` — part lists for both sets
- `scripts/verify_enclosure_collision.py` — the gate it ends with
- `website/static/viewer.html` — `ASSEMBLY_PARTS` (add a file there if you add a viewer part; `part_straps.stl` is one)
- `website/docs/design/enclosure.md` — printing + assembly-order sections
