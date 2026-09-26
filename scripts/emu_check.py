#!/usr/bin/env python3
"""Quick 60 fps check across the non-SNES emulators on the card.

For each ROM: launch, press START twice (title screens), then average the
rg_system stats line ("BUSY:xx%, FPS:yy (S:skipped R:rendered+partial)")
for a few seconds. Prints a table; optional webcam snapshot per game.

    emu_check.py [--snap] [--only=<app>]   e.g. --only=arcade
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from board_ctl import Board  # noqa: E402

# (app, partition, preferred ROM or None). With None the first file of the
# system's folder on the card is used, so a new system is covered as soon as
# its /sd/roms/<app> folder has a ROM. Every app must carry the console:
# rebuild gwenesis/fmsx/prboom-go after a shared-component change.
GAMES = [
    ("nes", "retro-core", "/sd/roms/nes/Super Mario Bros. + Duck Hunt (USA).nes"),
    ("nes", "retro-core", "/sd/roms/nes/owlia.nes"),
    ("gb", "retro-core", "/sd/roms/gb/Tetris (JUE) (V1.1) [!].gb"),
    ("gbc", "retro-core", "/sd/roms/gbc/Space Invaders (USA, Europe) (GB Compatible).gbc"),
    ("gbc", "retro-core", "/sd/roms/gbc/ucity.gbc"),
    ("sms", "retro-core", "/sd/roms/sms/silvervalley.sms"),
    ("gg", "retro-core", "/sd/roms/gg/Swabby-GG-1.11.gg"),
    ("pce", "retro-core", "/sd/roms/pce/reflectron.pce"),
    ("md", "gwenesis", "/sd/roms/md/miniplanets.bin"),
    ("lnx", "retro-core", None),
    ("gw", "retro-core", None),
    ("col", "retro-core", None),
    ("msx", "fmsx", None),
    ("doom", "prboom-go", None),
    ("sg1", "retro-core", None),
    ("ngp", "retro-extra", None),
    ("a26", "retro-extra", None),
    ("duke3d", "duke3d-go", "/sd/roms/duke3d/DUKE3D.GRP"),  # the folder also holds .CON/.RTS/.DMO
    ("arcade", "mame-go", "/sd/roms/arcade/pacman.zip"),
    ("arcade", "mame-go", "/sd/roms/arcade/robby.zip"),
    ("arcade", "mame-go", "/sd/roms/arcade/1942a.zip"),
    ("arcade", "mame-go", "/sd/roms/arcade/1943.zip"),
    ("arcade", "mame-go", "/sd/roms/arcade/targ.zip"),
    ("arcade", "mame-go", "/sd/roms/arcade/circus.zip"),
]
# Keys pressed after boot to leave the title screens (default: START twice).
# Arcade games need a coin (SELECT) before START.
START_KEYS = {"arcade": ["select", "start"]}
FOLDERS = {}  # app name -> card folder when they differ (launcher scans /sd/roms/<app>)


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
    # bench rule: keep the speaker quiet while the checks run
    b.send("volume 5", wait=r"^CTL volume", timeout=3, echo=False)
    print(f"{'app':5} {'rom':52} {'fps':>5} {'busy':>5} {'drawn':>6}")
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    for app, part, rom in GAMES:
        if only and app not in only:
            continue
        if rom is None:
            folder = f"/sd/roms/{FOLDERS.get(app, app)}"
            # "CTL ls f <size> <name>" (the name may contain spaces)
            files = [l.split(None, 4)[4] for l in b.send(f"ls {folder}", wait=r"^CTL ls (done|failed)", timeout=10, echo=False)
                     if l.startswith("CTL ls f")]
            if not files:
                print(f"{app:5} {'(no ROM in ' + folder + ')':52}")
                continue
            rom = f"{folder}/{files[0]}"
        b.send(f"launch {part} {app} {rom}", timeout=3, echo=False)
        b.wait_boot()
        time.sleep(8)
        for key in START_KEYS.get(app, ["start", "start"]):
            b.key(key, 200)
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
