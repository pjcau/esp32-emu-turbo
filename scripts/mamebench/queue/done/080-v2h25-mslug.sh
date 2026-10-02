# B1: the LCD write clock at 25 MHz with V2h (bus 13.9 -> 11.1 ms a full frame).
# The hashes cannot see the bus: look hard at the screen (webcam, several shots,
# also in play) for artefacts, tearing, wrong colours. Report core 0 and display ms.
LCD_MHZ=25 NEOBAND=2 scripts/mamebench/board_run.sh v2h25 mslug 70
