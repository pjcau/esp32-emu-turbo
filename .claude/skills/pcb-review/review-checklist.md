# PCB Review Scoring Criteria

## 1. Power Integrity (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Power trace width | -1 to -3 | All power nets (VBUS, +5V, +3V3, GND, BAT+) must use >=0.5mm traces |
| GND vias near ICs | -1 per IC | Each power IC needs >=2 GND vias within 8mm |
| GND plane (In1.Cu) | -3 | Continuous GND zone required on In1.Cu |
| Power plane (In2.Cu) | -2 | +3V3 and +5V zones required on In2.Cu |

## 2. Signal Integrity (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Display bus matching | -1 to -3 | LCD_D0-D7 length mismatch < 10mm ideal, < 20mm acceptable |
| Data trace width | -1 to -2 | Data signals must use >=0.2mm traces |
| USB diff pair | -1 to -2 | D+/D- length mismatch < 2mm ideal, < 5mm acceptable |
| Via transitions | -0.5 per net | High-speed nets should minimize layer changes |

## 3. Thermal (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Thermal vias per IC | -2 per IC | U2 (IP5306), U3 (AMS1117), U5 (PAM8403) need >=3 GND vias within 5mm |
| Total GND vias | -1 | Board should have >=10 total GND vias |

## 4. Manufacturability (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Min trace width | -3 | All traces >= 0.09mm (JLCPCB 4-layer min) |
| Via dimensions | -2 | Drill >= 0.15mm, annular ring >= 0.13mm |
| Board aspect ratio | -1 | Width/height <= 4:1 to prevent warping |

## 5. EMI/EMC (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| GND plane present | -4 | Continuous GND on In1.Cu is critical |
| Inner layer signals | -2 max | Signal traces on In1/In2 break plane continuity |
| Signal layer grouping | -1 | High-speed signals should stay on one layer |

## 6. Mechanical (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Mounting symmetry | -1 | Holes should be symmetric about board center |
| Connector access | -0.5 per connector | Connectors should be within 5mm of board edge |
| Board size | -1 | Should fit handheld form factor (< 180x90mm) |

## JLCPCB 4-Layer Manufacturing Limits Reference

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| Trace width | 0.09mm | 0.2mm |
| Trace spacing | 0.09mm | 0.15mm |
| Via drill | 0.15mm | 0.3mm |
| Via annular ring | 0.13mm | 0.175mm |
| Board edge clearance | 0.3mm | 0.5mm |
| Drill-to-edge | 0.4mm | 0.5mm |
| Silkscreen width | 0.15mm | 0.2mm |
| Board thickness | 0.6-2.0mm | 1.6mm |
