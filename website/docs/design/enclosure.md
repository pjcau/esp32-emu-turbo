---
id: enclosure
title: 3D Enclosure Design
sidebar_position: 4
---

# 3D Enclosure Design

Parametric handheld console enclosure designed in [OpenSCAD](https://openscad.org/), optimized for FDM 3D printing.

## Design Overview

The enclosure follows a landscape form factor inspired by the Game Boy Advance and Nintendo Switch Lite.

**Dimensions:** 170 × 85 × 26.6 mm — **V2.1 (2026-09-16)**

:::info Source files
The OpenSCAD project files are in [`hardware/enclosure/`](https://github.com/pjcau/esp32-emu-turbo/tree/main/hardware/enclosure). Open with OpenSCAD 2021.01+ (the Docker image runs the 2026 dev build).

```bash
make render-enclosure                # 12 PNG views -> website/static/img/renders/enclosure/
make export-enclosure-stl            # print set -> 3d_case/, viewer set -> 3d_case/viewer/
make generate-enclosure-pcb          # pcb_parts.scad from board.py (also run by generate-pcb)
make verify-enclosure-sync           # scad constants vs board.py / datasheets (29 checks)
make verify-enclosure-requirements   # the user's constraints (16 checks: labels, thin walls, ...)
make verify-enclosure-collision      # CGAL interference: shells vs PCB/panel/battery/caps
```
:::

## V2 — what the first printed shell taught us

The V1 shell (printed April 2026) was designed before the panel, the tactile
switches and the JST connector were measured. Everything below is a
consequence of a real dimension, and every dimension is now a named constant
that `scripts/verify_enclosure_sync.py` checks against `board.py` or a datasheet.

| V1 problem on the printed shell | Root cause | V2 fix |
|---|---|---|
| Display did not fit / viewport wrong size | V1 viewport was 86.4 × 64.8 (a guessed 4.0" active area). The real ILI9488 3.95" panel with touch is **94.57 × 60.88 × 3.90 mm outline, 83.52 × 55.68 active**, with the 8-9 mm driver-ledge border on the **D-pad side** | Viewport = active area. The **glass** is centred between the Select cap and the Y cap bodies (0.47 mm gap each side — those two caps have their flange clipped on the glass side); the active area lands at x = 3.7, y = 2. The glass may overhang the FPC slot |
| No room for the FPC tail + extension board | The R37 workaround chain (panel tail → 40P extension board → type-B FFC → slot → J4) runs **under the panel**, over the PCB | Tail on the D-pad side, U-folded under the glass (1.8 mm fold zone, 2.1 mm from SW4); extension board 28 × 24 × 3 placed under the glass **before the slot** (x 16.5…44.5); **3.1 mm cable riser** → top interior exactly **7.0 mm** above the PCB (`disp_stack`) |
| Nothing held the panel | V1 had a bezel but no frame; the panel floated on the PCB | Top shell grows a **display frame**: 1.2 mm rim walls from the ceiling down to the PCB along both long sides plus two stubs beside the FFC passage; open on the tail side. The panel is taped to the bezel from inside; the frame contains it and lands on the PCB plane when the screws are tightened |
| No screw bosses in the top shell | V1 screws threaded into the bottom shell's own bosses — the top shell was never fastened | **Top-shell bosses** Ø7.2 at the 4 PCB corner holes, 7 mm tall (they are the spacer to the PCB), with a socket Ø3.1 × 3.0 for an **M2.5 heat-set insert (ID M2.5, L 2.5, OD 3.5)** at the PCB end, **2 mm of plastic around it** (boss Ø7.2) and a Ø2.8 relief above it (plain cylinders: the insert is pressed from the PCB side and fuses into the boss wall). **M2.5 × 20** from the back, through the bottom column and the PCB hole, into the insert |
| Bottom bosses hit the L/R buttons | The corner hole (70, 30.5) is **5 mm** from switch SW11/SW12 at (65, 32). A plunger centred on the switch can be at most ~3 mm wide next to the counterbore | L/R are **hinged levers**: pivot rod printed in the shell at x = 51 (outside the 95 mm battery pocket), nub on the switch at x = 65, face 14 × 8.5 mm ending 0.45 mm before the counterbore. Bottom columns get a Ø4.4 neck under the PCB with a relief on the switch side and **four 1.2 mm gussets from the floor** (outward and along ±Y, none toward the levers) |
| Button caps could not reach the switches | V1 stems were 2 mm with a 6.4 mm interior; real switch height is 1.5 mm | Cap stack computed from the real numbers (table below): 3 mm guide well under the ceiling, countersunk conical flange, 1.5 mm stem — 7.9 mm total. Sizes up: **ABXY Ø9**, **D-pad arms 6.5**, **Start/Select 10 × 5**, **Menu 12 × 4** — Start/Select cannot grow in X and ABXY cannot pass Ø9 without moving a switch (the glass is between them) |
| Battery pocket wrong size and place | V1 pocket 85 × 50 sat over J3 (JST S2B-PH-SM4-TB, **5.5 mm** tall under the PCB, datasheet p.4); the fitted cell measures **90 × 50 × 10** (user, 2026-09-16), not 80 | Pocket **95 × 50 × 10** at x −49…46, y −20…30; border 8 mm (below J3's 10.5 mm underside); corners notched for the hinges; clips removed (a pouch cell is held by a foam pad, not pinched). Gates: pocket ≥ measured cell (R10) and clear of **all 77 bottom-side parts** |
| Speaker grille in the wrong corner | V1 grille bottom-right when looking at the back | Grille **top-left when looking at the back** = enclosure (+63, +8); driver seat clears the pocket border (x 47.5), the R lever hinge, the side rib and the column (23.6 mm) |
| Only 2 of 6 LEDs visible | LED3-LED6 (bring-up diagnostics) had no light pipes | Ø1.2 light pipes at (54…72, −20.5); where they cross the Menu guide-well ring the ring is opened outward (no web thinner than 1.2 mm) |
| USB-C plug could not seat | Receptacle mouth is at the PCB edge, 5 mm inside the wall; the 9 × 3.2 hole only passed the plug shell | Opening sized for the **plug overmold** (13 × 6.5), crossing the shell split |
| Battery free to lift against the PCB | Nothing held the cell down; the ESP32 underside is only 0.9 mm above the cell top | Two printed **hold-down straps** 5 × 1 mm over the cell at x = −30 and +26 (outside the module footprint), pegged into four posts on the pocket border at the cell plane (Z 12); the PCB captures them. Gate: straps and posts ≥ 0.5 mm under every bottom-side part |
| Print service rejected the STLs: "thin walls" | Groove skin 0.7, column necks 0.8, speaker ring 0.7, tongue 1.0, cap flanges 0.8, straps 1.0, lever hook 0.35 | One constant **`min_wall = 1.2`**: side walls 2.6 (1.2 skin + 1.2 tongue + 0.2), column contact = outer half-column (no neck), speaker ring 1.7, cap flange 1.2, straps 1.2, lever hook 5 mm wide with 1.35 walls, well rings trimmed through their bore beside the glass, LED pipes open the Menu ring outward, port cutouts only through the wall. Gate R8 tabulates 17 named walls; **R12 slices every shell and lever in OpenSCAD, erodes by 0.6 and fails on anything that disappears** |
| Hand-drawn PCB model | A dozen boxes from memory; J3 was 3 mm too short, LEDs missing | `hardware/enclosure/pcb_parts.scad` is **generated from `board.py`** (all 98 fitted parts with body sizes/heights, slot, holes); a stale file is a red gate |
| Engraved labels wrong | V2.0 mirrored the whole label group about x = 0 (A/B/X/Y landed on the D-pad); V2.1 mirrored every top glyph (backwards B, STA/SEL) | Top-shell glyphs are engraved as-is (read from the front), only the back-face L/R are mirrored about their own centre; gate R9 exports the glyphs and checks position **and chirality** (stem side of the B and the L) |

## Z-axis stack (closed assembly, Z = 0 at the back face)

| Z (mm) | What |
|---|---|
| 0 | Back face |
| 2 | Floor inner face — battery pocket, speaker seat, lever hinge rods |
| 2 – 12 | Battery cell (90 × 50 × 10, measured) |
| 10.5 – 16 | J3 JST (5.5 mm under the PCB) — the pocket never overlaps it in XY |
| 12.9 – 16 | ESP32 module (3.1 mm), 0.9 mm above the cell |
| **16** | PCB bottom face = shell split = bottom column tops (`pcb_z`) |
| 17.6 | PCB top face; face switches to 19.1 (TS-1187A code A, 1.5 mm) |
| 17.6 – 20.7 | Cable riser (3.1): folded tail, extension board, type-B FFC |
| 20.7 – 24.6 | Panel (3.9 mm, touch version) |
| **24.6** | Ceiling (front wall inner face) = glass top |
| 26.6 | Front face |

## Button caps — computed from the stack

All face caps share one stack; the numbers are `echo()`ed by OpenSCAD on every render and checked by the sync gate (`cap-stem`).

| Element | Height | Constant |
|---|---|---|
| Face proud of the front surface | 0.6 | `btn_face_h` |
| Body through the wall | 2.0 | `wall` |
| Body through the guide well under the ceiling | 3.0 | `btn_guide_h` |
| Flange plate (outside the well bore) | 1.2 | `btn_flange_h` |
| Stem to the switch actuator | **1.1** | `btn_stem_h` = 7.0 − 3.0 − 1.2 − 1.5 − 0.2 |
| **Total cap height** | **7.9** | `btn_cap_h` |

- Cap body = cutout outline − 0.6 mm (0.3 per side). Flange = body + 1.2 mm radial, 1.2 mm plate; its top 1.5 mm is a stepped 45° cone that seats in a matching countersink at the well's end — self-centring and printable face-down without supports.
- Stem Ø3.0 (switch plunger Ø2.0). 0.2 mm pre-travel gap, 0.25 mm switch travel.
- The D-pad additionally has a Ø3 centre pivot resting on the PCB (3.2 mm tall) so the cross rocks instead of sinking.
- Shoulder levers: face 14 × 8.5 proud by 1.0 mm, flange 1.2 mm along the long sides, nub Ø3.4 × 11.3 mm to the switch (actuator at Z = 14.5, nub tip at 14.3), hinge tongue 5 mm wide with a snap hook over the shell's Ø2 rod at x = ±51 — every wall of the hook ≥ 1.35 mm (the print service flagged the 3 mm tongue as thin material).

## Screws and inserts

- 4 × **M2.5 heat-set inserts, ID M2.5 × L 2.5 × OD 3.5**, pressed into the top bosses from the PCB side (socket Ø3.1 × 3.0; boss Ø7.2 = 2.05 mm wall).
- 4 × **M2.5 × 20** pan head from the back, counterbore Ø5.0 × 1.8. Path: floor → bottom column (Ø6, Ø2.8 bore, outer half-column for the last 2 mm so the contact face clears SW11/SW12, four 1.5 mm gussets) → PCB Ø2.5 hole → insert (Z 17.6…20.1) → tip at Z 21.8 inside the Ø2.8 relief (Z 20.6…23.1). A 25 mm screw would hit the roof: the gate `R6 screw-length` rejects it.
- The two centre PCB holes (±25, 0) are under the battery pocket and stay unused.

## Rendered Views

### Front (Display Side)
![Front View](/img/renders/enclosure/enclosure-front.png?v=202609162213)

### Plan view
![Top View](/img/renders/enclosure/enclosure-top.png?v=202609162213)

### Back — hinged L/R levers, speaker grille, screw counterbores
![Back View](/img/renders/enclosure/enclosure-back.png?v=202609162213)

### Bottom edge — USB-C plug opening, SD slot, power switch slot
![Ports](/img/renders/enclosure/enclosure-ports.png?v=202609162213)

### Exploded View
![Exploded View](/img/renders/enclosure/enclosure-exploded.png?v=202609162213)

### Cross-section, XZ at Y = 0 — battery, module, PCB, panel + riser, caps
![Cross-Section View](/img/renders/enclosure/enclosure-cross-section.png?v=202609162213)

### Cross-section, YZ through the Y button — panel pocket, tail fold, guide well
![Cross-Section YZ](/img/renders/enclosure/enclosure-cross-section-yz.png?v=202609162213)

### Top shell from the inside — display frame, screw bosses, guide wells
![Top inside](/img/renders/enclosure/enclosure-top-inside.png?v=202609162213)

### Same, bare — bosses with the four inserts seated, LED light pipes through the Menu well
![Top inside bare](/img/renders/enclosure/enclosure-top-inside-bare.png?v=202609162213)

### One boss cut through its axis — the print geometry of the insert socket
![Boss section](/img/renders/enclosure/enclosure-boss-section.png?v=202609162213)

From the PCB-side face of the boss inward: socket **Ø3.1 × 3.0 deep** for the M2.5 insert (ID M2.5, L 2.5, OD 3.5, knurled — pressed with a soldering iron, flush with the boss face), then a **Ø2.8 relief 2.5 deep** for the screw tip, then 1.5 mm of boss plus the 2 mm front wall. Boss Ø7.2 = **2.05 mm of plastic** around the socket (the user asked for 2). Gate R6 pins these numbers.

### Bottom shell without the PCB — pocket with hold-down straps, columns with gussets, ribs, lever hinges, speaker seat ring
![Bottom inside](/img/renders/enclosure/enclosure-bottom-inside.png?v=202609162213)

### Fit Check (bottom shell + PCB + battery + levers)
![Fit Check View](/img/renders/enclosure/enclosure-fit-check.png?v=202609162213)

## Interactive 3D Viewer

:::tip
**[Open the interactive 3D viewer](pathname:///viewer.html)** — it loads `3d_case/viewer/*.stl` (served through `staticDirectories`); `make export-enclosure-stl` regenerates them together with the print set. No STL lives under `website/`.
:::

## Features

### Front Panel (top shell)
- **Display viewport** 83.52 × 55.68 (+0.3 clearance) at (3.7, 2) — the panel's active area, cosmetic 2 mm raised bezel; glass pocket x −46.8…48.3
- **Display frame** — rim walls to the PCB plane along both long sides (starting 1.5 mm in from the tail edge, clear of LED2) and two stubs beside the FFC passage on the ABXY side; open on the D-pad side where the tail U-folds
- **D-pad** 24 × 6.5, **A/B/X/Y** Ø9 (offsets follow the board's DFM shift: Y at −9), **Start/Select** 10 × 5, **Menu** 12 × 3.8 — every cutout has a 3 mm guide well with a countersunk flange seat
- **LED light pipes** Ø2 at (−55, −30), (−48, −30); Ø1.2 at (54/60/66/72, −20.5)
- **4 screw bosses** Ø7 with M2.5 insert sockets at the PCB corner holes

### Back Panel (bottom shell)
- **L/R hinged levers** — face cutout 14.8 × 9.3 centred at x = ±59.4, y = 32; hinge blocks + Ø2 rod at x = ±51
- **Speaker grille** — Ø22 hole pattern at (63, 8), seat ring Ø30 for the 28 mm driver (**top-left** when you look at the back)
- **4 × M2.5 counterbores** Ø5 at (±70, ±30.5)

### Bottom Edge
- **USB-C** 13 × 6.5 plug opening centred at Z = 14.4 (notches the top shell rim too)
- **SD card** 16 × 3.5 slot at x = 60, Z = 14.2, with an internal guide shelf from the wall to the PCB edge
- **Power switch** 8 × 3.2 slot at x = −40, Z = 14 — the MSK12C02 knob sits 5 mm inside; use a fingernail or a printed extender

### Internal (bottom shell)
- **Battery pocket** 95 × 50 (measured cell 90 × 50 × 10, +5 lead clearance) with an 8 mm border, lead notch on +X at y = −14, corners notched at +Y for the lever hinges
- **Battery hold-down** — 4 posts 8 × 3 × 10 on the outer face of the ±Y border walls with Ø2.7 peg holes; 2 printed straps 5 × 1 × 59 mm with Ø2.4 pegs (`3d_case/battery_strap_x2.stl`, print 2)
- **Column gussets** — 4 per bottom column, 1.2 × 6 × 8 mm
- **PCB edge ribs** — 6 blocks under the PCB edge (±40 top, ±25 bottom, ±80 sides) so the board cannot flex under the D-pad
- **Speaker seat**, **SD guide shelf**, **lever hinges**

## Physical Layout

```
FRONT (display side):
┌──────────────────────────────────────────────────────────┐
│  ○                                                   ○   │  ← top-shell columns at (±70, 30.5)
│              ┌────────────────────────────┐              │
│              │                            │     [A]      │
│      ┌─┐     │  83.5 x 55.7 active area   │              │
│    ┌─┤ ├─┐   │      (panel 94.6 x 60.9,   │ [Y]     [B]  │
│    └─┤ ├─┘   │       tail exits right ►)  │              │
│      └─┘     │                            │     [X]      │
│     D-pad    └────────────────────────────┘              │
│ (START) (Sel)                                  (MENU)    │
│  ○     ∘ ∘  LEDs                                     ○   │
│            ┌─PWR─┐    ┌──USB-C──┐         ┌──SD Card──┐  │
└────────────┴─────┴────┴─────────┴─────────┴───────────┴──┘

BACK (as physically seen from behind — left/right MIRRORED vs front):
┌──────────────────────────────────────────────────────────┐
│  ●  ┌──R lever──┐                  ┌──L lever──┐  ●      │  ● = M2.5 counterbore
│                                                          │
│                                          (( Speaker ))   │
│                                                          │
│  ●                                                ●      │
└──────────────────────────────────────────────────────────┘
```

:::note Left/right convention
The FRONT view is what the player sees; the BACK view is what you see when
you physically turn the device around, so left/right are mirrored. USB-C,
the SD slot and the power switch are on the **bottom side of the PCB**; in
device terms SD is on the ABXY side, the power switch and speaker on the
D-pad side.
:::

## Dimensions Reference

| Element | Dimension | Notes |
|---|---|---|
| Overall body | 170 × 85 × 26.6 mm | 26 → 26.6: the 7.0 mm display stack |
| Wall thickness | floor/front 2.0, side walls 2.6 | side = 1.2 skin + 1.2 lip + 0.2 clearance |
| Corner radius | 8 mm | |
| Panel outline pocket | 94.57 × 60.88 + 0.3/side | glass centred at x = 0.75 between the Select and Y caps; tail border 8.5 on the D-pad side (user: 8-9 mm) |
| Display viewport | 83.52 × 55.68 + 0.3/side | active area at (3.7, 2); r 1.0 corners |
| Cable riser under the panel | 3.1 mm | `disp_riser` |
| D-pad cutout | 24 × 6.5 cross | stems at r 9 = board `DPAD_OFFSETS` |
| Face button holes | Ø9 | A/B/X/Y at board `ABXY_OFFSETS`; Y flange clipped on the glass side |
| Start/Select | 10 × 5 pills | Select flange clipped on the glass side |
| Menu | 12 × 3.8 pill | 1.2 mm web to the LED4/LED5 light pipes |
| L/R lever face | 14 × 8.5 | cutout +0.8; tip at x = 65.8, hinge at x = 50.4; 1.3 mm floor web to the Ø5 counterbore |
| USB-C opening | 13 × 6.5 | Z = 14.4, plug overmold |
| SD slot | 16 × 3.5 | Z = 14.2 |
| Power switch slot | 8 × 3.2 | Z = 14 |
| Battery pocket | 95 × 50 × 10 | measured cell 90 × 50 × 10 + 5 mm leads; border 1.5 × 8 tall; centre (−1.5, 5) |
| Battery straps | 2 × (5 × 1.2 × 63.4) | at x = −30 / +26, Z 12…13.2; posts 8 × 5.2 × 10 |
| Bottom column | Ø6 / Ø2.8, outer half-column for the last 2 mm, 4 gussets 1.5 | 13.4 mm tall |
| Top boss | Ø7.2, insert socket Ø3.1 × 3.0 + relief Ø2.8 × 2.5 | 7 mm tall, plain cylinder, 2 mm wall |
| Speaker | grille Ø22 at (63.5, 8), seat ring Ø32 / Ø28.6 | 28 mm driver, 5 mm thick |

## Printing

| Part | Selector | Print file | Orientation |
|---|---|---|---|
| Top shell | `case_top_print` | `3d_case/case_top.stl` | front face down (bosses, frame and wells grow upward — no supports) |
| Bottom shell | `case_bottom` | `3d_case/case_bottom.stl` | back face down (hinge rods are 9 mm bridges) |
| D-pad, A/B/X/Y, Start/Select/Menu | `part_*` | `3d_case/*.stl` | face down; the conical flange is stepped so no supports |
| L/R levers | `part_shoulder_l/r` | `3d_case/lever_l.stl`, `3d_case/lever_r.stl` | face down |
| Battery straps (×2) | `part_strap_print` | `3d_case/battery_strap_x2.stl` | flat, pegs up |

| Parameter | Value |
|---|---|
| Material | PLA or PETG (caps in PETG or TPU feel better) |
| Layer height | 0.2 mm shells, 0.12 mm caps |
| Infill | 20 % shells, 100 % caps and levers |
| Supports | none |
| Tolerances built in | 0.3 mm per side on caps and the panel pocket, 0.3 mm on the alignment lip |

### Assembly order
0. Press the 4 M2.5 inserts (L 2.5, OD 3.5) into the top bosses (from the PCB side, soldering iron ~200 °C, flush with the boss face).
1. Tape the panel to the bezel from inside the top shell (glass against the ceiling), tail on the D-pad side.
2. Drop the face caps into their wells from inside (flange cone into the countersink).
3. Snap the L/R levers onto the hinge rods in the bottom shell (hook opening faces the floor); seat the speaker in its ring; cell in the pocket, leads through the +X notch to J3; drop the two straps' pegs into the post holes.
4. PCB onto the columns and ribs; fold the tail under the glass into the extension board (left of the slot), FFC through the slot into J4.
5. Close and drive the 4 × M2.5 screws from the back.

## Customization

All dimensions are parameterized in `enclosure.scad`; every column-0 constant is part of the sync-gate contract (numbers, names and `+ - * /` only).

```openscad
disp_border_tail = 8.5;  // measure the panel's driver-ledge border and set it
disp_riser = 3.1;        // cable space under the glass
bat_w = 90; bat_h = 50; bat_d = 10;   // cell L x W x T (measured) — another cell: change these + R10
bat_offset_x = -1.5; bat_offset_y = 5;
```

Run the three gates after any change:

| Gate | What it proves | Checks |
|---|---|---|
| `verify_enclosure_sync` | the scad agrees with `board.py` (positions, holes, panel spec, all 98 parts) and the datasheets (switch, JST, ESP32, cell); straps/posts clear every bottom part | 29 + 18 mutations |
| `verify_enclosure_requirements` | the model still does what was asked: 7.0 mm stack, glass between the caps, tail/extension zones, 6 LEDs, speaker corner, insert/screw geometry, button sizes, 17 named minimum thicknesses, the measured 90 × 50 × 10 cell, the hold-down straps, engraved labels beside their own button and not mirrored, and a **measured thin-wall audit** (OpenSCAD slices eroded by 0.6 mm) | 16 + 16 mutations |
| `verify_enclosure_collision` | the shells share no volume with the PCB parts, panel stack, battery, speaker or caps; caps vs panel; panel vs PCB parts (OpenSCAD CGAL) | — |

All three run in `make verify-all`; `make dispatch` routes a red one to the cad-engineer agent.

## Modular Design

| File | Contents |
|---|---|
| `enclosure.scad` | Constants contract, top/bottom shell, caps, levers, views, `collision_check`, `labels_check` |
| `pcb_parts.scad` | **Generated** by `scripts/generate_enclosure_pcb.py` from `board.py` — outline, slot, holes, 98 parts with body L × W × H |
| `modules/buttons.scad` | 2D cutout shapes, guide wells with countersink, conical cap flanges |
| `modules/display.scad` | Viewport cutout and bezel |
| `modules/ports.scad` | USB-C, SD card, power switch, speaker grille cutouts |
| `modules/battery.scad` | Battery compartment primitives |
