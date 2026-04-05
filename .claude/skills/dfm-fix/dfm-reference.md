# DFM Reference — JLCPCB Rules & Project-Specific Fixes

> Comprehensive DFM rules for JLCPCB standard PCB + PCBA service.
> Sources: JLCPCB official capabilities, help articles, blog posts, and project experience.

---

## Part 1 — JLCPCB Manufacturing Capabilities

### 1.1 Trace Width & Spacing

| Parameter | 2-Layer (1oz Cu) | 2-Layer (2oz Cu) | 4-Layer (1oz/0.5oz) | 6+ Layer |
|-----------|-----------------|-----------------|---------------------|----------|
| Min trace width | 0.127mm (5 mil) | 0.2mm (8 mil) | 0.1mm (4 mil) | 0.09mm (3.5 mil) |
| Min trace spacing | 0.127mm (5 mil) | 0.2mm (8 mil) | 0.1mm (4 mil) | 0.09mm (3.5 mil) |
| Ultra-fine (special) | N/A | N/A | N/A | 0.076mm (3 mil) |

**Our project**: 2-layer 1oz, min trace width = 0.15mm, min spacing = 0.15mm (conservative).

**Surcharges**: 3.0-3.5 mil trace/space on 4-8 layer = +20%; on 10+ layer = +30%.

### 1.2 Via Specifications

| Parameter | 2-Layer | 4+ Layer |
|-----------|---------|----------|
| Min via pad diameter | 0.6mm (24 mil) | 0.45mm (18 mil) |
| Min via drill diameter | 0.3mm (12 mil) | 0.2mm (8 mil) |
| Min via-to-via clearance | 0.254mm (10 mil) | 0.127mm (5 mil) |
| Min annular ring (standard) | 0.15mm (6 mil) | 0.15mm (6 mil) |
| Recommended annular ring | 0.2mm (8 mil) | 0.2mm (8 mil) |
| Absolute min annular ring | 0.075mm (3 mil) | 0.075mm (3 mil) |
| Max aspect ratio (drill:thickness) | 10:1 | 10:1 |

**Via plugging**: Cannot plug vias within 0.35mm of pads.

**Our project vias**:
- Standard: 0.46mm pad / 0.20mm drill → ring = 0.13mm (OK)
- Approach (tight): 0.35mm pad / 0.20mm drill → ring = 0.075mm (at absolute min)

### 1.3 Hole Sizes & Drilling

| Parameter | Min | Max | Tolerance |
|-----------|-----|-----|-----------|
| PTH (plated through-hole) | 0.15mm | 6.3mm | +0.13/-0.08mm |
| PTH (press-fit) | — | — | +/-0.05mm |
| NPTH (non-plated) | 0.5mm | 6.3mm | +/-0.05mm |
| Metallized slot | 0.65mm | — | +/-0.15mm |
| Non-metallized slot | 1.0mm | — | +/-0.15mm |
| Drill bit increment | 0.05mm | — | — |

**Rules**:
- Hole diameter > component pin max size + 0.1mm
- Holes must be multiples of 0.05mm drill bit increment
- NPTH-to-copper clearance: >= 2.0mm

### 1.4 Pad Specifications

| Parameter | Value |
|-----------|-------|
| Pad-to-pad clearance (different net) | >= 0.127mm (5 mil) |
| Trace-to-pad clearance | >= 0.127mm (5 mil) |
| Via copper-to-BGA pad spacing | >= 0.10mm |
| Trace-to-BGA pad spacing | >= 0.10mm |
| BGA pad diameter (min) | 0.25mm |
| BGA ball-to-ball spacing (min) | 0.127mm (5 mil) |

### 1.5 Soldermask

| Parameter | Value |
|-----------|-------|
| Mask thickness | 16-30 um |
| Min dam width (bridge) — multilayer | 0.1mm |
| Min dam width (bridge) — 1-2 layer | 0.2mm |
| Min dam width (high-density) | 0.075mm |
| Standard expansion (SMD pads) | 0.05mm per side |
| Expansion (through-hole pads) | 0.1-0.15mm |
| Expansion (BGA, 0.4mm pitch) | 0.025mm |
| Expansion (traces) | 0.025-0.05mm |
| Expansion (vias, untented) | 0.05-0.1mm |
| Min exposed copper ring | 0.025mm |
| Alignment accuracy | +/-0.05mm |
| SMD pad tolerance | +/-0.025mm |
| Via-to-mask opening clearance | 0.2mm min |
| Sliver risk threshold | < 0.1mm (risk of peeling) |

**Rules**:
- Mask bridges < 0.1mm → solder bridging risk
- Mask bridge < 0.075mm → JLCPCB auto-removes the bridge
- Via tenting recommended unless explicitly needing probe access

### 1.6 Silkscreen / Legend

| Parameter | Standard | High-Precision |
|-----------|----------|---------------|
| Min line/stroke width | 0.15mm (6 mil) | 0.1mm (4 mil) |
| Min character height | 1.0mm (40 mil) | 0.8mm (32 mil) |
| Width-to-height ratio | 1:6 | 1:6 |
| Hollow font min stroke | 0.2mm | — |
| Hollow font min height | 1.5mm | — |
| Clearance from solder pads | >= 0.15mm | >= 0.15mm |
| Clearance from holes | >= 0.5mm | >= 0.5mm |
| Character-to-character gap | > 0.15mm | > 0.15mm |

**Auto-removal rules**:
- Characters overlapping pads or within 0.15mm of copper → auto-removed
- Characters on exposed copper (HASL/ENIG) → auto-deleted
- Silkscreen over vias → auto-removed

### 1.7 Board Edge & Outline Clearances

| Parameter | Value |
|-----------|-------|
| Copper-to-board-edge (min) | 0.3mm |
| Trace-to-board-edge (min) | 0.2mm |
| Pad-to-board-edge (min) | 0.3mm |
| Component-to-board-edge (PCBA) | >= 0.3mm |
| NPTH-to-copper clearance | >= 2.0mm |
| V-Cut depaneling tolerance | 0.2mm |

### 1.8 Copper Weight

| Weight | Thickness | Notes |
|--------|-----------|-------|
| 0.5 oz | 17.5 um | Inner layers standard |
| 1 oz | 35 um (nominal), ~30 um actual | Standard outer |
| 2 oz | 70 um | High current, wider min trace/space |

### 1.9 Board Dimensions

| Parameter | Min | Max |
|-----------|-----|-----|
| Single board | 5 x 5mm | 400 x 500mm |
| V-Cut panel | 70 x 70mm | 400 x 400mm |
| PCB Assembly board | 10 x 10mm | 470 x 500mm |
| Economic assembly panel | — | 250 x 250mm |

**Thickness options**: 0.4mm (ENIG only), 0.6mm (max 100x100mm), 0.8-2.0mm (standard). Tolerance: +/-10%.

### 1.10 Impedance Control

| Parameter | Value |
|-----------|-------|
| Single-ended range | 20-90 ohm |
| Differential range | 50-150 ohm |
| Tolerance | +/-10% |

---

## Part 2 — JLCPCB PCBA / Assembly Rules

### 2.1 Process Edges & Tooling

| Parameter | Value |
|-----------|-------|
| Process edge width | 5mm recommended |
| Tooling hole diameter | 2mm |
| Fiducial pad diameter | 1.0mm (40 mil) |
| Fiducial mask opening | 2.0mm (2x pad diameter) |
| Fiducial copper clearance zone | 2.0mm diameter |
| Fiducial from panel edge | >= 3.85mm |
| Fiducial from board edge (min) | >= 3.35mm |
| Local fiducials needed for | pitch <= 0.5mm |

### 2.2 Component Spacing

| Parameter | Value |
|-----------|-------|
| SMD-to-SMD min clearance | 0.3mm |
| SMD-to-board-edge min | 0.3mm |
| Smallest package supported | 01005 |

### 2.3 Solder Paste Stencil Apertures — Passive Components

| Component | Aperture Width | Length Extension |
|-----------|---------------|-----------------|
| 0402 | 0.26mm | +0.15mm |
| 0603 | 0.28mm | +0.20mm |
| 0603 (gap > 0.75mm) | 0.32mm | +0.20mm |
| 0805 | 0.32mm | +0.20mm |
| 0805 (gap > 0.95mm) | 0.35mm | +0.20mm |

### 2.4 Solder Paste Stencil Apertures — ICs (pitch-based)

| Pitch | Aperture Width | Notes |
|-------|---------------|-------|
| 0.8-1.27mm | 45-60% of pitch | Standard |
| 0.635-0.65mm | 0.3-0.33mm | L=1mm, rounded corners |
| 0.5mm | 0.24mm | Extend L by 0.1mm if < 1.5mm |
| 0.4mm | 0.19mm | Extend L by 0.1mm |
| 0.35mm | 0.17mm | Extend L by 0.1mm |
| 0.3mm | 0.16mm | Extend L by 0.1mm |

### 2.5 Solder Paste Stencil Apertures — BGA

| Pitch | Aperture (square) |
|-------|-------------------|
| 0.4mm | 0.23mm |
| 0.45mm | 0.26mm |
| 0.5mm | 0.30mm |
| 0.65mm | 0.35mm |
| 0.8mm | 0.45mm |
| 1.0mm | 0.55mm |
| 1.27mm | 0.65mm |

### 2.6 BGA Layout Rules

| Parameter | 2-Layer | 4-Layer | 6+ Layer (via-in-pad) |
|-----------|---------|---------|----------------------|
| Via drill | 0.15mm | 0.15mm | 0.15mm |
| Via copper diameter | 0.25mm | 0.25mm | 0.35mm (filled) |
| BGA pad diameter | 0.25mm | 0.25mm | 0.25mm |
| Drill-to-BGA pad | 0.35mm | 0mm | via-in-pad |
| Trace-to-trace | 0.10mm | 0.09mm | 0.09mm |
| Trace-to-BGA pad | 0.10mm | 0.10mm | — |
| Via copper-to-BGA pad | 0.10mm | 0.10mm | — |

---

## Part 3 — Generic DFM Best Practices

### 3.1 Trace Geometry & Routing

| Rule | Description |
|------|-------------|
| **No acute angles** | Angles < 90 deg trap etchant ("acid traps") → over-etching |
| **45-degree routing** | Default routing angle; creates 135-degree corners (safe) |
| **90-degree angles** | Acceptable when space-constrained, but 45 deg preferred |
| **Trace necking** | Avoid abrupt width changes; taper over >= 2x trace width |
| **Current capacity** | 1oz/35um Cu: 0.25mm trace ≈ 0.5A, 0.5mm ≈ 1A, 1mm ≈ 2A (external, 10C rise) |
| **Length matching** | High-speed pairs: match within 0.5mm (USB), 2mm (general) |

### 3.2 Thermal Management

| Rule | Description |
|------|-------------|
| **Thermal relief** | Always use spokes connecting pads to copper pours |
| **No thermal relief** | → cold joints, tombstoning during reflow |
| **Spoke width** | >= 0.25mm (typical 0.3mm) |
| **Spoke count** | 4 spokes standard, 2 for small pads |
| **Pour clearance from high-speed** | >= 0.5mm from high-speed traces |
| **Solid fills only** | No hatched/grid copper (causes manufacturing issues) |
| **Thermal via array** | For exposed pads: 5-9 vias, 0.3mm drill, 1mm grid |

### 3.3 Copper Pour Rules

| Rule | Description |
|------|-------------|
| **Min copper island** | Remove islands < 0.5mm — they float and cause shorts |
| **Pour-to-trace clearance** | >= trace-to-trace clearance (0.15mm our project) |
| **Pour-to-pad clearance** | >= 0.2mm for different nets |
| **Pour orphan removal** | Remove isolated copper fragments after pour |
| **Pour near board edge** | Keep >= 0.5mm from edge (0.3mm absolute min) |

### 3.4 Via Placement Best Practices

| Rule | Description |
|------|-------------|
| **Via-in-pad** | Avoid unless using filled vias (extra cost). Solder flows through open via |
| **Via-near-pad offset** | >= 1mm from pad center for open vias |
| **Fanout vias** | Place within 1.27mm of BGA/QFP pads |
| **Via stitching** | Ground pour stitching every 5-10mm for EMC |
| **Via current capacity** | Single 0.3mm drill via ≈ 1A continuous |
| **Return path vias** | Place ground vias near signal vias for return current |

### 3.5 Pad Design Rules

| Rule | Description |
|------|-------------|
| **Pad extension beyond drill** | >= 0.15mm per side (annular ring) |
| **Pad-to-pad same component** | Follow IPC-7351 for footprint; verify with JLCPCB 3D |
| **Tombstone prevention** | Equal pad sizes, equal trace connections, symmetric paste |
| **Solder thief pads** | Add for asymmetric thermal mass on passives |
| **Test point pads** | Min 1mm diameter, accessible from one side |

### 3.6 Mechanical & Assembly

| Rule | Description |
|------|-------------|
| **Mounting holes** | M3: drill 3.2mm, pad 6mm; M2.5: drill 2.7mm, pad 5mm |
| **Board corners** | Radius >= 0.5mm to prevent cracking |
| **Panelization** | V-score: 0.8mm min board thickness; tab-route: 3mm min tab width |
| **Breakaway tabs** | 3 perforations per tab, 0.5mm drill, 0.3mm web |
| **Connector placement** | Edge connectors need 0mm setback from board edge (pad flush) |
| **Heavy component** | Support pads >= 2x component footprint area |

### 3.7 EMC / Signal Integrity

| Rule | Description |
|------|-------------|
| **Ground plane** | Unbroken under high-speed signals |
| **Decoupling cap placement** | < 3mm from IC power pins |
| **Crystal routing** | Guard ring around crystal, no traces under crystal |
| **Differential pairs** | Maintain constant spacing, route parallel, avoid vias |
| **USB 2.0 impedance** | 90 ohm differential, length match within 0.15mm |

---

## Part 4 — JLCPCB Common Rejection Reasons

### 4.1 Top 15 Rejection/Warning Causes

| # | Issue | JLCPCB Response | Prevention |
|---|-------|----------------|------------|
| 1 | **Silkscreen overlapping pads** | Auto-removed, flagged as warning | Move text to Fab layer |
| 2 | **Insufficient annular ring** (< 0.15mm) | Reject or flag | Via size - drill >= 0.3mm (0.15mm ring) |
| 3 | **Trace/space below minimum** (< 5 mil 2L) | Reject | DRC check before export |
| 4 | **Copper too close to board edge** (< 0.3mm) | Reject | Edge clearance rule |
| 5 | **Missing solder mask layer** | Reject (empty back mask) | Always export both mask layers |
| 6 | **Acid traps** at acute-angle junctions | Warning, may reject | Use 45-degree routing |
| 7 | **Via-in-pad without specification** | Warning | Offset vias from pads or order filled vias |
| 8 | **NPTH too close to copper** (< 2mm) | Flag | Increase clearance |
| 9 | **Soldermask bridge too narrow** (< 0.1mm) | Bridge auto-removed | Reduce mask expansion or increase pad gap |
| 10 | **Holes not matching drill increment** | Rounded to nearest 0.05mm | Use 0.05mm multiples |
| 11 | **Missing drill file** | Reject | Verify gerber package contains .drl files |
| 12 | **Outline not closed** | Reject or query | Check Edge.Cuts layer is a closed polygon |
| 13 | **Solder paste on NPTH** | Warning | No paste layer on mounting holes |
| 14 | **Trace crossing board outline** | Reject | Keep all copper inside Edge.Cuts |
| 15 | **Starved thermal connections** | Warning | Ensure spoke width >= 0.25mm |

### 4.2 JLCPCB DFM Tool Categories

| JLCPCB Code | Category | Impact |
|-------------|----------|--------|
| Silkscreen to Pad | Text overlap | Auto-removed, warning |
| Silkscreen to Hole | Text overlap | Auto-removed, warning |
| Solder Mask Bridge | Mask gap too narrow | Bridge removed, solder risk |
| Mask Exceeding Trace | Mask overflow | Cosmetic, usually OK |
| Trace Clearance | Spacing violation | Reject if < absolute min |
| Via Annular Ring | Via undersized | Reject if < 0.075mm |
| Component Spacing | Placement too close | PCBA rejection |
| Missing Solder Mask | No mask on area | Reject if layer empty |
| Copper Sliver | Thin copper fragment | Peeling risk, warning |
| Acid Trap | Acute angle | Warning, manual review |
| Insufficient Overlap | Pad/via/trace overlap | Connectivity risk |
| Drill Hole Size | Below/above limits | Adjusted or rejected |

---

## Part 5 — Project-Specific Issues & Fixes (History)

### 5.1 Previously Fixed Issues (v1.0 → v1.8)

#### Silkscreen-to-pad DANGER
**Problem**: Footprint Reference/Value text on SilkS layer overlaps SMD pads.
**Solution**: Move ALL footprint text to Fab layer (`F.Fab` / `B.Fab`).
**File**: `board.py` — `_component_placeholders()`, set `text_layer` to Fab for all footprints.

#### Silkscreen-to-hole DANGER
**Problem**: Mounting hole Reference text on `F.SilkS` at (0,0) overlaps the hole.
**Solution**: Change mounting hole Reference layer to `F.Fab`.
**File**: `primitives.py` — `mounting_hole()`, line with `"F.SilkS"` → `"F.Fab"`.

#### gr_text near mounting holes
**Problem**: Board labels (gr_text) placed within 6mm of mounting hole centers.
**Solution**: Move labels away from holes. Known hole positions: (10,7), (150,7), (10,68), (150,68), (55,37.5), (105,37.5).
**File**: `board.py` — `_silkscreen_labels()`.

#### Component spacing (C1/C2 vs U3)
**Problem**: Capacitors C1/C2 too close to AMS1117 (SOT-223).
**Solution**: Increase Y offset from +/-5mm to +/-7mm from U3 center.
**Files**: `board.py` (placement), `routing.py` (C1_POS/C2_POS constants).

#### Via annular ring
**Problem**: Via annular ring < 0.075mm (JLCPCB absolute minimum).
**Solution**: All vias must have `(size - drill) / 2 >= 0.075mm`. Standard vias use 0.46mm/0.20mm (ring=0.13mm). Right-side button approach vias use 0.35mm/0.20mm (ring=0.075mm).
**File**: `routing.py` — check all `_via_net()` calls.

#### SOP-16 merged pad apertures
**Problem**: KiCad's gerber export didn't rotate pad apertures for pre-rotated footprints.
**Solution**: `_pre_rotate_element()` in `footprints.py` swaps pad width/height for 90/270 deg rotation.
**File**: `footprints.py` — `_pre_rotate_element()`.

#### Soldermask bridge
**Problem**: Mask openings on close pads create solder bridges.
**Solution**: Reduce mask expansion or increase pad spacing. JLCPCB minimum mask bridge = 0.1mm.
**File**: `footprints.py` — pad definitions with `(solder_mask_margin ...)`.

#### CPL position corrections
**Problem**: JLCPCB 3D model origin differs from footprint center.
**Solution**: Add offset in `_JLCPCB_POS_CORRECTIONS`. Only needed when model origin != body center.
**File**: `jlcpcb_export.py`.
- U1 (ESP32): +(0, 3.62) — asymmetric pin layout
- J1 (USB-C): NO correction — symmetric body
- SW_PWR: NO correction — symmetric body

#### CPL rotation corrections
**Problem**: JLCPCB 3D model default orientation doesn't match KiCad footprint.
**Solution**: Per-footprint DB correction (generic) or per-component override.
**File**: `jlcpcb_export.py` — `_JLCPCB_ROT_OVERRIDES` and `_JLCPCB_ROT_CORRECTIONS`.

### 5.2 Project-Specific Component Lessons

| Component | Lesson |
|-----------|--------|
| PAM8403 C5122557 | Narrow SOP-16 (3.9mm body), NOT wide SOIC-16W (7.5mm) |
| JST PH 2P | Drill 0.85mm (JLCPCB min 0.80mm) |
| USB-C shield THT | Drill 0.60mm, pad 1.1x2.0mm, mask margin -0.1mm |
| USB-C NPTH positioning | 0.65mm (component pegs 0.50mm) — was 0.35mm |
| TF-01A SD slot NPTH | 1.00mm (datasheet "2-1.00") — was 0.50mm |
| MSK12C02 switch NPTH | 0.90mm (component pegs 0.75mm) — was 0.45mm |
| NPTH general rule | ALWAYS check manufacturer datasheet for peg size, never guess |

### 5.3 Project DFM Constants (verify_dfm_v2.py)

| Test Category | Our Threshold | JLCPCB Min | Notes |
|---------------|--------------|------------|-------|
| Trace width | 0.15mm | 0.127mm (5 mil) | Conservative |
| Trace spacing | 0.15mm | 0.127mm (5 mil) | Conservative |
| Annular ring | 0.13mm | 0.075mm (absolute) | Standard via |
| Pad-to-edge | 0.3mm | 0.3mm | Matches JLCPCB |
| Pad spacing | 0.15mm | 0.127mm | Slightly conservative |
| Via-to-SMD | 0.15mm | 0.127mm | Conservative |
| Via ring-to-pad | 0.10mm | 0.10mm | Matches JLCPCB |
| PTH-to-trace | 0.15mm | 0.127mm | Conservative |
| Trace-to-edge | 0.2mm | 0.2mm | Matches JLCPCB |
| Soldermask bridge | 0.1mm | 0.1mm (multilayer) | Matches JLCPCB |
| Silkscreen-to-hole | 0.5mm | 0.5mm | Matches JLCPCB |
| Silkscreen-to-pad | 0.15mm | 0.15mm | Matches JLCPCB |
| Silkscreen line width | 0.15mm | 0.15mm | Standard |
| PTH-to-PTH edge gap | 0.15mm | 0.15mm | Conservative |
| Slot min width | 0.5mm | 0.5mm | NPTH minimum |
| Sharp corner angle | 90 deg | 90 deg | Acid trap prevention |
| Drill-to-trace | 0.15mm | 0.15mm | Our custom test |
| Trace-to-pad (diff net) | 0.10mm | 0.10mm | Our custom test |
| Via approach clearance | 0.10mm | 0.10mm | Our custom test |

---

## Part 6 — Quick Reference Card

### Absolute Minimums (JLCPCB 2-Layer, Will Be Rejected Below These)

```
Trace width:     0.127mm (5 mil)     | Via drill:       0.3mm (12 mil)
Trace spacing:   0.127mm (5 mil)     | Via pad:         0.6mm (24 mil)
Annular ring:    0.075mm (3 mil)     | Hole (PTH):      0.15mm
Mask bridge:     0.075mm (3 mil)     | Hole (NPTH):     0.5mm
Cu to edge:      0.3mm               | Silk stroke:     0.15mm (6 mil)
Trace to edge:   0.2mm               | Silk height:     1.0mm (40 mil)
```

### Recommended (Safe for Production — Our Project Defaults)

```
Trace width:     0.15mm+             | Via:             0.46/0.20mm (ring 0.13mm)
Trace spacing:   0.15mm+             | Via (tight):     0.35/0.20mm (ring 0.075mm)
Pad spacing:     0.15mm+             | Mask expansion:  0.05mm (SMD)
Cu to edge:      0.5mm+              | Mask bridge:     0.1mm+
PTH-to-trace:    0.15mm+             | Silk-to-pad:     0.15mm+
```

### PCBA Assembly Minimums

```
SMD-to-SMD:      0.3mm               | Fiducial pad:    1.0mm
SMD-to-edge:     0.3mm               | Fiducial mask:   2.0mm
Process edge:    5mm                  | Tooling hole:    2.0mm
```
