#!/bin/bash
# mamebench.sh <M68KJIT 0|1> <rom> [secs]: MAMEBENCH+NEOPROF build (NOBUILD=1 skips it), resume slot 0,
# print MAMEBENCH hashes and the 68000/video ms (NEOPROF) lines
cd "$(dirname "$0")/../.."
if [ -z "$NOBUILD" ]; then
OUT=$(timeout 1500 docker compose -f docker-compose.retro-go.yml run --rm -e M68KJIT=$1 -e NEOPROF=1 -e MAMEBENCH=1 -e MAMEPROF=${MAMEPROF:-0} -e MAMEGO_CLEARCHECK=${MAMEGO_CLEARCHECK:-0} retro-go-build sh -c "python rg_tool.py --target=esp32-emu-turbo build mame-go" 2>&1 | grep -E "error:|binary size" | head -3)
echo "$OUT"
echo "$OUT" | grep -q "binary size" || { echo "BUILD FAILED, nothing installed"; exit 1; }
timeout 400 python3 scripts/sd_update.py --console mame-go 2>&1 | grep -E "Error|error|put done" | head -2
fi
timeout 30 python3 scripts/board_ctl.py launcher >/dev/null 2>&1; sleep 1
timeout 90 python3 scripts/mamebench/wait_launcher.py >/dev/null
timeout 200 python3 - "$2" "${3:-60}" <<'PY'
import sys, time, re
sys.path.insert(0, 'scripts')
from board_ctl import Board
b = Board('/dev/ttyACM0')
b.send("volume 0", wait=r"^CTL volume", timeout=3, echo=False)
import os
b.launch("neogeo", sys.argv[1], resume=os.environ.get("RESUME", "1") != "0", slot=0)
t0 = time.time()
while time.time() - t0 < float(sys.argv[2]):
    l = b.readline()
    if l and re.search(r"MAMEBENCH|MAMESAMPLE|MAMEGO|NEOPROF|M68KJIT|CLEARCHECK|Guru|panic", l): print(l.strip()[:200], flush=True)
PY
