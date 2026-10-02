# The faster sprite plotter (opaque/empty word fast paths, pens on the stack) on
# V2i, 16-line bands: hashes = reference; sprites should drop from ~5.1 toward 3.5.
NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 scripts/mamebench/board_run.sh plotter mslug 70
