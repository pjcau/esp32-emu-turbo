#!/usr/bin/env python3
"""Firmware update through the SD card (roadmap Phase 6).

Puts the app images the build wrote (retro-go/<app>/build/<app>.bin) into
retro-go/update/ on the card; at the next boot the launcher writes them into
their partitions (retro-go/components/retro-go/rg_update.c) and renames each
file to .done (.failed if it did not verify). launcher.bin is written by
another app, which hands back to the launcher.

    scripts/sd_update.py --card /media/<user>/<card> mame-go retro-core
    scripts/sd_update.py --console mame-go          # upload over USB, then reboot
    scripts/sd_update.py --card /media/x            # every app that was built

Only apps: a changed partition table (sizes in rg_tool.py) still needs a
full USB flash, and this refuses an image larger than its partition.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RG = os.path.join(ROOT, "retro-go")


def partitions():
    """{app: partition size} from rg_tool.py's PROJECT_APPS"""
    text = open(os.path.join(RG, "rg_tool.py")).read()
    block = text[text.index("PROJECT_APPS = {"):]
    block = block[:block.index("}")]
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"'([\w-]+)':\s*\[\s*\d+\s*,\s*\d+\s*,\s*(\d+)\s*\]", block)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    dest = ap.add_mutually_exclusive_group(required=True)
    dest.add_argument("--card", help="mount point of the SD card")
    dest.add_argument("--console", action="store_true", help="upload through the USB console (board_ctl put)")
    ap.add_argument("apps", nargs="*", help="apps to update (default: every built one)")
    a = ap.parse_args()

    sizes = partitions()
    apps = a.apps or [x for x in sizes if os.path.exists(os.path.join(RG, x, "build", x + ".bin"))]
    todo = []
    for app in apps:
        if app not in sizes:
            sys.exit(f"{app}: not an app of rg_tool.py")
        src = os.path.join(RG, app, "build", app + ".bin")
        if not os.path.exists(src):
            sys.exit(f"{app}: {src} not built")
        n = os.path.getsize(src)
        if n > sizes[app]:
            sys.exit(f"{app}: {n} bytes do not fit its {sizes[app]}-byte partition")
        todo.append((app, src, n))

    if a.console and todo:   # uploads go through the launcher's console
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "board_ctl.py"), "launcher"], check=True)
        import time
        time.sleep(12)
    for app, src, n in todo:
        if a.card:
            d = os.path.join(a.card, "retro-go", "update")
            os.makedirs(d, exist_ok=True)
            shutil.copyfile(src, os.path.join(d, app + ".bin"))
            print(f"{app}: {n // 1024} KB -> {d}")
        else:
            print(f"{app}: uploading {n // 1024} KB (about {max(1, n // 190000)} s)")
            subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "board_ctl.py"), "put", src,
                            f"/sd/retro-go/update/{app}.bin"], check=True)
    if a.console and todo:
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "board_ctl.py"), "launcher"], check=True)
        print("rebooted to the launcher: it applies the update now")
    elif todo:
        print("put the card back and switch the console on: the launcher applies the update")


if __name__ == "__main__":
    main()
