# V2 (bands handed to the display task, no PSRAM frame bitmap) with D1 + D2:
# hashes must be the reference ones (the band hash walks the same bytes in the
# same order); core 0 loses the band copy, core 1 the PSRAM read. Look at the
# screen: tearing or a wrong band would be a core-sync bug, not a drawing one.
NEOBAND=2 scripts/mamebench/board_run.sh v2 mslug 70
