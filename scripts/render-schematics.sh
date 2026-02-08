#!/usr/bin/env bash
# Export KiCad schematic to SVG using Docker
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

KICAD_DIR="$PROJECT_ROOT/hardware/kicad"
OUTPUT_DIR="$PROJECT_ROOT/website/static/img/schematics"

mkdir -p "$OUTPUT_DIR"

echo "==> Exporting schematic to SVG..."
docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
    kicad \
    sch export svg \
    --output /output/ \
    --exclude-drawing-sheet \
    --no-background-color \
    /project/esp32-emu-turbo.kicad_sch

echo "==> Schematics exported to $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"
