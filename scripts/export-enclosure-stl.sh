#!/usr/bin/env bash
# Export the OpenSCAD enclosure to STL via Docker.
#
# ONE set of part files, from one source (hardware/enclosure/enclosure.scad):
#   1. 3d_case/*.stl — the print set, every part in its PRINT orientation
#      (flat face on the bed). The website 3D viewer loads THESE files and
#      only moves them (3d_case/viewer/placement.json: rotation + offset),
#      so the preview is the print file — there is no second "preview"
#      geometry that could differ (the 2026-09 top was printed mirrored
#      while a separate preview export looked right);
#   2. hardware/enclosure/reference/*.stl — the scad assembly copies, NOT
#      served: only the gates use them, to prove each placed print file
#      lands exactly where the design puts it (verify_enclosure_stl S0);
#   3. 3d_case/viewer/parts/{part_display,part_pcb}.stl — the two things in
#      the viewer that are not printed.
# Docusaurus serves 3d_case/ through `staticDirectories`.
# OpenSCAD writes to the container's /output mount (website/static/img/
# renders) and the files are moved out afterwards.
#
# Ends by running the interference gate so an STL set is never shipped
# from a model whose shells cut into what they enclose.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RENDERS="$PROJECT_ROOT/website/static/img/renders"     # docker: /output
PRINT_DIR="$PROJECT_ROOT/3d_case"          # everything lands here
VIEWER_DIR="$PRINT_DIR/viewer"

mkdir -p "$RENDERS/3d/parts" "$RENDERS/print" "$VIEWER_DIR/parts"

scad() {  # scad <output path under /output> <part selector>
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm --user "$(id -u):$(id -g)" openscad \
        -o "/output/$1" -D "part=\"$2\"" /project/enclosure.scad \
        2>&1 | grep -E "WARNING|ERROR|Facets" | sed "s|^|    $2: |" || true
}

REF_DIR="$PROJECT_ROOT/hardware/enclosure/reference"
mkdir -p "$REF_DIR"

echo "==> Assembly references + non-printed viewer parts"
for p in case_top case_bottom part_display part_dpad part_btn_a part_btn_b \
         part_btn_x part_btn_y part_start part_menu part_select \
         part_shoulder_l part_shoulder_r part_pcb part_straps; do
    scad "3d/parts/$p.stl" "$p"
done

echo "==> Print set (bed orientation) -> $PRINT_DIR"
# selector|file  — caps and levers print face-down: their face is the
# lowest Z in assembly coords already, no transform needed
for entry in case_top_print:case_top case_bottom:case_bottom \
             part_dpad:dpad part_btn_a:btn_a part_btn_b:btn_b \
             part_btn_x:btn_x part_btn_y:btn_y part_start:start \
             part_menu:menu part_select:select \
             part_shoulder_l:lever_l part_shoulder_r:lever_r \
             part_strap_print:battery_strap_x2; do
    sel="${entry%%:*}"; name="${entry##*:}"
    scad "print/$name.stl" "$sel"
done
mv "$RENDERS"/print/*.stl "$PRINT_DIR/"
mv "$RENDERS"/3d/parts/part_display.stl "$RENDERS"/3d/parts/part_pcb.stl "$VIEWER_DIR/parts/"
mv "$RENDERS"/3d/parts/*.stl "$REF_DIR/"
rmdir "$RENDERS/print" "$RENDERS/3d/parts" "$RENDERS/3d"

echo "==> Viewer placement (print files, moved — never re-exported)"
python3 "$SCRIPT_DIR/enclosure_placement.py"

echo "==> Interference gate"
python3 "$SCRIPT_DIR/verify_enclosure_collision.py"

echo "==> STL audit (the exported files, measured)"
python3 "$SCRIPT_DIR/verify_enclosure_stl.py"

echo "==> Done"
ls -la "$PRINT_DIR" "$VIEWER_DIR" "$VIEWER_DIR/parts" "$REF_DIR"
