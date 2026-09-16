#!/usr/bin/env bash
# Export the OpenSCAD enclosure to STL via Docker.
#
# Two consumers, one source (hardware/enclosure/enclosure.scad), ONE
# folder — 3d_case/ in the project root (no STL lives under website/):
#   1. 3d_case/*.stl — the print set, every part in its PRINT orientation
#      (flat face on the bed); the top shell is part="case_top_print"
#      (front face down), not the mirrored assembly copy;
#   2. 3d_case/viewer/{assembly,exploded}.stl + viewer/parts/*.stl — the
#      website 3D viewer's set in ASSEMBLY coordinates (Z=0 = back face).
#      Docusaurus serves 3d_case/ through `staticDirectories`, so
#      viewer.html loads them from <site>/viewer/...
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

echo "==> Viewer set (assembly coordinates) -> $VIEWER_DIR"
scad 3d/assembly.stl assembly
scad 3d/exploded.stl exploded
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
mv "$RENDERS"/3d/*.stl "$VIEWER_DIR/"
mv "$RENDERS"/3d/parts/*.stl "$VIEWER_DIR/parts/"
rmdir "$RENDERS/print" "$RENDERS/3d/parts" "$RENDERS/3d"

echo "==> Interference gate"
python3 "$SCRIPT_DIR/verify_enclosure_collision.py"

echo "==> Done"
ls -la "$PRINT_DIR" "$VIEWER_DIR" "$VIEWER_DIR/parts"
