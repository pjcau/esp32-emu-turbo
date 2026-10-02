# The same at 25 MHz: if dmawait does not move, the clock is not reaching the bus
# (or the bus is not the limit); if it drops ~20 %, the clock applies.
NB_LINES=16 LCD_MHZ=25 NEOBAND=2 scripts/mamebench/board_run.sh dma25 mslug 70
