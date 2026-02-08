#!/usr/bin/env bash
# Master render script: build Docker images and run all renders
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=============================="
echo " ESP32 Emu Turbo — Full Render"
echo "=============================="

echo ""
echo "[1/3] Building Docker images..."
docker compose -f "$PROJECT_ROOT/docker-compose.yml" build

echo ""
echo "[2/3] Rendering schematics..."
"$SCRIPT_DIR/render-schematics.sh"

echo ""
echo "[3/3] Rendering 3D enclosure..."
"$SCRIPT_DIR/render-enclosure.sh"

echo ""
echo "=============================="
echo " All renders complete."
echo "=============================="
