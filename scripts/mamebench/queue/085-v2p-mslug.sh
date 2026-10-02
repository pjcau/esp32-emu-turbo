# V2h with the frame-deep pipeline (fork: the display accepts the next frame's
# bands while this frame's tail is still being sent). Hashes = reference; the
# video split "copy" (the wait for a band buffer) must drop from 6 ms to ~0,
# core 0 to ~19 ms. Screen must stay clean.
NEOBAND=2 scripts/mamebench/board_run.sh v2p mslug 70
