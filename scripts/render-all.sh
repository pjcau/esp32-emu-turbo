#!/usr/bin/env bash
# Master render script: generate schematic, build Docker images, run all renders
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=============================="
echo " ESP32 Emu Turbo — Full Render"
echo "=============================="

echo ""
echo "[1/4] Generating KiCad schematic from Python spec..."
docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm generate-sch

echo ""
echo "[2/4] Building Docker images..."
docker compose -f "$PROJECT_ROOT/docker-compose.yml" build

echo ""
echo "[3/4] Rendering schematics (SVG export)..."
"$SCRIPT_DIR/render-schematics.sh"

echo ""
echo "[4/4] Rendering 3D enclosure..."
"$SCRIPT_DIR/render-enclosure.sh"

echo ""
echo "=============================="
echo " All renders complete."
echo "=============================="
