#!/usr/bin/env bash
# Export each KiCad schematic sheet to SVG + combined PDF using Docker
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

KICAD_DIR="$PROJECT_ROOT/hardware/kicad"
OUTPUT_DIR="$PROJECT_ROOT/website/static/img/schematics"

mkdir -p "$OUTPUT_DIR"

SHEETS=(
    "01-power-supply"
    "02-mcu"
    "03-display"
    "04-audio"
    "05-sd-card"
    "06-controls"
    "07-joystick"
)

echo "==> Exporting ${#SHEETS[@]} schematic sheets to SVG..."
for sheet in "${SHEETS[@]}"; do
    if [ -f "$KICAD_DIR/${sheet}.kicad_sch" ]; then
        echo "  Exporting ${sheet}.svg ..."
        docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
            kicad \
            sch export svg \
            --output /output/ \
            --exclude-drawing-sheet \
            --no-background-color \
            "/project/${sheet}.kicad_sch"
    else
        echo "  SKIP: ${sheet}.kicad_sch not found"
    fi
done

echo ""
echo "==> Exporting combined PDF..."
for sheet in "${SHEETS[@]}"; do
    if [ -f "$KICAD_DIR/${sheet}.kicad_sch" ]; then
        docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
            kicad \
            sch export pdf \
            --output "/output/${sheet}.pdf" \
            "/project/${sheet}.kicad_sch"
    fi
done

echo ""
echo "==> Schematics exported to $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"
