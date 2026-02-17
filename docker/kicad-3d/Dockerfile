FROM kicad/kicad:nightly-full

# KiCad 10 (nightly-full) bundles kicad-packages3d — no apt install needed.
# Tag: nightly-full tracks KiCad 10 (9.99.0 → 10.0.0), switch to 10.0-full when stable.

WORKDIR /project
ENTRYPOINT ["kicad-cli"]
