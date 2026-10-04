#!/bin/sh
# retro_go_build.sh <app>: build one retro-go app in the ESP-IDF container and
# print only the errors and the binary size (the full log goes to /tmp).
# Works on any machine with the espressif/idf:v5.4 image (the Mac has it).
set -e
cd "$(dirname "$0")/.."
LOG=${TMPDIR:-/tmp}/retro-go-build-$1.log
# The build switches of mame-go are read from the environment at configure
# time: forward the ones that are set. Without them the Neo Geo band code is
# not even compiled, so check a mame-go change with the play build's options:
#   NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 AUDIO_MIX_HZ=16000 scripts/retro_go_build.sh mame-go
ENVS=""
for v in NB_LINES LCD_BUFS BAND_INTERNAL NEOBAND AUDIO_MIX_HZ MAMEBENCH MAMEPROF NEOPROF M68KJIT LCD_MHZ NEOSND_PRIO SD_HOLD_CS RG_SDKCONFIG_EXTRA; do
    eval "val=\${$v:-}"
    [ -n "$val" ] && ENVS="$ENVS -e $v=$val"
done
docker compose -f docker-compose.retro-go.yml run --rm $ENVS retro-go-build sh -c "rm -f $1/sdkconfig; python rg_tool.py --target=esp32-emu-turbo build $1" > "$LOG" 2>&1 || true
grep -E "error:|undefined reference|multiple definition|binary size|region .* overflowed" "$LOG" | sed 's/.*\/project\///' | sort -u | head -40
ls -l "retro-go/$1/build/$1.bin" 2>/dev/null | awk '{print "BIN", $5}'
