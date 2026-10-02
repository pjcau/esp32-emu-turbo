# V2h, frame-deep pipeline, 8-line bands with four buffers (fork): the band-buffer
# wait ("copy" in the video split) must fall from 6 ms to ~0. Hashes = reference
# (the band height changed: the PC compare on 4 games is asked for separately).
NEOBAND=2 scripts/mamebench/board_run.sh v2b8 mslug 70
