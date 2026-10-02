#!/bin/sh
# board_run.sh <step> <rom-name> [secs] [JIT 0|1]: one MAMEBENCH run on the board PC,
# saved under results/ and pushed, so the development machine can read it.
#   scripts/mamebench/board_run.sh v0 mslug 70
#   NEOBAND=1 scripts/mamebench/board_run.sh v1 mslug 70     (band renderer build)
set -e
cd "$(dirname "$0")/../.."
STEP=$1; GAME=$2; SECS=${3:-70}; JIT=${4:-0}
[ -n "$STEP" ] && [ -n "$GAME" ] || { echo "usage: $0 <step> <rom-name> [secs] [JIT]"; exit 1; }
git pull --ff-only
git submodule update --init --recursive
OUT=scripts/mamebench/results/$(date +%F)-$STEP-$GAME.txt
scripts/mamebench/mamebench.sh "$JIT" /sd/roms/neogeo/$GAME.zip "$SECS" > "$OUT"
scripts/mamebench/mbsum.py "$OUT"
git add "$OUT"
git commit -q -m "mamebench: $STEP run on $GAME ($(git -C retro-go rev-parse --short HEAD))

$(scripts/mamebench/mbsum.py "$OUT")"
git push
echo "pushed $OUT"
