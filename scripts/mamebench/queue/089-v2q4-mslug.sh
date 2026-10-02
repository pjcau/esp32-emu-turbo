# V2h, 8-line bands, four buffers AND a four-deep band queue (fork): both
# hand-over latencies hidden. Hashes = reference; "copy" and "rest" in the video
# split must be ~0; core 0 should land near 19.5 ms.
NEOBAND=2 scripts/mamebench/board_run.sh v2q4 mslug 70
