---
id: enclosure
title: 3D Enclosure Design
sidebar_position: 4
---

# 3D Enclosure Design

Parametric handheld console enclosure designed in [OpenSCAD](https://openscad.org/), optimized for FDM 3D printing.

## Design Overview

The enclosure follows a landscape form factor inspired by the Game Boy Advance and Nintendo Switch Lite.

**Dimensions:** 170 × 85 × 26.6 mm — **V3.0 (2026-10-08)**

:::info Source files
The OpenSCAD project files are in [`hardware/enclosure/`](https://github.com/pjcau/esp32-emu-turbo/tree/main/hardware/enclosure). Open with OpenSCAD 2021.01+ (the Docker image runs the 2026 dev build).

```bash
make render-enclosure                # 15 PNG views -> website/static/img/renders/enclosure/
make export-enclosure-stl            # print set -> 3d_case/, viewer set -> 3d_case/viewer/
make generate-enclosure-pcb          # pcb_parts.scad from board.py (also run by generate-pcb)
make verify-enclosure-sync           # scad constants vs board.py / datasheets (34 checks)
make verify-enclosure-requirements   # the user's constraints (20 checks: labels, thin walls, ...)
make verify-enclosure-collision      # CGAL interference: shells vs PCB/panel/battery/caps
make verify-enclosure-stl            # measure the exported STLs themselves (S0-S13)
```
:::

## V3 — the user's review of the V2.1 shell (2026-10-07)

Five asks, each now a named constant with a gate (R13-R15 in
`verify_enclosure_requirements.py`, S8/S10 in `verify_enclosure_stl.py`):

| Ask | What changed | Numbers |
|---|---|---|
| "The buttons must stand about 2 mm out of the face so they can be found by touch, with rounded edges" | `btn_face_h` 0.6 → **2.0**, every cap head rounded with `btn_face_r` 1.5 (`rounded_top_extrude`: stacked inward offsets on a quarter circle) | cap 7.9 → **9.3** tall; the stem, flange and well are unchanged |
| "L/R turned 90° toward Z, on the edge between the two covers, 2-3 mm out" — then (2026-10-08) "I keep SW11/SW12 soldered: a printed mechanism from the caps to the switches" | SW11/SW12 **stay on the board** (TS-1187A, PCB bottom side, actuator facing −Z). A 14 × 8 cap slides through a window in the +Y wall whose top edge is the shell split, **2.5 mm proud**; behind it a printed **bell-crank lever** per side turns the cap's −Y push into a +Z push on the switch | lever pivot: Ø2 pins along X at (y 37.6, Z 13.3) in two U-slot blocks fused to the inner wall; lower arm with a bump 0.05 mm behind the cap flange at Z 7.7; flat upper arm (top Z 14.3 = actuator tip − 0.2) whose end edge sits on the switch centre line. Arms 5.6 / 5.6: cap travel 0.45 and 160 gf, like the face buttons |
| "The speaker on the left" | Player's left = the D-pad side (−X), where `board.py` also marks `SPEAKER_ENC`; the battery pocket slides +2.6 mm in X to free the Ø32 seat | grille at (−62.5, 8); pocket x −45…50 |
| "Rounded like the Switch Lite" | Both shells are **hulls of fillet slices** (`filleted_prism` / `filleted_cavity`): plan corners 8 → **11**, an **8 mm fillet** all round the back face, a **2 mm fillet** round the front | the floor's inner outline is inset 8 mm: the speaker driver (edge x −76.5) stays inside it; the front fillet leaves 1.40 mm at the inner corner |
| "The bottom-edge openings recessed into the face: USB ≥ 2 mm, SD ≥ 4 mm, the switch computed so SW16 can really be moved" | **USB-C**: a 17 × 9 **pocket 2 mm deep** round the 13 × 6.5 opening, with a 1.6 mm pad on the inner wall face so the floor stays 2.2 thick. **SD**: the V2.1 16 × 3.5 **slit** through the bottom-shell wall at Z 14.2 (the V3 20 × 4.7 window was reverted by the user on 2026-10-08); the TF-01A housing front is at |y| 37.0 and a latched card ends 1.3 past it, i.e. 4.2 mm inside the face. **Power**: the MSK12C02 knob (1.6 wide, 1 mm tall) is **5.1 mm inside the face** under the PCB, where no finger goes, so a printed **slider** carries it out: flange inside the wall, a tab up into the lip groove (through a notch in the tongue), a fork straddling the knob, a 4 × 3 nub 1 mm proud in a 10 mm trough; slot 6 = nub 4 + travel 1.6 + 0.4 | gates: `R13 edge-recesses`, sync `sd-slit`, `usbc-recess`, `pwr-slider-vs-sw16` (board placement + datasheets) |

The KSS341GLFS (C&K, C221798 — IP40, 100k, 4 N) is the right **on-board** side switch for the next PCB respin, with its own footprint at the edge; it cannot sit on the TS-1187A pads (two 1.7 mm feet 7.6 apart, pushing perpendicular to them — the pad pattern's long axis points at the edge). Datasheet kept in `hardware/datasheets/SWLR-RESPIN_KSS341GLFS_C221798.pdf`.

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
| No screw bosses in the top shell | V1 screws threaded into the bottom shell's own bosses — the top shell was never fastened | **Top-shell bosses** Ø7.2 at the 4 PCB corner holes, 7 mm tall (they are the spacer to the PCB), with a socket Ø3.1 × 4.5 for an **M2.5 heat-set insert HANGLIFE M2.5 × D3.5 × L4** (OD 3.5, L 4.0) at the PCB end, **2 mm of plastic around it** (boss Ø7.2) and a Ø2.8 relief above it (plain cylinders: the insert is pressed from the PCB side and fuses into the boss wall). **M2.5 × 20** from the back, through the bottom column and the PCB hole, into the insert |
| Bottom bosses hit the L/R buttons | The corner hole (70, 30.5) is **5 mm** from switch SW11/SW12 at (65, 32). A plunger centred on the switch can be at most ~3 mm wide next to the counterbore | L/R are **hinged levers**: pivot rod printed in the shell at x = 51 (outside the 95 mm battery pocket), nub on the switch at x = 65, face 14 × 8.5 mm ending 0.45 mm before the counterbore. Bottom columns get a Ø4.4 neck under the PCB with a relief on the switch side and **four 1.2 mm gussets from the floor** (outward and along ±Y, none toward the levers) |
| Button caps could not reach the switches | V1 stems were 2 mm with a 6.4 mm interior; real switch height is 1.5 mm | Cap stack computed from the real numbers (table below): 3 mm guide well under the ceiling, countersunk conical flange, 1.5 mm stem — 7.9 mm total. Sizes up: **ABXY Ø9**, **D-pad arms 6.5**, **Start/Select 10 × 5**, **Menu 12 × 4** — Start/Select cannot grow in X and ABXY cannot pass Ø9 without moving a switch (the glass is between them) |
| Battery pocket wrong size and place | V1 pocket 85 × 50 sat over J3 (JST S2B-PH-SM4-TB, **5.5 mm** tall under the PCB, datasheet p.4); the fitted cell measures **90 × 50 × 10** (user, 2026-09-16), not 80 | Pocket **95 × 50 × 10** at x −49…46, y −20…30; border 8 mm (below J3's 10.5 mm underside); corners notched for the hinges; clips removed (a pouch cell is held by a foam pad, not pinched). Gates: pocket ≥ measured cell (R10) and clear of **all 77 bottom-side parts** |
| Speaker grille in the wrong corner | V1 grille bottom-right when looking at the back | Grille **top-left when looking at the back** = enclosure (+63, +8); driver seat clears the pocket border (x 47.5), the R lever hinge, the side rib and the column (23.6 mm) |
| Only 2 of 6 LEDs visible | LED3-LED6 (bring-up diagnostics) had no light pipes | Ø1.2 light pipes at (54…72, −20.5); where they cross the Menu guide-well ring the ring is opened outward (no web thinner than 1.2 mm) |
| USB-C plug could not seat | Receptacle mouth is at the PCB edge, 5 mm inside the wall; the 9 × 3.2 hole only passed the plug shell | Opening sized for the **plug overmold** (13 × 6.5), crossing the shell split |
| Battery free to lift against the PCB | Nothing held the cell down; the ESP32 underside is only 0.9 mm above the cell top | Two printed **hold-down straps** 5 × 1 mm over the cell at x = −30 and +26 (outside the module footprint), pegged into four posts on the pocket border at the cell plane (Z 12); the PCB captures them. Gate: straps and posts ≥ 0.5 mm under every bottom-side part |
| Print service rejected the STLs: "thin walls" | Groove skin 0.7, column necks 0.8, speaker ring 0.7, tongue 1.0, cap flanges 0.8, straps 1.0, lever hook 0.35 | One constant **`min_wall = 1.2`**: side walls 2.6 (1.2 skin + 1.2 tongue + 0.2), column contact = outer half-column (no neck), speaker ring 1.7, cap flange 1.2, straps 1.2, lever hook 5 mm wide with 1.35 walls, well rings trimmed through their bore beside the glass, LED pipes open the Menu ring outward, port cutouts only through the wall. Gate R8 tabulates 17 named walls; **R12 slices every shell and lever in OpenSCAD, erodes by 0.6 and fails on anything that disappears** |
| Bosses and frame 0.4 mm short of the PCB (found 2026-09-17 by measuring the STL) | The lip groove was subtracted as a full slab, chopping the last 0.4 mm off every internal feature — invisible to constant-based gates | Groove is a ring; new gate **`verify_enclosure_stl`** slices the exported `3d_case/*.stl` with OpenSCAD `import()` and measures every cutout, boss, pocket and part against `board.py`, the datasheets and the requirements — a second, independent road (S0–S13) |
| Hand-drawn PCB model | A dozen boxes from memory; J3 was 3 mm too short, LEDs missing | `hardware/enclosure/pcb_parts.scad` is **generated from `board.py`** (all 98 fitted parts with body sizes/heights, slot, holes); a stale file is a red gate |
| Engraved labels wrong | V2.0 mirrored the whole label group about x = 0 (A/B/X/Y landed on the D-pad); V2.1 mirrored every top glyph (backwards B, STA/SEL) | Top-shell glyphs are engraved as-is (read from the front), only the back-face L/R are mirrored about their own centre; gate R9 exports the glyphs and checks position **and chirality** (stem side of the B and the L) |

## Z-axis stack (closed assembly, Z = 0 at the back face)

| Z (mm) | What |
|---|---|
| 0 | Back face |
| 2 | Floor inner face — battery pocket, speaker seat, L/R lever pivot blocks |
| 13.3 | L/R lever pivot axis (pin Ø2, top flush with the lever top plane Z 14.3); cap window Z 8 – 16, cap axis Z 12 |
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
| Face proud of the front surface | **2.0** (rounded, r 1.5) | `btn_face_h`, `btn_face_r` |
| Body through the wall | 2.0 | `wall` |
| Body through the guide well under the ceiling | 3.0 | `btn_guide_h` |
| Flange plate (outside the well bore) | 1.2 | `btn_flange_h` |
| Stem to the switch actuator | **1.1** | `btn_stem_h` = 7.0 − 3.0 − 1.2 − 1.5 − 0.2 |
| **Total cap height** | **9.3** | `btn_cap_h` |

- Cap body = cutout outline − 0.6 mm (0.3 per side). Flange = body + 1.2 mm radial, 1.2 mm plate; its top 1.5 mm is a stepped 45° cone that seats in a matching countersink at the well's end — self-centring and printable face-down without supports.
- Stem Ø3.0 (switch plunger Ø2.0). 0.2 mm pre-travel gap, 0.25 mm switch travel.
- The D-pad additionally has a Ø3 centre pivot resting on the PCB (3.2 mm tall) so the cross rocks instead of sinking.
- L/R caps (V3): body 13.7 × 7.7 through the +Y wall window (14.3 × 8.3, open to the split), 2.5 mm proud with 1.5 mm rounded edges; inner flange 1.2 thick, 1.2 wider on the two sides and the bottom, flush on top (the top shell's wall edge keeps the cap down). The lever's bump rests 0.05 mm behind the flange. L and R are the same part: `3d_case/lr_cap_x2.stl`, print 2.
- L/R levers (V3): one bell crank per side (L is the mirror of R, so two files). Beam along X (x 49.3…66.9) with Ø2 pins at both ends; lower arm 4 × 1.6 at the cap centre (x 57.5) down to Z 7, a half-round bump toward the flange; upper arm 3 wide under SW11/SW12, flat top at Z 14.3, end edge on the switch centre line (y 32). The whole top is one plane, so the lever prints upside down without supports: `3d_case/lr_lever_l.stl`, `3d_case/lr_lever_r.stl`.
- Power slider (V3): flange 10 × 4.8 × 1.2 against the inner wall, tab 4 wide × 1.4 up into the lip groove, fork arms 1.2 thick either side of the 1.6 mm knob (Z 14.3…15.8), nub 4 × 3 through the 6 mm slot, 1 mm proud. The flange runs in a **horizontal guide** on the inner wall face: a 16 × 2.9 block (Z 10…13.8) with a 12.2 × 1.3 channel, a 1.6 mm lip holding the flange against the wall and 1.9 mm end stops; the slider drops in from above before the PCB. The MSK12C02 knob (1.6 wide, 1.5 long, datasheet) needs **1.6 mm of travel** ON↔OFF; the channel allows 2.2 and the switch's own detents are the real stops. `3d_case/power_slider.stl`.
- Brand lines (2026-10-08): "GAME BRO!" engraved 0.6 deep above the screen on the top cover (4.5 mm, y = 36.3) and "CPJ & CP 2026" low on the back face (3 mm, y = −27, mirrored for reading from the back); gate R9 counts their glyphs and checks the chirality of the B and the J.

## Screws and inserts

- 4 × **M2.5 heat-set inserts HANGLIFE M2.5 × D3.5 × L4** (OD 3.5, L 4.0), pressed into the top bosses from the PCB side (socket Ø3.1 × 4.5; boss Ø7.2 = 2.05 mm wall).
- 4 × **M2.5 × 20** pan head from the back, counterbore Ø5.0 × 1.8. Path: floor → bottom column (Ø6, Ø2.8 bore, outer half-column for the last 2 mm so the contact face clears SW11/SW12, four 1.5 mm gussets) → PCB Ø2.5 hole → insert (Z 17.6…21.6) → tip at Z 21.8, 0.2 mm into the Ø2.8 relief (Z 22.1…24.1). A 25 mm screw would hit the roof: the gate `R6 screw-length` rejects it.
- The two centre PCB holes (±25, 0) are under the battery pocket and stay unused.

## Rendered Views

### Front (Display Side)
![Front View](/img/renders/enclosure/enclosure-front.png?v=202610090020)

### Plan view
![Top View](/img/renders/enclosure/enclosure-top.png?v=202610090020)

### Back — 8 mm fillet, speaker grille (player's left), L/R labels, screw counterbores
![Back View](/img/renders/enclosure/enclosure-back.png?v=202610090020)

### Bottom edge — USB-C in its 2 mm recess, SD slit, power slider in its trough
![Ports](/img/renders/enclosure/enclosure-ports.png?v=202610090020)

### Top edge — the L/R caps at the shell split, 2.5 mm proud
![L/R edge](/img/renders/enclosure/enclosure-edge-lr.png?v=202610090020)

### Every printed part, as it comes off the bed
![Parts](/img/renders/enclosure/enclosure-parts.png?v=202610090020)

### Exploded View
![Exploded View](/img/renders/enclosure/enclosure-exploded.png?v=202610090020)

### Cross-section, XZ at Y = 0 — battery, module, PCB, panel + riser, caps
![Cross-Section View](/img/renders/enclosure/enclosure-cross-section.png?v=202610090020)

### Cross-section, YZ through the Y button — panel pocket, tail fold, guide well
![Cross-Section YZ](/img/renders/enclosure/enclosure-cross-section-yz.png?v=202610090020)

### Top shell from the inside — display frame, screw bosses, guide wells
![Top inside](/img/renders/enclosure/enclosure-top-inside.png?v=202610090020)

### Same, bare — bosses with the four inserts seated, LED light pipes through the Menu well
![Top inside bare](/img/renders/enclosure/enclosure-top-inside-bare.png?v=202610090020)

### The groove bug the STL audit caught (section through a boss, before / after)
![Groove bug](/img/renders/enclosure/enclosure-groove-bug.png?v=202610090020)

Exact 2D sections at y = 30.5 (through the top-right boss), old model on the left. The lip groove was subtracted as a full 167.6 × 82.6 slab from Z 18.0 up: every boss and frame wall stopped at Z 18.0, 0.4 mm above the PCB top (17.6), and the insert stuck out of its socket. The constants said "7.0 mm interior"; only measuring the exported STL (gate S5) showed the geometry did not. The groove is now the ring between the outer skin and the interior.

### One boss cut through its axis — the print geometry of the insert socket
![Boss section](/img/renders/enclosure/enclosure-boss-section.png?v=202610090020)

From the PCB-side face of the boss inward: socket **Ø3.1 × 4.5 deep** for the insert (HANGLIFE M2.5 × D3.5 × L4: OD 3.5, L 4.0, knurled — pressed with a soldering iron, flush with the boss face), then a **Ø2.8 relief 2.0 deep** for the screw tip, then 0.5 mm of boss plus the 2 mm front wall. Boss Ø7.2 = **2.05 mm of plastic** around the socket (the user asked for 2). M2.5 × 20 tip at Z 21.8 = 0.2 mm past the insert end: full 4 mm engagement. Gate R6 pins these numbers.

### Bottom shell without the PCB — pocket with hold-down straps, columns with gussets, ribs, L/R levers in their pivot blocks, speaker seat ring
![Bottom inside](/img/renders/enclosure/enclosure-bottom-inside.png?v=202610090020)

### Fit Check (bottom shell + PCB + battery + L/R levers and caps + slider)
![Fit Check View](/img/renders/enclosure/enclosure-fit-check.png?v=202610090020)

## Interactive 3D Viewer

:::tip
**[Open the interactive 3D viewer](pathname:///viewer.html)** — it loads **the print files themselves** (`3d_case/*.stl`, served through `staticDirectories`) and only rotates and moves them into place (`3d_case/viewer/placement.json`), so what you see is exactly what you print. Only the display and the PCB, which are not printed, come from `3d_case/viewer/parts/`. `make export-enclosure-stl` regenerates everything; gate S0 of `verify_enclosure_stl.py` proves each placed print file lands exactly on the design's assembly position with a pure rotation (never a mirror). No STL lives under `website/`.

The **Parts & colours** panel lists every placed part. A colour picker repaints it live, a checkbox hides it, and clicking a part in the 3D view selects its row. Colours are kept in the browser (`localStorage`) and survive the Assembly/Exploded switch. **Copy** puts the whole colour set on the clipboard as JSON and **Paste** applies one. The print files are never touched.
:::

## Features

### Front Panel (top shell)
- **Display viewport** 83.52 × 55.68 (+0.3 clearance) at (3.7, 2) — the panel's active area, cosmetic 2 mm raised bezel; glass pocket x −46.8…48.3
- **Display frame** — rim walls to the PCB plane along both long sides (starting 1.5 mm in from the tail edge, clear of LED2) and two stubs beside the FFC passage on the ABXY side; open on the D-pad side where the tail U-folds
- **D-pad** 24 × 6.5, **A/B/X/Y** Ø9 (offsets follow the board's DFM shift: Y at −9), **Start/Select** 10 × 5, **Menu** 12 × 3.8 — every cutout has a 3 mm guide well with a countersunk flange seat
- **LED light pipes** Ø2 at (−55, −30), (−48, −30); Ø1.2 at (54/60/66/72, −20.5)
- **4 screw bosses** Ø7 with M2.5 insert sockets at the PCB corner holes

### Back Panel (bottom shell)
- **8 mm fillet** all round the back face, 11 mm plan corners (V3)
- **L/R caps** on the +Y edge: windows 14.3 × 8.3 at x = ±57.5, open to the split; "L"/"R" engraved on the flat back face at y = 30
- **Speaker grille** — Ø22 hole pattern at (−62.5, 8), seat ring Ø32 for the 28 mm driver (**player's left**, the D-pad side)
- **4 × M2.5 counterbores** Ø5 at (±70, ±30.5)

### Bottom Edge
- **USB-C** 13 × 6.5 plug opening centred at Z = 14.4 inside a 17 × 9 recess 2 mm deep (crosses the split; the lip tongue is notched over it)
- **SD card** slit 16 × 3.5 centred at Z = 14.2, x = 60, bottom shell only (the V2.1 slit; the card end is 4.2 mm inside the face); internal guide shelf from the wall to the PCB edge, top at Z 13.3
- **Power switch** slider at x = −40: 6 mm slot open to the split, 10 × 4 trough 0.6 deep, nub 1 mm proud; the slider's fork drives the MSK12C02 knob 5.1 mm inside; guided by a channel block on the inner wall (travel 1.6 + 0.6)

### Internal (bottom shell)
- **Battery pocket** 95 × 50 (measured cell 90 × 50 × 10, +5 lead clearance) with an 8 mm border, centred at (2.6, 5), lead notch on +X at y = −14, corners notched at +Y
- **L/R lever pivot blocks** at x = ±(46.9…48.9) and ±(67.3…69.3): 2 mm thick, from the floor to Z 15.4, fused to the +Y inner wall, a 2.3 mm U-slot open upward for the Ø2 pin (−Y slot wall 1.4)
- **Battery hold-down** — 4 posts 8 × 3 × 10 on the outer face of the ±Y border walls with Ø2.7 peg holes; 2 printed straps 5 × 1 × 59 mm with Ø2.4 pegs (`3d_case/battery_strap_x2.stl`, print 2)
- **Column gussets** — 4 per bottom column, 1.2 × 6 × 8 mm
- **PCB edge ribs** — 6 blocks under the PCB edge (±40 top, ±25 bottom, ±80 sides) so the board cannot flex under the D-pad
- **Speaker seat**, **SD guide shelf**

## Physical Layout

![Enclosure layout to scale: front with display, D-pad, ABXY, Start/Select/Menu, LEDs and bottom-edge ports; back with mirrored L/R levers, speaker grille and screw counterbores](/img/diagrams/enclosure-layout.svg)

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
| Corner radius | 11 mm plan; back fillet 8, front fillet 2 | V3 |
| Panel outline pocket | 94.57 × 60.88 + 0.3/side | glass centred at x = 0.75 between the Select and Y caps; tail border 8.5 on the D-pad side (user: 8-9 mm) |
| Display viewport | 83.52 × 55.68 + 0.3/side | active area at (3.7, 2); r 1.0 corners |
| Cable riser under the panel | 3.1 mm | `disp_riser` |
| D-pad cutout | 24 × 6.5 cross | stems at r 9 = board `DPAD_OFFSETS` |
| Face button holes | Ø9 | A/B/X/Y at board `ABXY_OFFSETS`; Y flange clipped on the glass side |
| Start/Select | 10 × 5 pills | Select flange clipped on the glass side |
| Menu | 12 × 3.8 pill | 1.2 mm web to the LED4/LED5 light pipes |
| L/R cap | 14 × 8, 2.5 proud | window +0.3, open to the split at Z 16; cap axis Z 12 at x = ±57.5; bell-crank lever to SW11/SW12 at (±65, 32), arms 5.6 / 5.6 |
| USB-C opening | 13 × 6.5 in a 17 × 9 × 2 recess | Z = 14.4, plug overmold |
| SD slit | 16 × 3.5 (Z 12.45…15.95) | bottom shell only; card end 4.2 inside the face |
| Power slider | slot 6 × 3.6, nub 4 × 3, trough 10 × 4 × 0.6 | x = −40; knob travel 1.6 |
| Battery pocket | 95 × 50 × 10 | measured cell 90 × 50 × 10 + 5 mm leads; border 1.5 × 8 tall; centre (2.6, 5) |
| Battery straps | 2 × (5 × 1.2 × 63.4) | at x = −30 / +26, Z 12…13.2; posts 8 × 5.2 × 10 |
| Bottom column | Ø6 / Ø2.8, outer half-column for the last 2 mm, 4 gussets 1.5 | 13.4 mm tall |
| Top boss | Ø7.2, insert socket Ø3.1 × 4.5 + relief Ø2.8 × 2.0 | 7 mm tall, plain cylinder, 2 mm wall |
| Speaker | grille Ø22 at (−62.5, 8), seat ring Ø32 / Ø28.6 | 28 mm driver, 5 mm thick |

## Printing

| Part | Selector | Print file | Orientation |
|---|---|---|---|
| Top shell | `case_top_print` | `3d_case/case_top.stl` | front face down (bosses, frame and wells grow upward — no supports) |
| Bottom shell | `case_bottom` | `3d_case/case_bottom.stl` | back face down; the 8 mm back fillet prints as a shallow overhang (≤ 45° above Z 2.3) |
| D-pad, A/B/X/Y, Start/Select/Menu | `part_*` | `3d_case/*.stl` | face down; the conical flange is stepped so no supports |
| L/R caps (×2, same part) | `part_lr_cap_print` | `3d_case/lr_cap_x2.stl` | flange down, face up |
| L/R levers (L and R, mirrored) | `part_lr_lever_l_print`, `part_lr_lever_r_print` | `3d_case/lr_lever_l.stl`, `3d_case/lr_lever_r.stl` | top plane down (upside down), no supports |
| Power slider | `part_power_slider_print` | `3d_case/power_slider.stl` | flange down, nub up |
| Battery straps (×2) | `part_strap_print` | `3d_case/battery_strap_x2.stl` | flat, pegs up |

| Parameter | Value |
|---|---|
| Material | PLA or PETG (caps in PETG or TPU feel better) |
| Layer height | 0.2 mm shells, 0.12 mm caps |
| Infill | 20 % shells, 100 % caps and slider |
| Supports | none |
| Tolerances built in | 0.3 mm per side on caps and the panel pocket, 0.3 mm on the alignment lip |

### Assembly order
0. Press the 4 M2.5 inserts (D3.5 × L4) into the top bosses (from the PCB side, soldering iron ~200 °C, flush with the boss face).
1. Tape the panel to the bezel from inside the top shell (glass against the ceiling), tail on the D-pad side.
2. Drop the face caps into their wells from inside (flange cone into the countersink).
3. Push the L/R caps into their windows from inside (flange inside the wall), then drop each L/R lever into its two pivot blocks (pins into the U-slots, upper arm toward the board centre under where SW11/SW12 will be, bump against the cap flange); the PCB, once screwed down, keeps the levers in their slots. Fit the power slider into its slot (tab into the tongue notch, fork over the MSK12C02 knob once the PCB is in); seat the speaker in its ring; cell in the pocket, leads through the +X notch to J3; drop the two straps' pegs into the post holes.
4. PCB onto the columns and ribs; fold the tail under the glass into the extension board (left of the slot), FFC through the slot into J4.
5. Close and drive the 4 × M2.5 screws from the back.

## Customization

All dimensions are parameterized in `enclosure.scad`; every column-0 constant is part of the sync-gate contract (numbers, names and `+ - * /` only).

```openscad
disp_border_tail = 8.5;  // measure the panel's driver-ledge border and set it
disp_riser = 3.1;        // cable space under the glass
bat_w = 90; bat_h = 50; bat_d = 10;   // cell L x W x T (measured) — another cell: change these + R10
bat_offset_x = 2.6; bat_offset_y = 5;
```

Run the three gates after any change:

| Gate | What it proves | Checks |
|---|---|---|
| `verify_enclosure_sync` | the scad agrees with `board.py` (positions, holes, panel spec, all 98 parts) and the datasheets (switch incl. the TS-1187A cover and actuator, JST, ESP32, cell, MSK12C02, TF-01A); straps/posts and the L/R levers and pivot blocks clear every bottom part; the levers' arm on SW11/SW12, 5.6 / 5.6 arms, swing under the cover, pin held in its slot; slider, SD slit and USB-C recess vs the board | 33 + 21 mutations |
| `verify_enclosure_requirements` | the model still does what was asked: 7.0 mm stack, glass between the caps, tail/extension zones, 6 LEDs, speaker side, insert/screw geometry, button sizes, 24 named minimum thicknesses, the measured 90 × 50 × 10 cell, the hold-down straps, engraved labels beside their own button and not mirrored, a **measured thin-wall audit** (OpenSCAD slices eroded by 0.6 mm), and the V3 asks: edge recesses, proud rounded caps, rounded shell | 19 + 23 mutations |
| `verify_enclosure_collision` | the shells share no volume with the PCB parts, panel stack, battery, speaker or caps; caps vs panel; panel vs PCB parts (OpenSCAD CGAL) | — |

| `verify_enclosure_stl` | **the other road**: no scad constants — it slices `3d_case/case_top.stl`, `case_bottom.stl`, the L/R caps and levers, the slider and the viewer parts with OpenSCAD `import()` and measures envelopes, every front cutout vs its switch/LED placement, the viewport vs the panel datasheet, the glass pocket and its gaps, insert sockets (Ø3.1 × 4.5, 2 mm wall), counterbores/bores/half-columns, pocket vs the measured cell and J3, the edge openings (L/R windows, slider slot, USB-C recess depth, SD slit width), grille side, cap/edge-part/strap/display alignment and thin walls on the STL slices; refuses STLs older than the scad | 11 |

All four run in `make verify-all`; `make dispatch` routes a red one to the cad-engineer agent. `make export-enclosure-stl` ends with the collision gate and the STL audit.

## Modular Design

| File | Contents |
|---|---|
| `enclosure.scad` | Constants contract, filleted top/bottom shells, face caps, L/R caps and levers, power slider, lever pivot blocks, views, `collision_check`, `labels_check` |
| `pcb_parts.scad` | **Generated** by `scripts/generate_enclosure_pcb.py` from `board.py` — outline, slot, holes, 98 parts with body L × W × H |
| `modules/buttons.scad` | 2D cutout shapes, guide wells with countersink, conical cap flanges |
| `modules/display.scad` | Viewport cutout and bezel |
| `modules/ports.scad` | USB-C, SD card, power switch, speaker grille cutouts |
| `modules/battery.scad` | Battery compartment primitives |
