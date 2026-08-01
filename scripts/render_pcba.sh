#!/usr/bin/env bash
# Render photorealistic 3D PCBA views with the KiCad raytracer.
#
# This is the ONLY board-imagery pipeline: it replaced the old SVG/PNG/GIF
# renderer (render_pcb_svg.py / render_pcb_animation.py, deleted). All board
# pictures in docs and in release_jlcpcb/renders/ come from these renders.
#
# Steps:
#   1. inject-3d-models.py maps footprints to KiCad STEP models (temp copy,
#      the source .kicad_pcb is never modified)
#   2. kicad-cli pcb render produces 11 camera presets + 2 transparent
#      variants at 1920x1080, --quality high (raytracing), in parallel
#
# The .kicad_pcb must have its zones FILLED first (make pcb-filled) or the
# renders show a board with no copper pours. Use `make render-pcb`, which
# enforces that dependency.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

PCB_SRC="hardware/kicad/esp32-emu-turbo.kicad_pcb"
PCB_TMP="$(mktemp -t pcba-render)"
PCB="$PCB_TMP.kicad_pcb"
OUT="website/static/img/renders/pcba"
W=1920; H=1080

trap 'rm -f "$PCB_TMP" "$PCB"' EXIT
mkdir -p "$OUT"

echo "[1/3] Injecting 3D component models..."
python3 scripts/inject-3d-models.py "$PCB_SRC" "$PCB"

echo "[2/3] Rendering 13 raytraced views (parallel)..."

render() { # name, extra kicad-cli args...
  local name="$1"; shift
  kicad-cli pcb render -o "$OUT/$name.png" \
    --width $W --height $H --quality high "$@" "$PCB" >/dev/null &
}

# ── TOP SIDE (front: buttons, LEDs) ──
render pcba-top            --side top --floor --background opaque \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4
render pcba-iso-front      --rotate "-45,0,30" --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5
render pcba-iso-back       --rotate "-45,0,210" --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5
render pcba-low-angle      --rotate "-25,0,20" --perspective --floor --background opaque \
  --zoom 0.6 --light-top 0.7 --light-camera 0.5 --light-side 0.6 --light-side-elevation 30
render pcba-detail-mcu     --rotate "-40,0,15" --perspective --background opaque \
  --zoom 2.0 --pan "2,1,0" --light-top 0.85 --light-camera 0.5 --light-side 0.4

# ── BOTTOM SIDE (back: ESP32, ICs, connectors) — needs --side bottom + --rotate ──
render pcba-bottom             --side bottom --floor --background opaque \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4
render pcba-bottom-iso-front   --side bottom --rotate "-45,0,30" --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5
render pcba-bottom-iso-back    --side bottom --rotate "-45,0,210" --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5
render pcba-bottom-low-angle   --side bottom --rotate "-25,0,20" --perspective --floor --background opaque \
  --zoom 0.6 --light-top 0.7 --light-camera 0.5 --light-side 0.6 --light-side-elevation 30
render pcba-bottom-detail-mcu  --side bottom --rotate "-40,0,15" --perspective --background opaque \
  --zoom 2.0 --pan "2,1,0" --light-top 0.85 --light-camera 0.5 --light-side 0.4
render pcba-bottom-detail-power --side bottom --rotate "-40,0,195" --perspective --background opaque \
  --zoom 2.0 --pan "2,1,0" --light-top 0.85 --light-camera 0.5 --light-side 0.4

# ── Transparent variants (compositing / docs) ──
render pcba-top-transparent    --side top --background transparent \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4
render pcba-bottom-transparent --side bottom --background transparent \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4

wait

echo "[3/3] Syncing release renders..."
mkdir -p release_jlcpcb/renders
cp "$OUT/pcba-top.png" "$OUT/pcba-bottom.png" "$OUT/pcba-iso-front.png" \
   release_jlcpcb/renders/

COUNT=$(ls "$OUT"/pcba-*.png | wc -l | tr -d ' ')
if [ "$COUNT" -lt 13 ]; then
  echo "ERROR: expected 13 renders, found $COUNT" >&2
  exit 1
fi
echo "Done: $COUNT renders in $OUT (top/bottom/iso synced to release_jlcpcb/renders/)"
