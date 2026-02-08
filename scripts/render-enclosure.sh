#!/usr/bin/env bash
# Render OpenSCAD enclosure model to PNG from multiple angles using Docker
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

OUTPUT_DIR="$PROJECT_ROOT/website/static/img/renders"
IMGSIZE="1920,1080"

mkdir -p "$OUTPUT_DIR"

# View definitions: name|rotation|part|distance
VIEWS=(
    "front|25,0,340|assembly|500"
    "back|205,0,20|assembly|500"
    "top|90,0,0|assembly|500"
    "exploded|55,0,330|exploded|600"
)

for entry in "${VIEWS[@]}"; do
    IFS='|' read -r name rotation view_part distance <<< "$entry"
    echo "==> Rendering enclosure-${name}.png (part=${view_part})..."

    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
        openscad \
        -o "/output/enclosure-${name}.png" \
        --imgsize "$IMGSIZE" \
        --camera "0,0,12.5,${rotation},${distance}" \
        -D "part=\"${view_part}\"" \
        /project/enclosure.scad
done

echo "==> Renders exported to $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"
