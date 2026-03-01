FROM kicad/kicad:nightly-full

# KiCad 10 (nightly-full) bundles kicad-packages3d — no apt install needed.
# Tag: nightly-full is KiCad 10 pre-release (v9.99.0). Will switch to 10.0-full when stable tag appears.

WORKDIR /project
ENTRYPOINT ["kicad-cli"]
