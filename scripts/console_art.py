#!/usr/bin/env python3
"""console_art.py: launcher covers for the console games (the arcade ones: arcade_art.py).

    scripts/console_art.py fetch <outdir> <tab> <rom file> [<rom file>...]
        Writes <outdir>/romart/<tab>/<rom file name>.png for each ROM: the game's
        box art (the title screen, then an in-game shot, when there is no box),
        scaled to fit the launcher's preview box (240x224 on the 480x320 panel).
        Copy the folder to the card as /sd/romart/<tab>/: the launcher looks for
        /sd/romart/<tab>/<rom file name>.png (launcher/main/gui.c).

    scripts/console_art.py tabs
        The launcher tabs this script knows and the thumbnail sets behind them.

    scripts/console_art.py shot <outdir> <tab> <rom file> <screenshot.png>
        For a game the server has nothing for (homebrew, native ports): its own
        screenshot, scaled the same way, as the cover.

    scripts/console_art.py card <outdir> <tab> <rom file> ["Title to print"]
        Last resort: a plain card with the game's name, so that no entry of the
        launcher is left without a picture.

The images come from the libretro thumbnails server (thumbnails.libretro.com),
whose files are named after the No-Intro game names. A ROM file is matched by
its name: first exactly (region tags and punctuation aside), then by the
closest name; every line of the output says which image was used, so a wrong
match can be seen and fixed by hand ("<rom file>=<thumbnail name>"). The images
are not kept in this repository: run the script where the card is.
"""
import difflib
import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://thumbnails.libretro.com/%s/%s/"
KINDS = ("Named_Boxarts", "Named_Titles", "Named_Snaps")
BOX = (240, 224)          # PREVIEW_WIDTH x PREVIEW_HEIGHT of launcher/main/gui.c on a 480x320 panel
# launcher tab (launcher/main/applications.c) -> thumbnail sets, in order of preference
SYSTEMS = {
    "nes": ["Nintendo - Nintendo Entertainment System", "Nintendo - Family Computer Disk System"],
    "snes": ["Nintendo - Super Nintendo Entertainment System"],
    "gb": ["Nintendo - Game Boy", "Nintendo - Game Boy Color"],
    "gbc": ["Nintendo - Game Boy Color", "Nintendo - Game Boy"],
    "gba": ["Nintendo - Game Boy Advance"],
    "sg1": ["Sega - SG-1000"],
    "sms": ["Sega - Master System - Mark III"],
    "gg": ["Sega - Game Gear"],
    "md": ["Sega - Mega Drive - Genesis"],
    "col": ["Coleco - ColecoVision"],
    "pce": ["NEC - PC Engine - TurboGrafx 16"],
    "ngp": ["SNK - Neo Geo Pocket Color", "SNK - Neo Geo Pocket"],
    "doom": ["DOOM"],
    "quake": ["Quake"],
    "wolf3d": ["Wolfenstein 3D"],
}
_index = {}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "esp32-emu-turbo console_art.py"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def index(system, kind):
    """The names (without .png) the server has for this set and kind."""
    key = (system, kind)
    if key not in _index:
        try:
            html = get(BASE % (urllib.parse.quote(system), kind)).decode("utf-8", "replace")
            names = [urllib.parse.unquote(m)[:-4] for m in re.findall(r'href="([^"/]+\.png)"', html)]
        except Exception as e:
            print("  (no listing for %s / %s: %s)" % (system, kind, e))
            names = []
        _index[key] = names
    return _index[key]


def norm(name):
    """A game name with its tags, articles' position and punctuation out of the way."""
    name = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)
    name = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", name)          # (USA), [!], (Rev 1)
    name = re.sub(r"^(.*), (The|A|An)\b", r"\2 \1", name)       # "Legend of Zelda, The"
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def region_rank(candidate, rom):
    tags = " ".join(re.findall(r"\(([^)]*)\)", rom))
    for i, r in enumerate(("USA", "World", "Europe", "Japan")):
        if r in tags and r in candidate:
            return -10 + i                                      # the ROM's own region first
    for i, r in enumerate(("USA", "World", "Europe", "Japan")):
        if r in candidate:
            return i
    return 9


def match(rom, names):
    """(thumbnail name, how) or (None, None)."""
    if not names:
        return None, None
    want = norm(rom)
    table = {}
    for n in names:
        table.setdefault(norm(n), []).append(n)
    if want in table:
        return sorted(table[want], key=lambda c: (region_rank(c, rom), len(c)))[0], "exact"
    close = difflib.get_close_matches(want, list(table), n=1, cutoff=0.85)
    if close:
        return sorted(table[close[0]], key=lambda c: (region_rank(c, rom), len(c)))[0], "closest"
    return None, None


def fetch(outdir, tab, roms):
    from PIL import Image
    if tab not in SYSTEMS:
        raise SystemExit("unknown tab %s (see: console_art.py tabs)" % tab)
    dest = os.path.join(outdir, "romart", tab)
    os.makedirs(dest, exist_ok=True)
    missing, guessed = [], []
    for rom in roms:
        rom, _, forced = rom.partition("=")
        rom = os.path.basename(rom)
        stem = os.path.splitext(rom)[0]
        found = None
        for kind in KINDS:
            for system in SYSTEMS[tab]:
                names = index(system, kind)
                if forced:
                    name, how = (forced, "given") if forced in names else (None, None)
                else:
                    name, how = match(rom, names)
                if name:
                    found = (system, kind, name, how)
                    break
            if found:
                break
        if not found:
            missing.append(rom)
            print("%-44s NO ART" % rom[:44])
            continue
        system, kind, name, how = found
        try:
            data = get(BASE % (urllib.parse.quote(system), kind) + urllib.parse.quote(name + ".png"))
            im = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception as e:
            missing.append(rom)
            print("%-44s DOWNLOAD FAILED (%s): %s" % (rom[:44], name, e))
            continue
        im.thumbnail(BOX, Image.LANCZOS)
        path = os.path.join(dest, stem + ".png")
        im.save(path, optimize=True)
        if how == "closest":
            guessed.append(rom)
        print("%-44s %-7s %s: %s  %dx%d" % (rom[:44], how, kind[6:], name, im.width, im.height))
        time.sleep(0.2)
    print("done: %d written (%d by closest name: check them), %d without art%s" % (
        len(roms) - len(missing), len(guessed), len(missing), (": " + "; ".join(missing)) if missing else ""))
    return 1 if missing else 0


def shot(outdir, tab, rom, picture):
    from PIL import Image
    dest = os.path.join(outdir, "romart", tab)
    os.makedirs(dest, exist_ok=True)
    im = Image.open(picture).convert("RGB")
    im.thumbnail(BOX, Image.LANCZOS)
    path = os.path.join(dest, os.path.splitext(os.path.basename(rom))[0] + ".png")
    im.save(path, optimize=True)
    print("%s: %dx%d from %s" % (path, im.width, im.height, picture))
    return 0


def card(outdir, tab, rom, title=None):
    from PIL import Image, ImageDraw, ImageFont
    dest = os.path.join(outdir, "romart", tab)
    os.makedirs(dest, exist_ok=True)
    stem = os.path.splitext(os.path.basename(rom))[0]
    title = title or re.sub(r"[_\-]+", " ", re.sub(r"[\(\[][^\)\]]*[\)\]]", "", stem)).strip()
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:                       # Pillow before 10.1: the small bitmap font
        font = ImageFont.load_default()
    w, h = 240, 150
    im = Image.new("RGB", (w, h), (28, 40, 72))
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, w - 5, h - 5], outline=(245, 200, 40), width=2)
    words, lines, line = title.split(), [], ""
    for word in words:                      # wrap to the card's width
        t = (line + " " + word).strip()
        if d.textlength(t, font=font) <= w - 24 or not line:
            line = t
        else:
            lines.append(line)
            line = word
    lines.append(line)
    lines = lines[:5]
    step = 26 if d.textlength("M", font=font) > 8 else 12
    y = (h - step * len(lines)) // 2
    for l in lines:
        d.text(((w - d.textlength(l, font=font)) // 2, y), l, font=font, fill=(255, 255, 255))
        y += step
    path = os.path.join(dest, stem + ".png")
    im.save(path, optimize=True)
    print("%s: card \"%s\"" % (path, title))
    return 0


def main():
    a = sys.argv[1:]
    if a == ["tabs"]:
        for tab, systems in SYSTEMS.items():
            print("%-8s %s" % (tab, " | ".join(systems)))
        return 0
    if len(a) >= 4 and a[0] == "fetch":
        return fetch(a[1], a[2], a[3:])
    if len(a) == 5 and a[0] == "shot":
        return shot(a[1], a[2], a[3], a[4])
    if len(a) in (4, 5) and a[0] == "card":
        return card(a[1], a[2], a[3], a[4] if len(a) == 5 else None)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
