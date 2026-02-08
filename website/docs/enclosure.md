---
id: enclosure
title: 3D Enclosure Design
sidebar_position: 7
---

# 3D Enclosure Design

Parametric handheld console enclosure designed in [OpenSCAD](https://openscad.org/), optimized for 3D printing.

## Design Overview

The enclosure follows a landscape form factor inspired by the Game Boy Advance and Nintendo Switch Lite, with ergonomic grip areas on both sides.

**Dimensions:** 170 × 85 × 25 mm

:::info Source files
The OpenSCAD project files are in [`hardware/enclosure/`](https://github.com/pjonny/esp32-emu-turbo/tree/main/hardware/enclosure). Open with OpenSCAD 2021.01+.

To render all views:
```bash
make render-enclosure
```
:::

## Interactive 3D Viewer

:::tip
**[Open the interactive 3D viewer](pathname:///viewer.html)** to inspect the enclosure from any angle. Switch between assembly and exploded views, toggle wireframe mode, and zoom into details.
:::

## Rendered Views

### Front (Display Side)
![Front View](/img/renders/enclosure-front.png)

### Back (Battery Side)
![Back View](/img/renders/enclosure-back.png)

### Top (Shoulder Buttons)
![Top View](/img/renders/enclosure-top.png)

### Exploded View
![Exploded View](/img/renders/enclosure-exploded.png)

## Features

### Front Panel
- **4.0" display viewport** — centered, with 2mm raised bezel
- **D-pad** — cross-shaped cutout on left side
- **A/B/X/Y buttons** — diamond layout on right side (SNES style)
- **Start/Select** — pill-shaped cutouts below the D-pad
- **L/R shoulder buttons** — rectangular cutouts on top edge

### Back Panel
- **Speaker grille** — array of 1.5mm holes in circular pattern (left side)
- **Ventilation** — optional vent slots near the processor area

### Bottom Edge
- **USB-C port** — 9.0 × 3.2mm cutout (centered)
- **SD card slot** — 12 × 2.5mm cutout (right side)

### Internal
- **Battery compartment** — 82 × 52 × 11mm cavity with retainer clips (fits 105080 LiPo)
- **Screw bosses** — 6 mounting points (4 corners + 2 center) with 2.5mm screw holes
- **Display shelf** — internal ledge to support the display module PCB
- **Wire channel** — routing path for battery connector cable

## Physical Layout

```
┌─────────────────────────────────────────────────────────┐
│  [L]                                              [R]   │
│                                                         │
│                 ┌───────────────────┐                    │
│                 │                   │                    │
│    ┌─┐          │    4.0" Display   │          [X]      │
│  ┌─┤ ├─┐        │    320 x 480      │       [Y]   [A]   │
│  └─┤ ├─┘        │    ST7796S        │          [B]      │
│    └─┘          │                   │                    │
│   D-pad         └───────────────────┘                    │
│  [Sel] [Sta]                                             │
│                                                         │
│  ┌──USB-C──┐                           ┌──SD Card──┐    │
└──┴─────────┴───────────────────────────┴───────────┴────┘
```

## Dimensions Reference

| Element | Dimension | Notes |
|---|---|---|
| Overall body | 170 × 85 × 25 mm | Landscape orientation |
| Wall thickness | 2.0 mm | All walls |
| Corner radius | 8 mm | Rounded for ergonomics |
| Display cutout | 86.4 × 64.8 mm | Active display area |
| D-pad cutout | 24 × 24 mm cross | 5mm arm width |
| Face button holes | 8 mm diameter | A/B/X/Y, 13mm spacing |
| Start/Select | 10 × 4 mm pills | Below D-pad |
| Shoulder buttons | 20 × 7 mm | Near top corners |
| USB-C port | 9.0 × 3.2 mm | Centered on bottom edge |
| SD card slot | 12 × 2.5 mm | Right side of bottom edge |
| Battery bay | 82 × 52 × 11 mm | For 105080 LiPo |
| Screw bosses | 6mm OD / 2.5mm ID | M2.5 self-tapping |

## 3D Printing Recommendations

| Parameter | Value |
|---|---|
| **Material** | PLA or PETG |
| **Layer height** | 0.2 mm |
| **Infill** | 15-20% |
| **Supports** | Yes (for button cutouts and port overhangs) |
| **Print orientation** | Shell face-down (flat bottom on bed) |
| **Nozzle** | 0.4 mm standard |
| **Estimated print time** | ~4-6 hours per shell |
| **Estimated filament** | ~50g per shell |

:::tip Post-processing
Light sanding on the button holes improves button feel. For a premium finish, apply thin primer + spray paint.
:::

## Customization

All dimensions are parameterized in `enclosure.scad`. Key parameters to adjust:

```openscad
body_w = 170;        // Overall width
body_h = 85;         // Overall height
body_d = 25;         // Overall depth
wall   = 2.0;        // Wall thickness
corner_r = 8;        // Corner radius

disp_w = 86.4;       // Display viewport width
disp_h = 64.8;       // Display viewport height

dpad_x = -62;        // D-pad horizontal position
abxy_x = 62;         // ABXY horizontal position
abxy_spacing = 13;   // Button center-to-center distance
```

### Rendering Different Views

Use the `-D` flag to select which part to render:

```bash
# Full assembly
openscad -o assembly.png -D 'part="assembly"' enclosure.scad

# Top shell only (for printing)
openscad -o top.stl -D 'part="top"' enclosure.scad

# Bottom shell only (for printing)
openscad -o bottom.stl -D 'part="bottom"' enclosure.scad

# Exploded view
openscad -o exploded.png -D 'part="exploded"' enclosure.scad
```

## Modular Design

The OpenSCAD project is split into modules for maintainability:

| File | Contents |
|---|---|
| `enclosure.scad` | Main assembly, shell definitions, render control |
| `modules/buttons.scad` | D-pad, face buttons, Start/Select, shoulder button cutouts |
| `modules/display.scad` | Display viewport cutout, bezel, mounting shelf |
| `modules/ports.scad` | USB-C, SD card slot, speaker grille, ventilation |
| `modules/battery.scad` | Battery compartment cavity, retainer clips, wire channel |
