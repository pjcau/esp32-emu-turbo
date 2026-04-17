#!/usr/bin/env bash
# generate_ibom.sh — regenerate Interactive HTML BOM
#
# Renders website/static/ibom/ibom.html from hardware/kicad/esp32-emu-turbo.kicad_pcb
# via the esp32-emu-turbo-kibot Docker image (ships generate_interactive_bom.py).
#
# Usage:
#   scripts/generate_ibom.sh          # regen only if ibom.html is stale
#   scripts/generate_ibom.sh --force  # always regen

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PCB="$PROJECT_DIR/hardware/kicad/esp32-emu-turbo.kicad_pcb"
OUT_DIR="$PROJECT_DIR/website/static/ibom"
OUT="$OUT_DIR/ibom.html"
IMAGE="esp32-emu-turbo-kibot:latest"

FORCE=0
[ "${1:-}" = "--force" ] && FORCE=1

if [ ! -f "$PCB" ]; then
    echo "iBOM: PCB not found at $PCB" >&2
    exit 1
fi

if [ "$FORCE" -eq 0 ] && [ -f "$OUT" ]; then
    # Skip when ibom.html is newer than the PCB
    if [ "$OUT" -nt "$PCB" ]; then
        echo "iBOM: up-to-date (ibom.html newer than PCB)."
        exit 0
    fi
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "iBOM: Docker image $IMAGE not found — build it via docker/kibot/Dockerfile." >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

echo "iBOM: regenerating $OUT …"
docker run --rm --platform linux/amd64 \
    --entrypoint bash \
    -v "$PROJECT_DIR:/project" -w /project \
    "$IMAGE" \
    -c "Xvfb :99 -screen 0 1024x768x24 & sleep 1; \
        DISPLAY=:99 generate_interactive_bom.py \
            --dest-dir /project/website/static/ibom \
            --name-format ibom \
            --no-browser \
            --dark-mode \
            /project/hardware/kicad/esp32-emu-turbo.kicad_pcb" \
    2>&1 | tail -5

echo "iBOM: done → $OUT"
