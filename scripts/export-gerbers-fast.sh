#!/usr/bin/env bash
# Fast gerber export using local kicad-cli (no Docker overhead for gerbers/drill).
# Docker is still needed for zone fill (pcbnew Python API not available in kicad-cli).
#
# Benchmarks on M1 Max:
#   Docker version:  ~4.7s (3 container starts)
#   This version:    ~2.5s (1 container + 2 local calls)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PCB_FILE="esp32-emu-turbo.kicad_pcb"
KICAD_DIR="$PROJECT_ROOT/hardware/kicad"
GERBER_DIR="$KICAD_DIR/gerbers"

# Clean and recreate output directory
rm -rf "$GERBER_DIR"
mkdir -p "$GERBER_DIR"

if [ ! -f "$KICAD_DIR/$PCB_FILE" ]; then
    echo "ERROR: $KICAD_DIR/$PCB_FILE not found. Run 'make generate-pcb' first."
    exit 1
fi

# Step 1: Zone fill via Docker (pcbnew Python API — no local alternative)
echo "==> Step 1: Filling zones via Docker (pcbnew API)..."
docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
    --entrypoint python3 \
    kicad-pcb \
    /scripts/kicad_fill_zones.py "/project/$PCB_FILE"

# Step 2+3: Local kicad-cli (no Docker overhead)
if command -v kicad-cli &>/dev/null; then
    echo "==> Step 2: Exporting Gerbers (local kicad-cli)..."
    kicad-cli pcb export gerbers \
        --output "$GERBER_DIR/" \
        --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
        --subtract-soldermask \
        --use-drill-file-origin \
        "$KICAD_DIR/$PCB_FILE"

    echo "==> Step 3: Exporting drill files (local kicad-cli)..."
    kicad-cli pcb export drill \
        --output "$GERBER_DIR/" \
        --format excellon \
        --drill-origin plot \
        --excellon-units mm \
        --generate-map \
        --map-format gerberx2 \
        "$KICAD_DIR/$PCB_FILE"
else
    echo "WARN: kicad-cli not found locally, falling back to Docker..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
        kicad-pcb pcb export gerbers \
        --output /gerbers/ \
        --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
        --subtract-soldermask --use-drill-file-origin \
        "/project/$PCB_FILE"

    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
        kicad-pcb pcb export drill \
        --output /gerbers/ \
        --format excellon --drill-origin plot \
        --excellon-units mm --generate-map --map-format gerberx2 \
        "/project/$PCB_FILE"
fi

echo ""
echo "==> Gerbers exported to $GERBER_DIR"
ls "$GERBER_DIR"/*.g* "$GERBER_DIR"/*.drl 2>/dev/null | wc -l | xargs -I{} echo "  {} files exported"

echo "==> Creating JLCPCB-ready ZIP..."
mkdir -p "$KICAD_DIR/jlcpcb"
rm -f "$KICAD_DIR/jlcpcb/gerbers.zip"
(cd "$GERBER_DIR" && zip -j "$KICAD_DIR/jlcpcb/gerbers.zip" \
    ./*.gtl ./*.g1 ./*.g2 ./*.gbl \
    ./*.gto ./*.gbo ./*.gts ./*.gbs \
    ./*.gtp ./*.gbp ./*.gm1 \
    ./*.drl ./*.gbrjob 2>/dev/null)
echo "  ZIP: $KICAD_DIR/jlcpcb/gerbers.zip"
