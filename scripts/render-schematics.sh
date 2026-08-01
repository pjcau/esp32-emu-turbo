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
echo "==> Merging the all-sheets PDF (the website's 'Download all sheets' link)..."
# This file used to be a one-off hand merge that nothing regenerated: the
# per-sheet PDFs moved on and the combined download silently served the
# old schematic. Merged here, from the exact PDFs exported above, so it
# can no longer drift. Requires ghostscript (brew install ghostscript).
COMBINED="$OUTPUT_DIR/esp32-emu-turbo-schematics.pdf"
PDF_LIST=()
for sheet in "${SHEETS[@]}"; do
    [ -f "$OUTPUT_DIR/${sheet}.pdf" ] && PDF_LIST+=("$OUTPUT_DIR/${sheet}.pdf")
done
if [ "${#PDF_LIST[@]}" -eq 0 ]; then
    echo "ERROR: no per-sheet PDFs to merge" >&2
    exit 1
fi
gs -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile="$COMBINED" "${PDF_LIST[@]}"
echo "  merged ${#PDF_LIST[@]} sheets -> $COMBINED"

echo ""
echo "==> Schematics exported to $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"
