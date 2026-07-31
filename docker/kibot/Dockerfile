FROM ghcr.io/inti-cmnb/kicad10_auto:latest

# KiBot external DFM analysis container
# Provides: KiBot 1.9.x + KiCad 10 (DRC/ERC/design report)
# Must track the local KiCad major version (10.0.0) — a KiCad 9 container
# cannot reliably load boards saved by KiCad 10.
# Platform: runs under emulation on arm64 (M1/M2 Mac)

WORKDIR /project
ENTRYPOINT ["kibot"]
