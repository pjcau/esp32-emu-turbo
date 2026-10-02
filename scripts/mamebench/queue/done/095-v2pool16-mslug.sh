# The band buffer pool with 16-line bands (2 internal + 32 PSRAM reserve): half the
# per-band overhead of job 093. Hashes = reference (PC proof at 16 lines done);
# "copy" ~0; expect core 0 around 20.5 ms. Screen clean.
NB_LINES=16 NEOBAND=2 scripts/mamebench/board_run.sh v2pool16 mslug 70
