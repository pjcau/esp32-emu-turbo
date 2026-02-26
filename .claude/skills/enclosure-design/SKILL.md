---
name: enclosure-design
description: Design and modify the OpenSCAD parametric enclosure for the handheld console
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: <component-or-feature> (e.g. "dpad", "battery", "usb-c", "shoulder-buttons")
---

# OpenSCAD Enclosure Design

Design and modify the parametric 3D enclosure for the ESP32 Emu Turbo handheld console.

**Argument** (optional): Component or feature to modify (e.g., `dpad`, `battery`, `usb-c`, `shoulder-buttons`).

## Architecture

The enclosure is a landscape handheld (170 x 85 x 25 mm) with:
- **Top shell** (display side, 10mm deep) — display viewport, D-pad, ABXY, Start/Select/Menu, LED holes
- **Bottom shell** (battery side, 15mm deep) — battery bay, screw bosses, speaker grille, USB-C, SD slot, power switch, shoulder buttons
- **Alignment lip** — tongue on bottom shell fits groove in top shell (0.3mm tolerance)
- **Button caps** — flange + stem design (retention flange + actuator stem for tactile switches)

## File Structure

| File | Purpose |
|------|---------|
| `hardware/enclosure/enclosure.scad` | Main enclosure (top/bottom shell, PCB, assembly, views) |
| `hardware/enclosure/modules/buttons.scad` | Button cutout modules (D-pad, ABXY diamond, pill, shoulder) |
| `hardware/enclosure/modules/display.scad` | Display viewport cutout and bezel |
| `hardware/enclosure/modules/ports.scad` | USB-C, SD card, power switch, speaker grille cutouts |
| `hardware/enclosure/modules/battery.scad` | Battery compartment, wire channel |

## Key Parameters (enclosure.scad)

### Enclosure body
- `body_w=170`, `body_h=85`, `body_d=25` — Overall dimensions
- `wall=2.0` — Wall thickness
- `corner_r=8` — Corner radius
- `top_d=10`, `bot_d=15` — Shell split

### Display (ILI9488 3.95")
- `disp_w=86.4`, `disp_h=64.8` — Active area
- `disp_pcb_w=98`, `disp_pcb_h=72` — Module PCB size

### Controls
- `dpad_x=-62`, `dpad_y=5` — D-pad center
- `abxy_x=62`, `abxy_y=5`, `abxy_spacing=10` — ABXY diamond center + spacing
- `ss_x=dpad_x`, `ss_y=-17` — Start/Select position
- `menu_x=62`, `menu_y=-25` — Menu button

### Ports (bottom edge)
- `usbc_x=0` — USB-C (centered)
- `sd_x=60` — SD card (right)
- `pwr_sw_x=-40` — Power switch (left)
- `spk_x=-50`, `spk_y=-15` — Speaker grille (back)

### PCB (from KiCad)
- `pcb_w=160`, `pcb_h=75`, `pcb_d=1.6`, `pcb_corner_r=6`
- `pcb_z=bot_d` (15mm) — PCB sits on screw boss tops at shell split

### Battery
- `bat_w=65`, `bat_h=55`, `bat_d=9.5` — LiPo dimensions

## Z-axis Stack (closed assembly)

```
Z=0:    Bottom shell outer face
Z=2:    Bottom shell floor (wall=2)
Z=2-11.5: Battery (9.5mm)
Z=12-15:  ESP32 module zone (3mm below PCB)
Z=15:     PCB bottom face / shell split line
Z=16.6:   PCB top face (1.6mm board)
Z=15-23:  Top shell interior (8mm)
Z=23:     Top shell ceiling
Z=25:     Top shell outer face
```

## Coordinate System

- **Enclosure origin**: Center of enclosure body (XY), Z=0 at bottom shell exterior
- **KiCad → Enclosure mapping**: `enc_x = kicad_x - 80`, `enc_y = 37.5 - kicad_y`
  (KiCad origin is top-left of board outline at (0,0), board center at (80, 37.5))

## Button Cap Design

Each button cap has 3 parts:
1. **Cap body** — Visible part, fills cutout with clearance
2. **Retention flange** — Wider, rests on inner shell surface (prevents cap from falling out)
3. **Actuator stem** — Thin post pressing the PCB tactile switch

Parameters: `btn_flange_extra=3mm`, `btn_flange_h=0.8mm`, `btn_stem_d=2.0mm`, `btn_stem_h=2.0mm`

## Render Views

The `part` variable selects the view:
- `assembly` — Complete assembly (default)
- `top` / `bottom` — Individual shells
- `exploded` — Exploded view with all components
- `cross_section` — XZ plane cut at Y=0
- `fit_check` — Bottom shell open-top with internals
- `battery_fit` — Bottom shell + battery only
- `pcb` — PCB model only
- `case_top` / `case_bottom` — Shells for STL export
- `part_dpad`, `part_btn_a`, etc. — Individual button caps

## Design Guidelines

- **3D print tolerance**: 0.3mm clearance for mating parts (alignment lip)
- **Button clearance**: 0.5mm between cap and cutout
- **Wall thickness**: Minimum 2.0mm for FDM printing
- **Corner radius**: 8mm for ergonomic grip
- **Screw bosses**: M3, 6mm OD, 4 corner positions
- **Speaker grille**: Radial hole pattern, 1.5mm holes, 3.5mm pitch

## Key Files

- `hardware/enclosure/enclosure.scad` — Main enclosure design
- `hardware/enclosure/modules/*.scad` — Component modules
- `scripts/render-enclosure.sh` — Render pipeline (7 views)
- `website/static/img/renders/` — Output renders
- `website/docs/enclosure.md` — Design documentation
