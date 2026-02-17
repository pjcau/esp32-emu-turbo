FROM kicad/kicad:nightly

# Official KiCad image includes kicad-cli for headless schematic export.
# Used to export schematics to SVG/PDF without a GUI.
# Also includes Python3 for schematic generation.
# Tag: nightly tracks KiCad 10 (9.99.0 → 10.0.0), switch to 10.0 when stable.

RUN apt-get update -qq && apt-get install -y -qq python3 > /dev/null 2>&1 || true

WORKDIR /project

ENTRYPOINT ["kicad-cli"]
