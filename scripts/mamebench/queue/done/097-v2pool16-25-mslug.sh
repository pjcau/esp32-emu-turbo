# 16-line pool + LCD bus at 25 MHz: with the waits gone the display consumes at
# the bus rate, so a faster bus means fewer bands spilled to PSRAM ("copy w").
# Hashes = reference; screen checked for artefacts as in job 080.
NB_LINES=16 LCD_MHZ=25 NEOBAND=2 scripts/mamebench/board_run.sh v2pool16-25 mslug 70
