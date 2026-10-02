# mamebench results

One file per board run, committed from the PC that has the board, so the
development machine can read it after a `git pull`:

    scripts/mamebench/results/<YYYY-MM-DD>-<step>-<game>.txt

`<step>` is the plan step the run measures (`v0`, `v1`, `f1`, ...). The file
is the raw `mamebench.sh` output; `mbsum.py <file>` summarises it. Keep the
hashes line in the commit message when it differs from the reference.
