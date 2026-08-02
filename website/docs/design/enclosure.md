---
id: enclosure
title: 3D Enclosure Design
sidebar_position: 4
---

# 3D Enclosure Design

Parametric handheld console enclosure designed in [OpenSCAD](https://openscad.org/), optimized for 3D printing.

## Design Overview

The enclosure follows a landscape form factor inspired by the Game Boy Advance and Nintendo Switch Lite, with ergonomic grip areas on both sides.

**Dimensions:** 170 × 85 × 26 mm

:::info Source files
The OpenSCAD project files are in [`hardware/enclosure/`](https://github.com/pjcau/esp32-emu-turbo/tree/main/hardware/enclosure). Open with OpenSCAD 2021.01+.

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
![Front View](/img/renders/enclosure/enclosure-front.png)

### Back (Battery Side)
![Back View](/img/renders/enclosure/enclosure-back.png)

### Top (Shoulder Buttons)
![Top View](/img/renders/enclosure/enclosure-top.png)

### Exploded View
![Exploded View](/img/renders/enclosure/enclosure-exploded.png)

### Cross-Section (XZ plane)
![Cross-Section View](/img/renders/enclosure/enclosure-cross-section.png)

### Fit Check (bottom shell + PCB + battery)
![Fit Check View](/img/renders/enclosure/enclosure-fit-check.png)

## Features

### Front Panel
- **3.95" display viewport** — centered, with 2mm raised bezel
- **D-pad** — cross-shaped cutout on left side
- **A/B/X/Y buttons** — diamond layout on right side (SNES style)
- **Start/Select** — pill-shaped cutouts below the D-pad

### Back Panel
- **L/R shoulder buttons** — pill-shaped cutouts near top edge (28 × 10mm)
- **Speaker grille** — array of 1.5mm holes in a 22mm circular pattern, sized to the radiating cone of the 28mm driver whose frame seats against the inner face (D-pad side of the device; appears on the **right** when you look at the back)

### Bottom Edge
- **USB-C port** — 9.0 × 3.2mm cutout (centered), Z-aligned with PCB connector
- **SD card slot** — 12 × 2.5mm cutout (ABXY side of the device), Z-aligned with PCB module
- **Power switch** — 8 × 4mm cutout (D-pad side, left of USB-C when viewed from the front)

### Internal
- **Battery compartment** — 85 × 50 × 10mm cavity with 1.5mm raised border wall and retainer clips (fits the 105080 cell: 80 × 50 × 10mm)
- **Screw bosses** — 4 corner mounting points with M3 countersunk clearance holes (the 2 centre bosses were removed — they fouled the battery, so the PCB's 2 centre M2.5 holes are unused mechanically)
- **PCB model** — 160 × 75mm PCB at shell split line (Z=15mm)
- **Button caps** — retention flange (3mm wider than cutout) prevents fallthrough, actuator stem presses PCB tactile switch
- **Wire channel** — routing path for battery connector cable

## Physical Layout

```
FRONT (display side):
┌──────────────────────────────────────────────────────────┐
│                                                          │
│              ┌────────────────────────────┐              │
│              │                            │     [X]      │
│      ┌─┐     │       3.95" Display        │              │
│    ┌─┤ ├─┐   │         320 x 480          │ [Y]     [A]  │
│    └─┤ ├─┘   │          ILI9488           │              │
│      └─┘     │                            │              │
│     D-pad    └────────────────────────────┘     [B]      │
│  (Sta)  (Sel)                                  (Menu)    │
│        ∘ ∘  LEDs                                         │
│            ┌─PWR─┐    ┌──USB-C──┐         ┌──SD Card──┐  │
└────────────┴─────┴────┴─────────┴─────────┴───────────┴──┘

BACK (as physically seen from behind — left/right MIRRORED vs front):
┌──────────────────────────────────────────────────────────┐
│    ┌──R──┐                                  ┌──L──┐      │
│                                                          │
│                                                          │
│                                                          │
│                                       (( Speaker ))      │
│                                                          │
│                                                          │
└──────────────────────────────────────────────────────────┘

BOTTOM EDGE (as physically seen from behind — mirrored):
─┬───────────┬─────────┬─────────┬────┬─────┬─────────────┬─
 └──SD Card──┘         └──USB-C──┘    └─PWR─┘
```

:::note Left/right convention
The FRONT view is what the player sees; the BACK and BOTTOM-EDGE views above are
what you see when you physically turn the device around, so left/right are
mirrored. USB-C, the SD slot and the power switch are all mounted on the
**bottom (back) side of the PCB** — on the bare board they face you when you
look at the back, with SD on the left and PWR on the right. In device terms:
SD is on the ABXY side, the power switch and speaker are on the D-pad side.
:::

## Dimensions Reference

| Element | Dimension | Notes |
|---|---|---|
| Overall body | 170 × 85 × 26 mm | Landscape orientation (depth went 25 → 26 mm for the 10 mm cell) |
| Wall thickness | 2.0 mm | All walls |
| Corner radius | 8 mm | Rounded for ergonomics |
| Display cutout | 86.4 × 64.8 mm | Active display area |
| D-pad cutout | 24 × 24 mm cross | 5mm arm width |
| Face button holes | 8 mm diameter | A/B/X/Y, 10mm spacing (matches KiCad) |
| Start/Select | 10 × 4 mm pills | Below D-pad, 20mm apart |
| Menu button | 10 × 4 mm pill | Below ABXY |
| Shoulder buttons | 28 × 10 mm | Back panel, Y=32mm from center |
| USB-C port | 9.0 × 3.2 mm | Centered, Z=14.5mm (PCB-aligned) |
| SD card slot | 12 × 2.5 mm | X=60mm, Z=14.5mm (PCB-aligned) |
| Power switch | 8 × 4 mm | X=-40mm, Z=14mm (PCB-aligned) |
| Battery bay | 85 × 50 × 10 mm | 80×50×10mm LiPo (105080) + 5mm length tolerance |
| Battery border | 1.5mm wall | Raised edge around bay perimeter |
| Screw bosses | 6mm OD / 2.5mm ID | 4 corners, M3 countersunk |

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
body_d = 26;         // Overall depth
wall   = 2.0;        // Wall thickness
corner_r = 8;        // Corner radius

disp_w = 86.4;       // Display viewport width
disp_h = 64.8;       // Display viewport height

dpad_x = -62;        // D-pad horizontal position
abxy_x = 62;         // ABXY horizontal position
abxy_spacing = 10;   // Button center-to-center (matches KiCad PCB)

bat_w = 80;          // Cell length (X)
bat_h = 50;          // Cell width  (Y)
bat_d = 10;          // Cell thickness (Z)
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
