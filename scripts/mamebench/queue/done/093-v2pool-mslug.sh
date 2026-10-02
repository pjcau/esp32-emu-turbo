# V2h with the band buffer pool (4 internal + 32 PSRAM reserve, 36-deep queue):
# hashes = reference; "copy" (buffer wait) ~0; "copy w" KB/frame = how much was
# drawn in PSRAM; core 0 near 19.5 ms. Screen clean.
NEOBAND=2 scripts/mamebench/board_run.sh v2pool mslug 70
