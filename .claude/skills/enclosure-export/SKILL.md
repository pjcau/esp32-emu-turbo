---
name: enclosure-export
model: claude-haiku-4-5-20251001
description: Export OpenSCAD enclosure parts to STL files for 3D printing
disable-model-invocation: true
allowed-tools: Bash, Read, Glob
argument-hint: [all|top|bottom|buttons|dpad|abxy]
---

# Enclosure STL Export for 3D Printing

Export individual enclosure parts to STL files for FDM/SLA 3D printing.

**Argument** (optional): `all` (default), or specific part name.

## Prerequisites

Docker must be running with the OpenSCAD image built:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
docker compose build openscad
```

## Export Commands

### Export all printable parts

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
mkdir -p hardware/enclosure/stl

# Top shell (display side)
docker compose run --rm openscad \
    -o /output/case_top.stl \
    -D 'part="case_top"' \
    /project/enclosure.scad

# Bottom shell (battery side)
docker compose run --rm openscad \
    -o /output/case_bottom.stl \
    -D 'part="case_bottom"' \
    /project/enclosure.scad

# D-pad cap
docker compose run --rm openscad \
    -o /output/dpad.stl \
    -D 'part="part_dpad"' \
    /project/enclosure.scad

# ABXY button caps (4 individual)
for btn in a b x y; do
    docker compose run --rm openscad \
        -o "/output/btn_${btn}.stl" \
        -D "part=\"part_btn_${btn}\"" \
        /project/enclosure.scad
done

# Start, Menu, Select caps
for cap in start menu select; do
    docker compose run --rm openscad \
        -o "/output/${cap}.stl" \
        -D "part=\"part_${cap}\"" \
        /project/enclosure.scad
done

# Shoulder buttons
docker compose run --rm openscad \
    -o /output/shoulder_l.stl \
    -D 'part="part_shoulder_l"' \
    /project/enclosure.scad

docker compose run --rm openscad \
    -o /output/shoulder_r.stl \
    -D 'part="part_shoulder_r"' \
    /project/enclosure.scad
```

### Export a single part

```bash
docker compose run --rm openscad \
    -o /output/<part_name>.stl \
    -D 'part="<part_selector>"' \
    /project/enclosure.scad
```

## Part Selector Reference

| Part | Selector | Print Notes |
|------|----------|-------------|
| Top shell | `case_top` | Print upside-down (flat face down) |
| Bottom shell | `case_bottom` | Print as-is (flat face down) |
| D-pad | `part_dpad` | Print cap-face down |
| Button A | `part_btn_a` | Print cap-face down |
| Button B | `part_btn_b` | Print cap-face down |
| Button X | `part_btn_x` | Print cap-face down |
| Button Y | `part_btn_y` | Print cap-face down |
| Start | `part_start` | Print cap-face down |
| Menu | `part_menu` | Print cap-face down |
| Select | `part_select` | Print cap-face down |
| Shoulder L | `part_shoulder_l` | Print cap-face down |
| Shoulder R | `part_shoulder_r` | Print cap-face down |

## 3D Printing Recommendations

### Material
- **PLA/PETG** for shells (strong, easy to print)
- **TPU** for button caps (flexible, better feel) — optional
- **PLA** for button caps works fine too

### Print Settings (FDM)
- Layer height: 0.2mm (shells), 0.12mm (button caps for detail)
- Infill: 20-30% (shells), 100% (button caps)
- Supports: Not needed for shells (designed for supportless printing)
- Tolerances: 0.3mm clearance built into alignment lip design

### Post-processing
- Light sanding on mating surfaces for smooth fit
- Test-fit button caps in cutouts before final assembly
- M3 heat-set inserts in screw boss holes (optional, can self-tap into PLA)

## Post-export Verification

```bash
ls -la website/static/img/renders/*.stl 2>/dev/null || ls -la hardware/enclosure/stl/*.stl 2>/dev/null
```

## Key Files

- `hardware/enclosure/enclosure.scad` — Main enclosure (all part selectors)
- `hardware/enclosure/modules/*.scad` — Component modules
- `docker-compose.yml` — OpenSCAD Docker service
- `website/docs/enclosure.md` — Design documentation
