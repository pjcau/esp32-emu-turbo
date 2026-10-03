#!/bin/sh
# board_install.sh <fork-commit> [VAR=value ...]: build the PLAY firmware of mame-go
# (no MAMEBENCH, no NEOPROF) from a given retro-go fork commit with the given build
# switches, install it over the SD updater and leave the board in the launcher for
# the user. Example (the 22 ms build of 2026-10-02, job 101):
#   scripts/mamebench/board_install.sh bbcf99f5 NB_LINES=16 NEOBAND=2
set -e
cd "$(dirname "$0")/../.."
REV=$1; shift
git pull --ff-only origin main
git submodule update --init --recursive
git -C retro-go fetch -q origin
git -C retro-go checkout -q "$REV"
git -C retro-go submodule update --init --recursive
ENVS=""
for kv in "$@"; do ENVS="$ENVS -e $kv"; done
docker compose -f docker-compose.retro-go.yml run --rm $ENVS retro-go-build sh -c "rm -f mame-go/sdkconfig; python rg_tool.py --target=esp32-emu-turbo build mame-go" 2>&1 | grep -E "error:|binary size" | head -3
python3 scripts/sd_update.py --console mame-go 2>&1 | grep -E "Error|error|put done" | head -2
python3 scripts/board_ctl.py launcher >/dev/null 2>&1 || true
git -C retro-go checkout -q - 2>/dev/null || true
git submodule update --init --recursive
echo "installed mame-go from fork $REV with: $*; board in the launcher"
