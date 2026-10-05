#!/bin/sh
# board_install.sh <fork-commit> [VAR=value ...]: build the PLAY firmware of mame-go
# (no MAMEBENCH, no NEOPROF) from a given retro-go fork commit with the given build
# switches, install it over the SD updater and leave the board in the launcher for
# the user. Example (the 22 ms build of 2026-10-02, job 101):
#   scripts/mamebench/board_install.sh bbcf99f5 NB_LINES=16 NEOBAND=2
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
REV=$1; shift
git pull --ff-only origin main
git submodule update --init --recursive
git -C retro-go fetch -q origin
git -C retro-go checkout -q "$REV"
git -C retro-go submodule update --init --recursive
ENVS=""
for kv in "$@"; do ENVS="$ENVS -e $kv"; done
# the old binary goes first: a failed build must not leave it to be installed
# (2026-10-05: a link error, and the previous build went to the board as the new one)
OUT=$(docker compose -f docker-compose.retro-go.yml run --rm $ENVS retro-go-build sh -c "rm -f mame-go/sdkconfig mame-go/build/mame-go.bin; python rg_tool.py --target=esp32-emu-turbo build mame-go" 2>&1)
echo "$OUT" | grep -E "error:|undefined reference|binary size" | head -5
if echo "$OUT" | grep -q -E "error:|undefined reference|FAILED:"; then
    echo "the build failed: not installing" >&2
    git -C retro-go checkout -q - 2>/dev/null || true
    git submodule update --init --recursive
    exit 1
fi
# A play build must read the gamepad. The bench code replaces it with a script and
# is the only place that prints "MAMEBENCH frames": the binary itself says which
# build it is, whatever the environment was (2026-10-03: the user got a board on
# which no button worked in the arcade games).
BIN=$(find retro-go/mame-go/build -maxdepth 1 -name "mame-go.bin" | head -1)
if [ -z "$BIN" ]; then
    echo "no retro-go/mame-go/build/mame-go.bin after the build: not installing" >&2
    exit 1
fi
if grep -a -q "MAMEBENCH frames" "$BIN"; then
    echo "$BIN is a BENCH build (it ignores the gamepad): not installing. The build directory belongs to root (Docker): clean it in the container and run again:" >&2
    echo "  docker compose -f docker-compose.retro-go.yml run --rm retro-go-build sh -c 'rm -rf mame-go/build'" >&2
    exit 1
fi
python3 scripts/sd_update.py --console mame-go 2>&1 | grep -E "Error|error|put done" | head -2
python3 scripts/board_ctl.py launcher >/dev/null 2>&1 || true
git -C retro-go checkout -q - 2>/dev/null || true
git submodule update --init --recursive
echo "installed mame-go from fork $REV with: $*; board in the launcher"
