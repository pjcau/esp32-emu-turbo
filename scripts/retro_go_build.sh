#!/bin/sh
# retro_go_build.sh <app>: build one retro-go app in the ESP-IDF container and
# print only the errors and the binary size (the full log goes to /tmp).
# Works on any machine with the espressif/idf:v5.4 image (the Mac has it).
set -e
cd "$(dirname "$0")/.."
LOG=${TMPDIR:-/tmp}/retro-go-build-$1.log
docker compose -f docker-compose.retro-go.yml run --rm retro-go-build sh -c "python rg_tool.py --target=esp32-emu-turbo build $1" > "$LOG" 2>&1 || true
grep -E "error:|undefined reference|multiple definition|binary size|region .* overflowed" "$LOG" | sed 's/.*\/project\///' | sort -u | head -40
ls -l "retro-go/$1/build/$1.bin" 2>/dev/null | awk '{print "BIN", $5}'
