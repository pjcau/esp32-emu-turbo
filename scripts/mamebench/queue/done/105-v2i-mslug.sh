# V2i: accepted bands scaled in place, no copies to PSRAM unless the emulator is
# short of internal buffers (then the oldest band is staged). 16-line bands, 3
# internal buffers, 3 DMA buffers. Hashes = reference; "copy w" (PSRAM-drawn) and
# core1 ym2610 should drop, the 68000 toward 7.5; core 0 near 20.
NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 scripts/mamebench/board_run.sh v2i mslug 70
