#!/usr/bin/env bash
# Render OpenSCAD enclosure model to PNG from multiple angles using Docker
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

OUTPUT_DIR="$PROJECT_ROOT/website/static/img/renders/enclosure"
IMGSIZE="1920,1080"

mkdir -p "$OUTPUT_DIR"

# View definitions: name|camera_center|rotation|part|distance
# Camera format: center_x,center_y,center_z,rot_x,rot_y,rot_z,distance
VIEWS=(
    "front|0,0,12.5|25,0,340|assembly|500"
    # back: as seen when you physically turn the console around — up stays up,
    # left/right mirror (matches pcba-bottom.png). The old rz=20 rendered the
    # back upside down (flipped over the top edge, left/right NOT mirrored).
    "back|0,0,12.5|205,0,200|assembly|500"
    # true plan view of the front face (the V1 "top" was the bottom edge)
    "top|0,0,12.5|0,0,0|assembly|430"
    # bottom edge: USB-C plug opening, SD slot, power switch slot
    "ports|0,0,12|90,0,0|assembly|300"
    "exploded|0,0,20|55,0,330|exploded|600"
    # XZ cut at Y=0: battery, ESP32, PCB, panel + cable space, cap stack
    "cross-section|0,-10,13|60,0,0|cross_section|300"
    # YZ cut through the Y button column: panel pocket, tail fold, guide well
    "cross-section-yz|53,0,14|70,0,90|cross_section_yz|180"
    "fit-check|0,0,10|35,0,340|fit_check|420"
    # top shell from the inside: display frame, screw bosses, guide wells
    "top-inside|0,0,5|35,0,20|top_inside|420"
    # same, bare shell: bosses with insert sockets, frame, wells, LED pipes
    "top-inside-bare|0,0,5|35,0,20|top_inside_bare|420"
    # bottom shell without the PCB: pocket, columns, ribs, lever hinges
    "bottom-inside|0,0,8|35,0,20|bottom_inside|420"
    # one top boss cut through its axis: insert socket o3.1 x 3.5, relief, wall
    "boss-section|70,30.5,20|70,0,0|boss_section|60"
    "pcb|0,0,1|25,0,340|pcb|300"
)

for entry in "${VIEWS[@]}"; do
    IFS='|' read -r name center rotation view_part distance <<< "$entry"
    echo "==> Rendering enclosure-${name}.png (part=${view_part})..."

    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm \
        --user "$(id -u):$(id -g)" openscad \
        -o "/output/enclosure/enclosure-${name}.png" \
        --imgsize "$IMGSIZE" \
        --camera "${center},${rotation},${distance}" \
        -D "part=\"${view_part}\"" \
        /project/enclosure.scad
done

# cache-bust the doc page: every render link carries the render time, so a
# browser never shows a stale PNG under an unchanged file name
STAMP="$(date +%Y%m%d%H%M)"
sed -i -E "s#(/img/renders/enclosure/enclosure-[a-z-]+\.png)(\?v=[0-9]+)?#\1?v=${STAMP}#g" \
    "$PROJECT_ROOT/website/docs/design/enclosure.md"
echo "==> Doc image links stamped ?v=${STAMP}"

echo "==> Renders exported to $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"
