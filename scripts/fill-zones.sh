#!/usr/bin/env bash
# Fill the board's copper zones, in place.
#
# Why this is its own script: `generate_pcb` writes the .kicad_pcb WITHOUT any
# `filled_polygon` — the fill needs the pcbnew Python API, which kicad-cli does
# not expose, so it only exists inside the Docker image. Anything that consumes
# the board after generation therefore has to run this, or it silently works on
# a board with no copper pours:
#
#   * gerbers exported unfilled ship a board with no planes;
#   * renders drawn unfilled show a board with no planes;
#   * verify-all's zone-fill gate goes red, and because the pre-commit DFM hook
#     runs that gate, an unrelated commit gets blocked citing zone fills.
#
# All three happened. See docs/known-issues.md section C.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PCB_FILE="${1:-esp32-emu-turbo.kicad_pcb}"
KICAD_DIR="$PROJECT_ROOT/hardware/kicad"

if [ ! -f "$KICAD_DIR/$PCB_FILE" ]; then
    echo "ERROR: $KICAD_DIR/$PCB_FILE not found. Run 'make generate-pcb' first." >&2
    exit 1
fi

docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
    --entrypoint python3 \
    kicad-pcb \
    /scripts/kicad_fill_zones.py "/project/$PCB_FILE"

# Fail loudly rather than leaving an unfilled board behind: a silent no-op here
# is exactly the failure this script exists to prevent.
python3 - "$KICAD_DIR/$PCB_FILE" <<'PY'
import re, sys
n = len(re.findall(r'\(filled_polygon', open(sys.argv[1]).read()))
if n == 0:
    sys.exit("ERROR: zone fill produced no filled_polygon — board left unfilled")
print(f"  zones filled: {n} filled_polygon entries")
PY
