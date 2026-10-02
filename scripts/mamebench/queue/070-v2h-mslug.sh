# V2h: the display scales straight from the band buffer while it keeps up and
# stages only what is left when the next band arrives. Hashes = reference; core 0
# total and the video split "rest" (should be ~0), the 68000 ms (was 6.96 in the
# first V2 run, 8.2 with V1), core1 display ms; the screen must be clean.
NEOBAND=2 scripts/mamebench/board_run.sh v2h mslug 70
