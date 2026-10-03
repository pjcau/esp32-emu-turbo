#!/bin/sh
# board_run.sh <step> <rom-name> [secs] [JIT 0|1]: one MAMEBENCH run on the board PC,
# saved under results/ and pushed, so the development machine can read it.
#   scripts/mamebench/board_run.sh v0 mslug 70
#   NEOBAND=1 scripts/mamebench/board_run.sh v1 mslug 70     (band renderer build)
set -e
cd "$(dirname "$0")/../.."
# One board, one console: two of these at once drive the same serial port and
# build directory and spoil both runs (2026-10-03: twice). The lock is held for
# the life of this process; a job script started from here inherits the mark.
if [ -z "$BOARD_LOCK_HELD" ]; then
    exec 9> /tmp/esp32-emu-turbo-board.lock
    if ! flock -n 9; then
        echo "another board job is running (lock /tmp/esp32-emu-turbo-board.lock): not starting" >&2
        exit 75
    fi
    export BOARD_LOCK_HELD=1
fi
STEP=$1; GAME=$2; SECS=${3:-70}; JIT=${4:-0}
[ -n "$STEP" ] && [ -n "$GAME" ] || { echo "usage: $0 <step> <rom-name> [secs] [JIT]"; exit 1; }
git pull --ff-only origin main
git submodule update --init --recursive
OUT=scripts/mamebench/results/$(date +%F)-$STEP-$GAME.txt
scripts/mamebench/mamebench.sh "$JIT" /sd/roms/neogeo/$GAME.zip "$SECS" > "$OUT"
scripts/mamebench/mbsum.py "$OUT"
git add "$OUT"
git commit -q -m "mamebench: $STEP run on $GAME ($(git -C retro-go rev-parse --short HEAD))

$(scripts/mamebench/mbsum.py "$OUT")"
git pull --rebase -q origin main || true    # the development machine pushes too: rebase, then push
git push
echo "pushed $OUT"
