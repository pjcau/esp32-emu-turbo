# 16-line pool with 3 internal band buffers, paid for by 3 (not 5) display DMA
# buffers, plus the 25 MHz bus. Hashes = reference; "copy w" should drop; watch the
# screen (fewer DMA buffers) and the "display" ms.
NB_LINES=16 LCD_MHZ=25 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 scripts/mamebench/board_run.sh v2pool16-3b mslug 70
