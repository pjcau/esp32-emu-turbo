# V2h, 8-line bands, four buffers, four-deep band queue, with the display sync
# fixed (the hang of 087/055/089 was the state-load hourglass interleaving its
# i80 stream with the band stream). Hashes = reference; "copy" and "rest" in the
# video split ~0; core 0 near 19.5 ms; screen clean.
NEOBAND=2 scripts/mamebench/board_run.sh v2q4 mslug 70
