FROM --platform=linux/amd64 kicad/kicad:10.0

# Official KiCad image includes kicad-cli for headless schematic export.
# Used to export schematics to SVG/PDF without a GUI.
# Also includes Python3 for schematic generation.
# Tag: 10.0 tracks the latest KiCad 10.0.x stable release.

RUN apt-get update -qq && apt-get install -y -qq python3 > /dev/null 2>&1 || true

WORKDIR /project

ENTRYPOINT ["kicad-cli"]
