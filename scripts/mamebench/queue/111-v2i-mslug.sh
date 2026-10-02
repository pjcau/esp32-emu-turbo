# V2i with the first-frame fix and the original plotter (fork c654abbc): accepted
# bands scaled in place, staging only on demand. Hashes = reference; the 68000
# toward 7.5, core1 ym2610 toward 7, "copy w" small; screen clean.
NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 scripts/mamebench/board_run.sh v2i mslug 70
