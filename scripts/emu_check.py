#!/usr/bin/env python3
"""Quick 60 fps check across the non-SNES emulators on the card.

For each ROM: launch, press START twice (title screens), then average the
rg_system stats line ("BUSY:xx%, FPS:yy (S:skipped R:rendered+partial)")
for a few seconds. Prints a table; optional webcam snapshot per game.
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from board_ctl import Board  # noqa: E402

GAMES = [  # app, partition, rom  (every app must carry the console: rebuild gwenesis/fmsx/prboom-go after shared changes)
    ("nes", "retro-core", "/sd/roms/nes/Super Mario Bros. + Duck Hunt (USA).nes"),
    ("nes", "retro-core", "/sd/roms/nes/owlia.nes"),
    ("gb", "retro-core", "/sd/roms/gb/Tetris (JUE) (V1.1) [!].gb"),
    ("gbc", "retro-core", "/sd/roms/gbc/Space Invaders (USA, Europe) (GB Compatible).gbc"),
    ("gbc", "retro-core", "/sd/roms/gbc/ucity.gbc"),
    ("sms", "retro-core", "/sd/roms/sms/silvervalley.sms"),
    ("gg", "retro-core", "/sd/roms/gg/Swabby-GG-1.11.gg"),
    ("pce", "retro-core", "/sd/roms/pce/reflectron.pce"),
    ("gen", "gwenesis", "/sd/roms/gen/miniplanets.bin"),
]


def stats(board, seconds):
    fps, busy, ren, deadline = [], [], [], time.time() + seconds
    while time.time() < deadline:
        l = board.readline()
        m = re.search(r"BUSY:(\d+)%, FPS:(\d+) \(S:(\d+) R:(\d+)\+(\d+)\)", l)
        if m:
            busy.append(int(m.group(1))); fps.append(int(m.group(2)))
            ren.append(int(m.group(4)) + int(m.group(5)))
    if not fps:
        return None
    return sum(fps) / len(fps), sum(busy) / len(busy), sum(ren) / len(ren)


def main():
    b = Board(os.environ.get("ESP_PORT", "/dev/ttyACM0"))
    snap = "--snap" in sys.argv
    print(f"{'app':5} {'rom':52} {'fps':>5} {'busy':>5} {'drawn':>6}")
    for app, part, rom in GAMES:
        b.send(f"launch {part} {app} {rom}", timeout=3, echo=False)
        b.wait_boot()
        time.sleep(8)
        for _ in range(2):
            b.key("start", 200)
            time.sleep(3)
        r = stats(b, 6)
        name = os.path.basename(rom)[:52]
        if r:
            print(f"{app:5} {name:52} {r[0]:5.1f} {r[1]:4.0f}% {r[2]:6.1f}")
        else:
            print(f"{app:5} {name:52}   no stats")
        if snap:
            os.system(f"python3 {os.path.dirname(__file__)}/board_cam.py /tmp/emu_{app}_{abs(hash(rom)) % 1000}.jpg >/dev/null")


if __name__ == "__main__":
    main()
