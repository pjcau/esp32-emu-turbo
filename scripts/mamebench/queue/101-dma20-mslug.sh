# The bus question, measured: the display task's wait for a DMA buffer per frame
# ("dmawait" in the NEOPROF core1 line) and the buffers sent, 16-line pool, 20 MHz.
NB_LINES=16 NEOBAND=2 scripts/mamebench/board_run.sh dma20 mslug 70
