#!/usr/bin/env bash
# Export Gerbers + drill files from KiCad PCB using Docker (kicad-cli).
# Step 1: Fill all zones via pcbnew Python API (kicad-cli 9.0 doesn't have --fill-all-zones)
# Step 2: Export Gerbers + drill files
# This is critical for internal copper planes (In1.Cu=GND, In2.Cu=3V3/5V).
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

echo "==> Step 1: Filling all zones via pcbnew Python API..."

# Fill zones using KiCad Python API (saves filled_polygon data into the .kicad_pcb)
docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
    --entrypoint python3 \
    kicad-pcb \
    /scripts/kicad_fill_zones.py "/project/$PCB_FILE"

echo ""
echo "==> Step 2: Exporting Gerbers..."

# Export Gerber files for all copper + mask + silkscreen + edge layers
docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
    kicad-pcb \
    pcb export gerbers \
    --output /gerbers/ \
    --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
    --subtract-soldermask \
    --use-drill-file-origin \
    "/project/$PCB_FILE"

echo ""
echo "==> Step 3: Exporting drill files..."

# Export Excellon drill files
docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
    kicad-pcb \
    pcb export drill \
    --output /gerbers/ \
    --format excellon \
    --drill-origin plot \
    --excellon-units mm \
    --generate-map \
    --map-format gerberx2 \
    "/project/$PCB_FILE"

echo ""
echo "==> Gerbers exported to $GERBER_DIR"
ls -la "$GERBER_DIR"

echo ""
echo "==> Creating JLCPCB-ready ZIP..."
mkdir -p "$KICAD_DIR/jlcpcb"
rm -f "$KICAD_DIR/jlcpcb/gerbers.zip"
(cd "$GERBER_DIR" && zip -j "$KICAD_DIR/jlcpcb/gerbers.zip" \
    ./*.gtl ./*.g1 ./*.g2 ./*.gbl \
    ./*.gto ./*.gbo ./*.gts ./*.gbs \
    ./*.gtp ./*.gbp ./*.gm1 \
    ./*.drl ./*.gbrjob 2>/dev/null)
echo "  ZIP: $KICAD_DIR/jlcpcb/gerbers.zip"
