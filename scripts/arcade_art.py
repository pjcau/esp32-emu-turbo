#!/usr/bin/env python3
"""arcade_art.py: launcher covers for the Neo Geo and CPS1 games, and the list of CPS1 sets.

    scripts/arcade_art.py sets cps1|neogeo
        The set names mame-go knows for that board, one per line, read from the
        driver sources (retro-go/mame-go/components/mame2000/src/drivers). Use
        `sets cps1` to decide which zips of /sd/roms/arcade move to /sd/roms/cps1.

    scripts/arcade_art.py fetch <outdir> <tab> <set> [<set>...]
        Writes <outdir>/romart/<tab>/<set>.png for each set: the game's title
        screen (in-game shot, then flyer, when there is no title), scaled to fit
        the launcher's preview box (240x224 on the 480x320 panel). A clone
        without art of its own gets its parent's. Copy the folder to the card
        as /sd/romart/<tab>/: the launcher looks for /sd/romart/<tab>/<rom
        file name>.png (launcher/main/gui.c, cover "based on filename").

The images come from ArcadeDB (adb.arcadeitalia.net), addressed by MAME set
name. They are not kept in this repository: run the script where the card is.
"""
import io
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVERS = os.path.join(ROOT, "retro-go", "mame-go", "components", "mame2000", "src", "drivers")
SOURCES = {
    "cps1": ("cps1.c", "cps1_modern_games.inc"),
    "neogeo": ("neogeo.c", "neogeo_modern_games.inc"),
}
BASE = "https://adb.arcadeitalia.net/media/mame.current/%s/%s.png"
KINDS = ("titles", "ingames", "flyers")
BOX = (240, 224)          # PREVIEW_WIDTH x PREVIEW_HEIGHT of launcher/main/gui.c on a 480x320 panel
GAME = re.compile(r"^\s*GAMEX?\s*\(\s*[^,]+,\s*(\w+)\s*,\s*(\w+)\s*,")


def sets(board):
    """{set: parent or None} from the GAME() lines of the board's driver sources."""
    out = {}
    for name in SOURCES[board]:
        path = os.path.join(DRIVERS, name)
        for line in open(path, encoding="latin-1"):
            m = GAME.match(line)
            if m:
                out[m.group(1)] = None if m.group(2) == "0" else m.group(2)
    if not out:
        raise SystemExit("no GAME() lines found for %s under %s" % (board, DRIVERS))
    return out


def download(setname):
    for kind in KINDS:
        req = urllib.request.Request(BASE % (kind, setname), headers={"User-Agent": "esp32-emu-turbo arcade_art.py"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
        except Exception:
            continue
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return kind, data
    return None, None


def fetch(outdir, tab, names):
    from PIL import Image
    parents = {}
    for board in SOURCES:
        parents.update(sets(board))
    dest = os.path.join(outdir, "romart", tab)
    os.makedirs(dest, exist_ok=True)
    missing = []
    for name in names:
        name = os.path.splitext(os.path.basename(name))[0]
        used, (kind, data) = name, download(name)
        if not data and parents.get(name):
            used = parents[name]
            kind, data = download(used)
        if not data:
            missing.append(name)
            print("%-12s NO ART" % name)
            continue
        im = Image.open(io.BytesIO(data)).convert("RGB")
        im.thumbnail(BOX, Image.LANCZOS)
        path = os.path.join(dest, name + ".png")
        im.save(path, optimize=True)
        print("%-12s %s%s %dx%d %d bytes" % (name, kind, "" if used == name else " of parent " + used,
                                             im.width, im.height, os.path.getsize(path)))
        time.sleep(0.3)
    print("done: %d written, %d without art%s" % (len(names) - len(missing), len(missing),
                                                 (": " + " ".join(missing)) if missing else ""))
    return 1 if missing else 0


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "sets" and a[1] in SOURCES:
        print("\n".join(sorted(sets(a[1]))))
        return 0
    if len(a) >= 4 and a[0] == "fetch":
        return fetch(a[1], a[2], a[3:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
