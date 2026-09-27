#!/usr/bin/env python3
"""Generate MAME 0.37b5 definitions for modern CPS1 ROM sets.

The zips people download today follow current MAME's src/mame/capcom/cps1.cpp.
Their graphics, sound and audio-CPU chips are almost always the same dumps
0.37b5 already knows (the loader matches files by CRC, so other file names do
not matter), but many carry a program revision 0.37b5 does not have (Street
Fighter II' Champion Edition "World 920513": s92e_23b). Translating the modern
graphics layout (ROM_LOAD64_WORD) to 0.37b5's is not needed then: for every
modern set whose non-program ROMs are exactly those of a 0.37b5 set of the
same game, this writes a set with that 0.37b5 definition and the modern
program ROMs.

    scripts/cps1_modern_sets.py [cps1.cpp]    (downloaded if not given)

writes retro-go/mame-go/components/mame2000/src/drivers/cps1_modern_roms.inc
(ROM_START blocks) and cps1_modern_games.inc (GAME lines), both #included by
drivers/cps1.c, then regenerates mamego_driver.c. A modern set is named like
the modern one, with "m" appended when 0.37b5 has a set of that name.
"""
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = os.path.join(ROOT, "retro-go", "mame-go", "components", "mame2000")
DRIVER = os.path.join(COMP, "src", "drivers", "cps1.c")
OUT_ROMS = os.path.join(COMP, "src", "drivers", "cps1_modern_roms.inc")
OUT_GAMES = os.path.join(COMP, "src", "drivers", "cps1_modern_games.inc")
MAME_URL = "https://raw.githubusercontent.com/mamedev/mame/master/src/mame/capcom/cps1.cpp"


def blocks(text):
    return {m.group(1): m.group(2) for m in
            re.finditer(r'^ROM_START\(\s*(\w+)\s*\)(.*?)^ROM_END', text, re.S | re.M)}


def modern_regions(body):
    """{region tag: [(macro, name, offset, length, crc)]} of a modern set"""
    out, region = {}, None
    for l in body.splitlines():
        l = l.split("//")[0].strip()
        m = re.match(r'ROM_REGION\(\s*\w+\s*,\s*"([^"]+)"', l)
        if m:
            region = m.group(1)
            out[region] = []
            continue
        m = re.match(r'(ROM_LOAD\w*)\(\s*"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*CRC\(\s*([0-9a-fA-F]{8})\s*\)', l)
        if m and region:
            out[region].append((m.group(1), m.group(2), int(m.group(3), 16), int(m.group(4), 16), m.group(5).lower()))
        elif region and l.startswith(("ROM_CONTINUE", "ROM_FILL", "ROM_COPY", "ROM_RELOAD", "ROM_IGNORE")):
            out[region].append((l.split("(")[0], None, 0, 0, None))
    return out


def old_split(body):
    """(program lines, other lines, program CRCs, other CRCs) of a 0.37b5 set"""
    prog, other, pcrc, ocrc, cur = [], [], set(), set(), None
    for l in body.strip("\n").splitlines():
        s = l.strip()
        m = re.match(r'ROM_REGION\(\s*(\w+)\s*,\s*(\w+)', s)
        if m:
            cur = "prog" if m.group(2) == "REGION_CPU1" else "other"
        crc = re.search(r',\s*(?:BADCRC\s*\(\s*)?0x([0-9a-fA-F]{8})\s*\)?\s*\)\s*(/\*.*)?$', s)
        (prog if cur == "prog" else other).append(l)
        if crc and s.startswith("ROM_LOAD"):
            (pcrc if cur == "prog" else ocrc).add(crc.group(1).lower())
    return prog, other, pcrc, ocrc


def translate_program(entries, region_line):
    """0.37b5 program region lines from a modern maincpu region, or None"""
    out = [region_line]
    for macro, name, off, length, crc in entries:
        if macro == "ROM_LOAD16_WORD_SWAP":
            out.append('\tROM_LOAD_WIDE_SWAP( "%s", 0x%06x, 0x%05x, 0x%s )' % (name, off, length, crc))
        elif macro == "ROM_LOAD16_BYTE":
            out.append('\tROM_LOAD_%s( "%s", 0x%05x, 0x%05x, 0x%s )' % ("ODD " if off & 1 else "EVEN", name, off & ~1, length, crc))
        else:
            return None     # anything else (continue, fill, 8-bit loads): leave to the hand-made sets
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    text = open(src).read() if src else urllib.request.urlopen(MAME_URL).read().decode("utf-8", "replace")
    old_text = open(DRIVER).read()
    old = blocks(old_text)
    old_games = {}
    for m in re.finditer(r'^GAME\(\s*(\d+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,', old_text, re.M):
        old_games[m.group(2)] = dict(parent=m.group(3), machine=m.group(4), input=m.group(5), init=m.group(6), flags=m.group(7))
    old_parts = {n: old_split(b) for n, b in old.items()}

    modern_games = {}
    for m in re.finditer(r'^GAME\(\s*(\d+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,[^"]*"([^"]*)"\s*,\s*"([^"]*)"', text, re.M):
        modern_games[m.group(2)] = (m.group(1), m.group(3), m.group(4), m.group(5))

    roms, games, done = [], [], 0
    for name, body in blocks(text).items():
        if name not in modern_games:
            continue
        regs = modern_regions(body)
        if "maincpu" not in regs:
            continue
        pcrc = {e[4] for e in regs["maincpu"] if e[4]}
        ocrc = {e[4] for r, es in regs.items() if r != "maincpu" and not r.endswith("plds") and r != "decryption"
                for e in es if e[4]}
        year, parent, maker, title = modern_games[name]
        if re.search(r'bootleg|hack', maker, re.I):
            continue            # binary space: official releases only
        family = {name, parent} if parent != "0" else {name}
        # a 0.37b5 set of the same game with exactly these other chips
        match = None
        for oname, (oprog, oother, opc, ooc) in old_parts.items():
            g = old_games.get(oname)
            if not g or not ({oname, g["parent"]} & family or oname in family):
                continue
            if ooc == ocrc:
                if opc == pcrc:
                    match = "same"      # 0.37b5 has this very set
                    break
                match = match or oname
        if not match or match == "same":
            continue
        oprog, oother, _, _ = old_parts[match]
        region_line = oprog[0] if oprog and "ROM_REGION" in oprog[0] else None
        if not region_line:
            continue
        prog = translate_program(regs["maincpu"], region_line)
        if not prog:
            continue
        ours = name + "m" if name in old else name
        g = old_games[match]
        roms.append("ROM_START( %s )\n%s\n%s\nROM_END\n" % (ours, "\n".join(prog), "\n".join(oother)))
        games.append('GAME( %s, %s, %s, %s, %s, %s, %s, "%s", "%s (modern set)" )'
                     % (year, ours, match, g["machine"], g["input"], g["init"], g["flags"],
                        maker.replace('"', "'"), title.replace('"', "'")))
        done += 1

    head = "/* Generated by scripts/cps1_modern_sets.py from current MAME's cps1.cpp: do not edit. */\n"
    open(OUT_ROMS, "w").write(head + "\n".join(roms))
    open(OUT_GAMES, "w").write(head + "\n".join(games) + "\n")
    print("%d modern CPS1 sets (new program revision on 0.37b5 chips)" % done)

    first = open(os.path.join(COMP, "mamego_driver.c")).readline()
    files = first.split("from:", 1)[1].replace("*/", "").split()
    if "src/drivers/cps1_modern_games.inc" not in files:
        files.append("src/drivers/cps1_modern_games.inc")
    subprocess.run([sys.executable, "gen_drivers.py", "mamego_driver.c", *files], cwd=COMP, check=True)


if __name__ == "__main__":
    main()
