#!/usr/bin/env python3
"""Prepare Neo Geo games for mame-go on the PC instead of on the board.

The first launch of a Neo Geo game on the board converts its sprite ROMs
(and sample ROMs larger than the flash partition) into files on the SD card:
seconds on a PC, minutes on the ESP32-S3 (Metal Slug 2: 32 MB of sprites).
This builds the same mame2000 code for the PC (retro-go/mame-go/tools/
neoprep.c) and runs it on each zip; copy the output folder to the card:

    scripts/neogeo_prepare.py test-roms/neogeo/*.zip
    cp -r build/neogeo-prepare/mame2000/neospr /media/<card>/retro-go/mame/mame2000/

Put neogeo.zip (the BIOS) next to games whose zip does not include it.
"""
import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = os.path.join(ROOT, "retro-go", "mame-go", "components", "mame2000")
TOOL = os.path.join(ROOT, "retro-go", "mame-go", "tools", "neoprep.c")
FLAGS = ("-O2 -w -fsigned-char -fcommon -DALIGN_INTS -DALIGN_SHORTS -DMAME_UNDERCLOCK -DMAME_FASTSOUND "
         "-DBIGCASE -D__LIBRETRO__ -DLSB_FIRST -DMAMEGO").split()


def component_sources():
    """Sources and -D flags straight from the component's CMakeLists (one list, no drift)."""
    text = open(os.path.join(COMP, "CMakeLists.txt")).read()
    srcs = re.search(r"COMPONENT_SRCS(.*?)\)", text, re.S).group(1).split()
    defines = re.findall(r"(-DHAS_\w+=1)", text)
    return srcs, defines


def build(out):
    objdir = os.path.join(out, "obj")
    os.makedirs(objdir, exist_ok=True)
    srcs, defines = component_sources()
    incs = ["-I" + os.path.join(COMP, d) for d in ("src", "src/libretro", "src/libretro/libretro-common/include")]
    cflags = FLAGS + defines + incs
    # gcc writes each object's real dependencies (#included .c files too:
    # drivers/neogeo.c, m68kmame.c) and they decide what to rebuild
    def compile_one(src):
        obj = os.path.join(objdir, src.replace("/", "_") + ".o")
        dep = obj[:-2] + ".d"
        deps = [os.path.join(COMP, src)]
        if os.path.exists(dep):
            deps = open(dep).read().replace("\\\n", " ").split(":", 1)[1].split()
        if not os.path.exists(obj) or not os.path.exists(dep) \
                or any(not os.path.exists(d) or os.path.getmtime(d) > os.path.getmtime(obj) for d in deps):
            subprocess.run(["gcc", *cflags, "-MMD", "-MF", dep, "-c", os.path.join(COMP, src), "-o", obj], check=True)
        return obj

    with ThreadPoolExecutor(os.cpu_count()) as pool:
        objs = list(pool.map(compile_one, srcs))
    exe = os.path.join(out, "neoprep")
    subprocess.run(["gcc", *cflags, TOOL, *objs, "-lm", "-o", exe], check=True)
    return exe


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zips", nargs="+", help="Neo Geo ROM zips (MAME sets, modern or 0.37b5)")
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "neogeo-prepare"))
    a = ap.parse_args()
    exe = build(a.out)
    sysdir = os.path.join(a.out, "sys")
    os.makedirs(sysdir, exist_ok=True)
    failed = 0
    for z in a.zips:
        if os.path.basename(z).lower() == "neogeo.zip":
            continue
        r = subprocess.run([exe, sysdir, os.path.abspath(z)], capture_output=True, text=True)
        lines = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(("neospr:", "neosnd:", "mamego:", "neoprep:")) or "NOT FOUND" in l]
        print(f"== {os.path.basename(z)}: {'ok' if r.returncode == 0 else 'FAILED'}")
        for l in lines:
            if "paged from the card" in l or "FAIL" in l or "NOT FOUND" in l or "mamego:" in l or "neoprep:" in l:
                print("  " + l)
        failed += r.returncode != 0
    neospr = os.path.join(sysdir, "mame2000", "neospr")
    print(f"\ncopy {neospr} to <card>/retro-go/mame/mame2000/neospr/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
