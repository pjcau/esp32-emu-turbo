#!/usr/bin/env python3
"""Generate MAME 0.37b5 ROM definitions for modern Neo Geo ROM sets.

Current MAME ROM sets (the zips people download today) are organised
differently from the 0.37b5 ones mame-go's driver knows: other file names,
the halves of 4 MB sprite ROMs in order instead of swapped, merged or split
sample ROMs, newer program revisions. Current MAME describes every set in
src/mame/snk/neogeo.cpp; this translates those descriptions into 0.37b5
syntax, so any modern zip loads without a hand-written definition.

    scripts/neogeo_modern_sets.py [neogeo.cpp]    (downloaded if not given)

writes retro-go/mame-go/components/mame2000/src/drivers/neogeo_modern_roms.inc
(ROM_START blocks) and neogeo_modern_games.inc (GAME lines), both #included
by drivers/neogeo.c, then regenerates mamego_driver.c.

Skipped on purpose, with the reason printed: encrypted sets (the 0.37b5
driver has no CMC/PCM2/SMA decryption), programs over 5 MB (no room on
the board: 1 MB fixed + 4 MB banked), 512 KB sound CPU ROMs, and any construct the translation does
not know (32-bit loads, fills, copies, BIOS overrides). Parent sets, then
the clones of a translated parent (the zip people have is often a clone:
another program revision), ~500 bytes of binary each.
"""
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = os.path.join(ROOT, "retro-go", "mame-go", "components", "mame2000")
DRIVER = os.path.join(COMP, "src", "drivers", "neogeo.c")
OUT_ROMS = os.path.join(COMP, "src", "drivers", "neogeo_modern_roms.inc")
OUT_GAMES = os.path.join(COMP, "src", "drivers", "neogeo_modern_games.inc")
MAME_URL = "https://raw.githubusercontent.com/mamedev/mame/master/src/mame/snk/neogeo.cpp"
MAX_PROGRAM = 0x500000          # 1 MB in PSRAM + 4 MB banked part in the flash partition
GFX2_MAX = 0x1000000            # the 0.37b5 driver splits sprites over GFX2 + GFX3 at 16 MB

CRC = r'CRC\(\s*([0-9a-fA-F]{8})\s*\)'


class Skip(Exception):
    pass


def num(s):
    return int(s, 0)


def translate(name, body):
    """0.37b5 ROM_START body for one modern set, or raise Skip(reason)."""
    lines = [l.split("//")[0].split("/*")[0].strip() for l in body.splitlines()]
    lines = [l for l in lines if l]
    out, region, have_adpcmb, sprites = [], None, False, []
    program = 0
    for l in lines:
        if re.search(r'ENCRYPTED|audiocrypt|"cslot1:fixed"|ROM_LOAD32|ROM_FILL|ROM_COPY|ROM_IGNORE|ROM_Y_ZOOM|ROM_SYSTEM_BIOS|ROM_DEFAULT_BIOS|WORD_SWAP_BIOS|"cslot1:pld"|ROM_RELOAD', l):
            raise Skip("uses " + re.match(r'[A-Z0-9_]+', l).group(0) if re.match(r'[A-Z0-9_]+', l) else l[:30])
        m = re.match(r'ROM_REGION\(\s*(0x[0-9a-fA-F]+)\s*,\s*"([^"]+)"', l)
        if m:
            size, tag = num(m.group(1)), m.group(2)
            region = tag
            if tag == "cslot1:maincpu":
                if size > MAX_PROGRAM:
                    raise Skip("program %d KB" % (size // 1024))
                program = size
                out.append("\tROM_REGION( 0x%x, REGION_CPU1 )" % size)
            elif tag == "cslot1:ymsnd:adpcma":
                out.append("\tROM_REGION( 0x%x, REGION_SOUND1 | REGIONFLAG_SOUNDONLY )" % size)
            elif tag == "cslot1:ymsnd:adpcmb":
                have_adpcmb = True
                out.append("\tROM_REGION( 0x%x, REGION_SOUND2 | REGIONFLAG_SOUNDONLY )" % size)
            elif tag == "cslot1:sprites":
                sprites_size = size
                out.append("@SPRITES@")
            elif tag == "mcu":
                pass    # link MCU (Thrash Rally, League Bowling): never dumped, not needed to play
            else:
                raise Skip("region " + tag)
            continue
        m = re.match(r'(NEO_SFIX_(?:64|128)K)\(\s*"([^"]+)"\s*,\s*' + CRC, l)
        if m:
            out.append('\t%s( "%s", 0x%s )' % (m.group(1), m.group(2), m.group(3).lower()))
            continue
        m = re.match(r'NEO_BIOS_AUDIO_(64|128|256)K\(\s*"([^"]+)"\s*,\s*' + CRC, l)
        if m:
            out.append('\tNEO_BIOS_SOUND_%sK( "%s", 0x%s )' % (m.group(1), m.group(2), m.group(3).lower()))
            continue
        if l.startswith("NEO_BIOS_AUDIO_"):
            raise Skip(l.split("(")[0])
        m = re.match(r'ROM_LOAD16_WORD_SWAP\(\s*"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*' + CRC, l)
        if m and region == "cslot1:maincpu":
            out.append('\tROM_LOAD_WIDE_SWAP( "%s", 0x%06x, 0x%06x, 0x%s )' % (m.group(1), num(m.group(2)), num(m.group(3)), m.group(4).lower()))
            continue
        m = re.match(r'ROM_CONTINUE\(\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*\)', l)
        if m and region == "cslot1:maincpu":
            out.append('\tROM_CONTINUE( 0x%06x, 0x%06x | ROMFLAG_WIDE | ROMFLAG_SWAP )' % (num(m.group(1)), num(m.group(2))))
            continue
        m = re.match(r'ROM_LOAD\(\s*"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*' + CRC, l)
        if m and region in ("cslot1:ymsnd:adpcma", "cslot1:ymsnd:adpcmb"):
            out.append('\tROM_LOAD( "%s", 0x%06x, 0x%06x, 0x%s )' % (m.group(1), num(m.group(2)), num(m.group(3)), m.group(4).lower()))
            continue
        m = re.match(r'ROM_LOAD16_BYTE\(\s*"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*' + CRC, l)
        if m and region == "cslot1:sprites":
            sprites.append((m.group(1), num(m.group(2)), num(m.group(3)), m.group(4).lower()))
            continue
        if region == "mcu" and "NO_DUMP" in l:
            continue
        if l.startswith("ROM_START") or l.startswith("ROM_END"):
            continue
        raise Skip("unknown line: " + l[:40])
    if not program or "@SPRITES@" not in out:
        raise Skip("no program or sprites")

    # adpcmb absent: the 0.37b5 macro that marks it
    if not have_adpcmb:
        i = max(i for i, l in enumerate(out) if "REGION_SOUND1" in l or l.startswith('\tROM_LOAD( "'))
        out.insert(i + 1, "\tNO_DELTAT_REGION")

    # sprites: GFX2 up to 16 MB, the rest in GFX3; even/odd byte lanes
    spr = []
    def region_lines(lo, hi, reg):
        size = min(sprites_size, hi) - lo
        if size <= 0:
            return
        spr.append("\tROM_REGION( 0x%x, %s )" % (size, reg))
        for n, off, length, crc in sprites:
            base = off & ~1
            if lo <= base < hi:
                if base + 2 * length > hi:
                    raise Skip("sprite ROM across the 16 MB split")
                spr.append('\t%s( "%s", 0x%07x, 0x%06x, 0x%s )' % (
                    "ROM_LOAD_GFX_ODD " if off & 1 else "ROM_LOAD_GFX_EVEN", n, base - lo, length, crc))
    region_lines(0, GFX2_MAX, "REGION_GFX2")
    region_lines(GFX2_MAX, 1 << 32, "REGION_GFX3")
    i = out.index("@SPRITES@")
    out[i:i + 1] = spr
    return "\n".join(out)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    if src:
        text = open(src).read()
    else:
        text = urllib.request.urlopen(MAME_URL).read().decode("utf-8", "replace")
    old = open(DRIVER).read()
    old_names = set(re.findall(r'^ROM_START\(\s*(\w+)\s*\)', old, re.M))
    # flags of the 0.37b5 sets (ROT0_16BIT on the games with more colours than
    # an 8-bit palette holds): a modern set of the same game takes them over
    old_flags = dict(re.findall(r'^GAME\(\s*\d+\s*,\s*(\w+)\s*,[^,]*,[^,]*,[^,]*,[^,]*,\s*(\w+)\s*,', old, re.M))
    games = {}
    for m in re.finditer(r'^GAME\(\s*(\d+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,[^"]*"([^"]*)"\s*,\s*"([^"]*)"', text, re.M):
        games[m.group(2)] = (m.group(1), m.group(3), m.group(4), m.group(5))

    def is_game(n):
        return n in games and games[n][1] == "neogeo"

    roms, gamelines, skipped = [], [], {}
    bodies = {m.group(1): m.group(2) for m in
              re.finditer(r'^ROM_START\(\s*(\w+)\s*\)(.*?)^ROM_END', text, re.S | re.M)}
    ours_of = lambda n: n + "m" if n in old_names else n
    done = set()
    # parents first, then clones of a parent that was translated (the zip a
    # user has is often a clone: a different program revision of the game)
    for pass_ in ("parent", "clone"):
        for name, body in bodies.items():
            if name not in games:
                continue
            parent = games[name][1]
            if pass_ == "parent" and parent != "neogeo":
                continue
            if pass_ == "clone" and not (is_game(parent) and parent in done):
                continue
            try:
                rom = translate(name, body)
            except Skip as e:
                skipped[name] = str(e)
                continue
            done.add(name)
            year, _, maker, title = games[name]
            ours = ours_of(name)
            if pass_ == "clone":
                parent37 = ours_of(parent)
            else:
                parent37 = name if name in old_names else "neogeo"
            flags = old_flags.get(name, old_flags.get(parent, "ROT0"))
            roms.append("ROM_START( %s )\n%s\nROM_END\n" % (ours, rom))
            gamelines.append('GAME( %s, %s, %s, neogeo, neogeo, neogeo, %s, "%s", "%s (modern set)" )'
                             % (year, ours, parent37, flags,
                                maker.replace('"', "'"), title.replace('"', "'")))

    head = "/* Generated by scripts/neogeo_modern_sets.py from current MAME's neogeo.cpp: do not edit. */\n"
    open(OUT_ROMS, "w").write(head + "\n".join(roms))
    open(OUT_GAMES, "w").write(head + "\n".join(gamelines) + "\n")
    print("%d modern sets translated, %d skipped" % (len(roms), len(skipped)))
    reasons = {}
    for n, r in skipped.items():
        reasons.setdefault(r.split(":")[0], []).append(n)
    for r, ns in sorted(reasons.items(), key=lambda x: -len(x[1])):
        print("  skipped (%s): %d, e.g. %s" % (r, len(ns), " ".join(sorted(ns)[:6])))

    # the drivers[] list: gen_drivers.py reads GAME lines from the given files
    first = open(os.path.join(COMP, "mamego_driver.c")).readline()
    files = first.split("from:", 1)[1].replace("*/", "").split()
    if "src/drivers/neogeo_modern_games.inc" not in files:
        files.append("src/drivers/neogeo_modern_games.inc")
    subprocess.run([sys.executable, "gen_drivers.py", "mamego_driver.c", *files], cwd=COMP, check=True)


if __name__ == "__main__":
    main()
