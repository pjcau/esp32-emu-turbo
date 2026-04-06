# PCB Review Scoring Criteria

## JLCPCB Manufacturing Rules Reference

### Copper & Traces

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Trace width (1oz) | 0.127mm (5mil) | ≥0.15mm (6mil) | 4-layer: 0.09mm possible |
| Trace spacing | 0.127mm (5mil) | ≥0.15mm (6mil) | Different-net minimum |
| Copper-to-edge | 0.20mm | ≥0.30mm | Copper-to-board-outline |
| Trace-to-pad (diff net) | 0.10mm | ≥0.15mm | Critical for dense areas |
| Trace angles | - | 45° preferred | Never 90° on high-speed |

### Trace Width vs Current (1oz Cu, 10°C rise, external)

| Current | Min Width (external) | Min Width (internal) |
|---------|---------------------|---------------------|
| 0.5A | 0.127mm (5mil) | 0.254mm (10mil) |
| 1.0A | 0.254mm (10mil) | 0.508mm (20mil) |
| 2.0A | 0.762mm (30mil) | 1.27mm (50mil) |
| 3.0A | 1.27mm (50mil) | 2.16mm (85mil) |

### Vias

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Via drill (PTH) | 0.20mm | ≥0.30mm | Aspect ratio ≤10:1 |
| Via outer diameter | 0.45mm | ≥0.60mm | Drill + 2×annular ring |
| Annular ring | 0.13mm | ≥0.15mm | (OD - drill) / 2 |
| Via-to-via (hole edge) | 0.25mm | ≥0.30mm | Hole-to-hole gap |
| Via-to-pad (diff net) | 0.15mm | ≥0.20mm | Ring edge to pad edge |
| Via-to-trace (diff net) | 0.15mm | ≥0.20mm | Ring edge to trace edge |
| Via-in-pad | Avoid | Offset ≥1mm | Unless filled/capped |

### Pads & Holes

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Pad spacing (diff net) | 0.127mm | ≥0.15mm | Edge-to-edge |
| PTH drill min | 0.20mm | ≥0.30mm | |
| NPTH drill min | 0.50mm | ≥0.80mm | Check datasheet |
| Hole-to-hole (PTH) | 0.50mm | ≥0.50mm | Edge-to-edge |
| Pad-to-edge | 0.25mm | ≥0.30mm | Pad edge to board edge |
| THT annular ring | 0.15mm | ≥0.20mm | |

### Soldermask

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Mask bridge (between pads) | 0.10mm | ≥0.12mm | Solder bridge risk |
| Mask expansion | 0.05mm | 0.05mm | Per-side opening |
| Mask registration | ±0.05mm | - | Manufacturing tolerance |
| Mask opening min | 0.10mm | ≥0.15mm | |

### Silkscreen

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Line width | 0.15mm | ≥0.20mm | Thinner may not print |
| Text height | 0.80mm | ≥1.0mm | |
| Silk-to-pad clearance | 0.15mm | ≥0.20mm | Prevents solder issues |
| Silk-to-hole clearance | 0.50mm | ≥0.50mm | |
| Silk on pads | Forbidden | - | Auto-clipped by fab |

### Board

| Parameter | Range | Notes |
|-----------|-------|-------|
| Min board size | 10×10mm | |
| Max board size | 400×500mm | Standard process |
| Thickness | 0.6–2.0mm | 1.6mm standard |
| Layers | 1–32 | 4-layer recommended |
| Copper weight | 1oz, 2oz | 1oz standard |
| Aspect ratio | ≤4:1 | Prevents warping |

---

## 1. Power Integrity (15 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Power trace width | -1 to -3 | Power nets (VBUS, +5V, +3V3, BAT+) ≥0.5mm (≥1A capacity) |
| GND trace/pour width | -1 to -2 | GND connections ≥0.3mm or via zone fill |
| Decoupling cap placement | -1 per IC | 100nF cap within 3mm of every IC VDD pin |
| Bulk caps on power rails | -1 per rail | 10µF+ on each power rail (VBUS, +5V, +3V3, BAT+) |
| GND vias near ICs | -1 per IC | Each power IC needs ≥2 GND vias within 8mm |
| GND plane (In1.Cu) | -3 | Continuous GND zone required on In1.Cu |
| Power plane (In2.Cu) | -2 | +3V3 and +5V zones on In2.Cu |
| Power path resistance | -1 | No thin bottleneck segments in power delivery |

## 2. Signal Integrity (15 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Display bus matching | -1 to -3 | LCD_D0-D7 length mismatch < 10mm ideal, < 20mm acceptable |
| USB diff pair matching | -1 to -3 | D+/D- length mismatch < 2mm, spacing consistent |
| USB impedance | -1 to -2 | 90Ω differential (trace width + spacing vs stackup) |
| 3W rule for parallel traces | -1 per violation | Parallel different-net traces spaced ≥3× trace width |
| Data trace width | -1 to -2 | Data signals ≥0.15mm (JLCPCB min) |
| High-speed over GND plane | -2 | All high-speed traces must route over solid GND plane |
| Via count on high-speed | -0.5 per via | Minimize layer changes on USB, SPI, display bus |
| Trace angle violations | -1 | No 90° corners on high-speed signals (use 45° or arcs) |

## 3. Thermal Management (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Thermal vias per IC | -2 per IC | U2 (IP5306), U3 (AMS1117), U5 (PAM8403) need ≥3 GND vias within 5mm |
| Exposed pad thermal vias | -2 | EP pads (U2 ESOP-8) need thermal vias to inner GND |
| Total GND vias | -1 | Board should have ≥15 total GND stitching vias |
| Power IC copper area | -1 | ≥25mm² copper pour around each power IC |
| Component thermal spacing | -1 | Hot components (U2, U3) ≥5mm apart |

## 4. JLCPCB DFM Compliance (20 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Min trace width | -2 | All traces ≥ 0.15mm (recommended, not just 0.09mm min) |
| Min trace spacing | -2 | All different-net gaps ≥ 0.15mm |
| Via annular ring | -2 | All vias: (OD - drill)/2 ≥ 0.13mm |
| Via-to-via spacing | -1 | Hole-to-hole gap ≥ 0.25mm |
| Via-to-pad spacing | -2 | Ring edge to pad edge ≥ 0.15mm |
| Pad spacing | -2 | Different-net pad edges ≥ 0.15mm |
| Soldermask bridge | -2 | Mask between adjacent pads ≥ 0.10mm |
| Mask openings vs traces | -2 | No mask openings exposing different-net copper |
| Copper-to-edge | -1 | All copper ≥ 0.20mm from board edge |
| Pad-to-edge | -1 | All pads ≥ 0.30mm from board edge |
| Drill sizes valid | -1 | PTH ≥ 0.20mm, NPTH ≥ 0.50mm |
| Silkscreen compliance | -1 | Width ≥ 0.15mm, no silk on pads, ≥0.5mm from holes |
| Fiducial marks | -1 | ≥2 fiducials for SMT assembly alignment |

## 5. EMI/EMC (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| GND plane continuity | -4 | Continuous GND on In1.Cu, no splits under high-speed |
| Return path integrity | -2 | No high-speed traces crossing GND plane gaps |
| Decoupling strategy | -1 | Multi-value caps: 100nF + 10µF near each IC |
| Signal layer grouping | -1 | High-speed signals on same layer where possible |
| Clock/oscillator routing | -1 | Short, direct, over solid ground |
| No antenna loops | -1 | Avoid large current loops in power/signal paths |

## 6. Component Placement & Polarity (15 points)

| Check | Points | Criteria |
|-------|--------|----------|
| IC pin-1 vs datasheet | -5 per IC | CRITICAL: every IC pin-1 must match datasheet orientation |
| LED polarity vs datasheet | -3 per LED | Anode/cathode must match routing direction |
| Connector pin-1 alignment | -3 per conn | FPC, USB-C, JST pin-1 must match footprint |
| CPL rotation accuracy | -2 per comp | JLCPCB 3D model must align with pads |
| BOM-CPL consistency | -2 | Every BOM designator in CPL and vice versa |
| Component courtyard | -1 | No overlapping courtyards (min 0.25mm gap) |
| Passives match datasheet | -1 | All cap/resistor values match schematic |

## 7. Datasheet Physical Compliance (automated via `verify_datasheet.py`)

| Check | Points | Criteria |
|-------|--------|----------|
| Pin count per IC | -2 per IC | Every IC/connector pad count must match datasheet |
| Pad pitch | -2 per comp | Measured pitch within ±0.35mm of datasheet |
| Pad span / body size | -3 per IC | Cross-body pad span matches package (e.g. SOP-16 narrow 3.9mm, not SOIC-16W 7.5mm) |
| NPTH count | -2 per comp | Positioning hole count matches datasheet |
| NPTH drill size | -2 per comp | NPTH drill diameter matches datasheet (±0.05mm) |
| THT drill size | -1 per comp | Through-hole drill matches datasheet (±0.1mm) |
| Datasheet files | -1 | All component datasheets present in `hardware/datasheets/` |

## 8. Mechanical (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Mounting symmetry | -1 | Holes should be symmetric for enclosure fit |
| Connector access | -0.5 per conn | Connectors within 5mm of board edge |
| Board size | -1 | Fits handheld form factor (< 180×90mm) |
| FPC strain relief | -1 | FPC connector near slot, cable bridge < 8mm |
| NPTH positioning holes | -1 | Match datasheet dimensions (±0.15mm) |
| Board outline clearance | -1 | Components ≥3mm from edge for handling |

## 8. Documentation & Assembly (5 points)

| Check | Points | Criteria |
|-------|--------|----------|
| BOM LCSC parts valid | -1 | All LCSC part numbers exist and in stock |
| Gerber file completeness | -1 | ≥12 gerber files in zip (all layers + drill) |
| Silkscreen ref designators | -1 | All refs on Fab layer, none on SilkS |
| Assembly variants documented | -1 | CPL rotation variants for empirical parts |
| Net assignments verified | -1 | All IC pins routed to correct nets |

---

## Scoring

| Rating | Score | Description |
|--------|-------|-------------|
| Excellent | 90-100 | Production-ready, no issues |
| Good | 75-89 | Minor improvements possible |
| Acceptable | 60-74 | Functional but needs DFM attention |
| Poor | 40-59 | Significant issues, risk of assembly failure |
| Critical | <40 | Must fix before ordering |

**Total: 100 points across 8 domains**
