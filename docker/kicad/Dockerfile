FROM --platform=linux/amd64 kicad/kicad:nightly

# Official KiCad image includes kicad-cli for headless schematic export.
# Used to export schematics to SVG/PDF without a GUI.
# Also includes Python3 for schematic generation.
# Tag: nightly is KiCad 10 pre-release (v9.99.0). Will switch to 10.0 when stable tag appears.

RUN apt-get update -qq && apt-get install -y -qq python3 > /dev/null 2>&1 || true

WORKDIR /project

ENTRYPOINT ["kicad-cli"]
