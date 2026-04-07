---
name: pcba-render
description: Generate photorealistic 3D PCBA renders using KiCad raytracer. Produces top, bottom, isometric, and detail views at 1920x1080 with floor reflections and studio lighting. Use after PCB changes, for documentation, or manufacturing review.
allowed-tools: Bash, Read, Glob
---

# Photorealistic PCBA Rendering

Generates high-quality raytraced 3D renders of the assembled PCB using local `kicad-cli pcb render` with the KiCad raytracer engine.

## Critical Rules

- ALWAYS inject 3D models first (step 1) before rendering
- NEVER modify the source PCB — inject-3d-models outputs to a temp file
- Renders use `--quality high` (raytracing) for photorealism
- Output to `website/static/img/renders/` for website integration

## Steps

### 1. Inject 3D Component Models

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/inject-3d-models.py \
  hardware/kicad/esp32-emu-turbo.kicad_pcb \
  /tmp/pcba-render.kicad_pcb
```

This maps 61 footprints to KiCad standard STEP models (resistors, caps, ICs, connectors, buttons). 10 components have no standard model (FPC, SD slot, speaker, inductor).

### 2. Render All Views

Run all 11 camera presets. Each takes ~5s (raytracing). Launch in parallel for speed.

IMPORTANT: For bottom-side isometric/detail views, you MUST combine `--side bottom` with `--rotate`.
Using only `--rotate` with positive X angles does NOT flip to the bottom — it just tilts the top view.

```bash
OUT="website/static/img/renders/pcba"
PCB="/tmp/pcba-render.kicad_pcb"
W=1920; H=1080

# ── TOP SIDE (front: buttons, LEDs) ────────────────────────

# View 1: Top — flat orthogonal, studio lighting
kicad-cli pcb render -o "$OUT/pcba-top.png" \
  --width $W --height $H --side top \
  --quality high --floor --background opaque \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4 \
  "$PCB"

# View 2: Top isometric front-left — hero shot
kicad-cli pcb render -o "$OUT/pcba-iso-front.png" \
  --width $W --height $H --rotate "-45,0,30" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5 \
  "$PCB"

# View 3: Top isometric back-right — alternate angle
kicad-cli pcb render -o "$OUT/pcba-iso-back.png" \
  --width $W --height $H --rotate "-45,0,210" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5 \
  "$PCB"

# View 4: Top low angle — dramatic perspective
kicad-cli pcb render -o "$OUT/pcba-low-angle.png" \
  --width $W --height $H --rotate "-25,0,20" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.6 --light-top 0.7 --light-camera 0.5 --light-side 0.6 \
  --light-side-elevation 30 \
  "$PCB"

# View 5: Top detail — button + LED area (zoomed)
kicad-cli pcb render -o "$OUT/pcba-detail-mcu.png" \
  --width $W --height $H --rotate "-40,0,15" \
  --quality high --perspective --background opaque \
  --zoom 2.0 --pan "2,1,0" \
  --light-top 0.85 --light-camera 0.5 --light-side 0.4 \
  "$PCB"

# ── BOTTOM SIDE (back: ESP32, ICs, connectors) ────────────
# NOTE: All bottom views use --side bottom + --rotate

# View 6: Bottom — flat orthogonal
kicad-cli pcb render -o "$OUT/pcba-bottom.png" \
  --width $W --height $H --side bottom \
  --quality high --floor --background opaque \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4 \
  "$PCB"

# View 7: Bottom isometric front-left
kicad-cli pcb render -o "$OUT/pcba-bottom-iso-front.png" \
  --width $W --height $H --side bottom --rotate "-45,0,30" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5 \
  "$PCB"

# View 8: Bottom isometric back-right
kicad-cli pcb render -o "$OUT/pcba-bottom-iso-back.png" \
  --width $W --height $H --side bottom --rotate "-45,0,210" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5 \
  "$PCB"

# View 9: Bottom low angle — dramatic
kicad-cli pcb render -o "$OUT/pcba-bottom-low-angle.png" \
  --width $W --height $H --side bottom --rotate "-25,0,20" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.6 --light-top 0.7 --light-camera 0.5 --light-side 0.6 \
  --light-side-elevation 30 \
  "$PCB"

# View 10: Bottom detail — ESP32 + USB-C area (zoomed)
kicad-cli pcb render -o "$OUT/pcba-bottom-detail-mcu.png" \
  --width $W --height $H --side bottom --rotate "-40,0,15" \
  --quality high --perspective --background opaque \
  --zoom 2.0 --pan "2,1,0" \
  --light-top 0.85 --light-camera 0.5 --light-side 0.4 \
  "$PCB"

# View 11: Bottom detail — power area (IP5306, AMS1117, PAM8403)
kicad-cli pcb render -o "$OUT/pcba-bottom-detail-power.png" \
  --width $W --height $H --side bottom --rotate "-40,0,195" \
  --quality high --perspective --background opaque \
  --zoom 2.0 --pan "2,1,0" \
  --light-top 0.85 --light-camera 0.5 --light-side 0.4 \
  "$PCB"
```

### 3. Generate Transparent Variants (optional)

For compositing in documentation or marketing:

```bash
# Transparent background versions
for side in top bottom; do
  kicad-cli pcb render -o "$OUT/pcba-${side}-transparent.png" \
    --width $W --height $H --side $side \
    --quality high --background transparent \
    --light-top 0.85 --light-camera 0.3 --light-side 0.4 \
    "$PCB"
done
```

### 4. Verify Output

```bash
ls -lh website/static/img/renders/pcba/pcba-*.png
echo "---"
echo "Renders complete. Open in browser:"
echo "  open website/static/img/renders/pcba/pcba-iso-front.png"
```

### 5. Cleanup

```bash
rm -f /tmp/pcba-render.kicad_pcb
```

## Camera Preset Reference

| # | View | Side | Rotation | Zoom | Floor | Use Case |
|---|------|------|----------|------|-------|----------|
| 1 | Top | top | — | 1.0 | yes | Documentation, BOM review |
| 2 | Top Iso Front | — | -45,0,30 | 0.7 | yes | Hero shot, README |
| 3 | Top Iso Back | — | -45,0,210 | 0.7 | yes | Alternate marketing angle |
| 4 | Top Low Angle | — | -25,0,20 | 0.6 | yes | Dramatic product shot |
| 5 | Top Detail | — | -40,0,15 | 2.0 | no | Button/LED area zoom |
| 6 | Bottom | bottom | — | 1.0 | yes | Back-side inspection |
| 7 | Bottom Iso Front | bottom | -45,0,30 | 0.7 | yes | ESP32/ICs overview |
| 8 | Bottom Iso Back | bottom | -45,0,210 | 0.7 | yes | Alternate back angle |
| 9 | Bottom Low Angle | bottom | -25,0,20 | 0.6 | yes | Dramatic back shot |
| 10 | Bottom Detail MCU | bottom | -40,0,15 | 2.0 | no | ESP32 + USB-C zoom |
| 11 | Bottom Detail Power | bottom | -40,0,195 | 2.0 | no | IP5306/AMS1117/PAM8403 zoom |

## Lighting Presets

| Preset | Top | Camera | Side | Side Elev | Effect |
|--------|-----|--------|------|-----------|--------|
| Studio | 0.85 | 0.3 | 0.4 | 60 | Even, professional |
| Dramatic | 0.7 | 0.5 | 0.6 | 30 | Shadows, contrast |
| Bright | 0.95 | 0.4 | 0.5 | 60 | Showroom, web |

## Key Files

- `scripts/inject-3d-models.py` — Maps footprints to KiCad 3D STEP models
- `hardware/kicad/esp32-emu-turbo.kicad_pcb` — Source PCB
- `website/static/img/renders/` — Output directory
- Local `kicad-cli` — KiCad 10 CLI with raytracer (no Docker needed)
