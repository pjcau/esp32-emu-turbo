# V2 again, with the display task copying each band to a PSRAM stage on arrival
# (no more waiting in the submit): hashes must be the reference ones; core 0's
# "rest" in the video split must be near 0 and the total below V1's 22.64.
NEOBAND=2 scripts/mamebench/board_run.sh v2s mslug 70
