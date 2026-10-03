#!/usr/bin/env python3
"""saveload_check.py: save / resume / in-session load of every game, on the board.

    scripts/saveload_check.py [--tabs nes,snes,...] [--roms "a.nes,b.nes"] [--out report.md]

For each ROM of each tab whose emulator has save states (the native ports keep
their own saves and are listed as "not tested"):

  1. list /sd/retro-go/saves/<tab>/ and pick a slot whose files do not exist for
     that game (2, 3, then 1); none free -> SKIPPED. The game's "-255.sav" (last
     used slot) is moved aside first and put back at the end, so the user's
     resume slot is unchanged;
  2. launch, wait until the emulator answers ping, let it run (boot time of the
     system + 20 s), "save <slot>", "shot" -> picture A;
  3. 5 s more, "load <slot>", "shot" -> picture C (the menu's load path);
  4. back to the launcher, "resume<slot>" the ROM, read the log while it boots:
     Load failed / short file / larger than the state / refused / a panic or a
     reboot is a FAIL; "shot" -> picture B;
  5. mean absolute difference per pixel A-B and A-C (0-255): a title screen
     instead of the saved scene shows up as a large number;
  6. remove exactly the files the test created (difference of the listings).

Board rules: every key/command goes to a pinged app; no keys in the launcher.
"""
import argparse
import datetime
import io
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_ctl import APPS, Board, fetch  # noqa: E402

NATIVE = {"doom", "quake", "duke3d", "wolf3d", "opentyrian"}
BOOT_S = {"neogeo": 25, "cps1": 25, "arcade": 20, "gba": 8}   # seconds after the app answers
PLAY_S = 20
FAIL_RE = re.compile(r"Load failed|short file|larger than the state|refused|Guru|panic|abort\(\)|rst:0x")
DIFF_FAIL = 40.0      # mean |A-B| per pixel above this: not the saved scene


def ls(b, path):
    out = {}
    for l in b.send(f"ls {path}", wait=r"^CTL ls (done|failed)", timeout=8, echo=False):
        m = re.match(r"CTL ls ([fd])\s+(\d+) (.+)$", l)
        if m and m.group(1) == "f":
            out[m.group(3)] = int(m.group(2))
    return out


def app_now(b):
    for l in b.send("ping", wait=r"^CTL pong", timeout=2, echo=False):
        m = re.search(r"app=(\S+)", l)
        if m:
            return m.group(1)
    return None


def wait_app(b, name, timeout):
    t = time.time()
    while time.time() - t < timeout:
        if app_now(b) == name:
            return True
        time.sleep(1.5)
    return False


def to_launcher(b):
    if app_now(b) == "launcher":
        return True
    b.send("launcher", wait=r"^CTL", timeout=5, echo=False)
    return wait_app(b, "launcher", 40)


def drain(b, seconds, keep=None):
    t = time.time()
    while time.time() - t < seconds:
        l = b.readline()
        if l and keep is not None:
            keep.append(l)


def shot(b):
    """Screenshot of the running emulator as a PIL image (PNG or raw RGB565), or None."""
    from PIL import Image
    remote = "/sd/slcheck.png"
    r = b.send("shot " + remote, wait=r"^CTL shot", timeout=20, echo=False)
    if not any("done" in l for l in r):
        return None
    data = fetch(b, remote)
    b.send("rm " + remote, wait=r"^CTL rm", timeout=5, echo=False)
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return Image.open(io.BytesIO(data)).convert("RGB")
    if len(data) > 4:
        w, h = struct.unpack("<HH", data[:4])
        px = struct.unpack("<%dH" % (w * h), data[4:4 + w * h * 2])
        img = Image.new("RGB", (w, h))
        img.putdata([((v >> 11) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3) for v in px])
        return img
    return None


def diff(a, b):
    if a is None or b is None or a.size != b.size:
        return None
    import numpy as np
    return float(np.abs(np.asarray(a, dtype=np.int16) - np.asarray(b, dtype=np.int16)).mean())


def check_rom(b, tab, rom, shots_dir):
    res = {"tab": tab, "rom": rom, "save": "", "bytes": "", "resume": "", "load": "", "dAB": "", "dAC": "", "verdict": "", "why": ""}
    sdir = f"/sd/retro-go/saves/{tab}"
    rompath = f"/sd/roms/{tab}/{rom}"
    if not to_launcher(b):
        res.update(verdict="FAIL", why="launcher did not answer")
        return res
    before = ls(b, sdir)
    slot = next((s for s in (2, 3, 1) if f"{rom}-{s}.sav" not in before), None)
    if slot is None:
        res.update(verdict="SKIPPED", why="no free slot")
        return res
    marker = f"{sdir}/{rom}-255.sav"
    parked = "/sd/slcheck_marker.tmp"          # the user's last-slot marker, parked during the test
    had_marker = f"{rom}-255.sav" in before
    if had_marker:
        b.send(f"mv {marker}|{parked}", wait=r"^CTL mv", timeout=5, echo=False)
    part = APPS.get(tab, "retro-core")
    try:
        b.launch(tab, rompath)
        if not wait_app(b, part, 60):
            res.update(verdict="FAIL", why=f"{part} did not start")
            return res
        b.expect_app = part
        drain(b, BOOT_S.get(tab, 5) + PLAY_S)
        r = b.send(f"save {slot}", wait=r"^CTL save (done|failed)", timeout=30, echo=False)
        ok = any("save done" in l for l in r)
        res["save"] = "ok" if ok else "FAILED"
        now = ls(b, sdir)
        res["bytes"] = now.get(f"{rom}-{slot}.sav", "")
        if not ok:
            res.update(verdict="FAIL", why="; ".join(r)[-160:])
            return res
        a = shot(b)
        if a:
            a.save(os.path.join(shots_dir, f"{tab}_{rom}_A.png"))
        drain(b, 5)
        r = b.send(f"load {slot}", wait=r"^CTL load (done|failed)", timeout=30, echo=False)
        res["load"] = "ok" if any("load done" in l for l in r) else "FAILED"
        drain(b, 1.0)                        # let the emulator draw a frame of the loaded state
        c = shot(b)
        dac = diff(a, c)
        res["dAC"] = "" if dac is None else f"{dac:.1f}"
        # resume from the launcher
        if not to_launcher(b):
            res.update(verdict="FAIL", why="launcher did not answer after the save")
            return res
        log = []
        b.launch(tab, rompath, resume=True, slot=slot)
        t, loaded = time.time(), False
        while time.time() - t < 90 and not loaded:   # the state loads during the boot: wait for its log line
            l = b.readline()
            if l:
                log.append(l)
                loaded = "rg_emu_load_state" in l or FAIL_RE.search(l) is not None
        if not loaded:
            log.append("no 'rg_emu_load_state' line within 90 s")
        # the load line comes before the first frame is drawn: 1.5 s gave an undrawn
        # framebuffer (GBC stripes) or no picture at all (SNES); 4 s is drawn and still close
        drain(b, 4.0, log)
        # the app switch itself reboots (rst:0xc) before the load: a reset counts only after the load line
        at = next((i for i, l in enumerate(log) if "rg_emu_load_state" in l), len(log))
        bad = [l for i, l in enumerate(log)
               if l.startswith("no 'rg_emu_load_state'")
               or (FAIL_RE.search(l) and (i >= at or "rst:0x" not in l))]
        res["resume"] = "FAILED" if bad else "ok"
        bimg = shot(b)
        if bimg:
            bimg.save(os.path.join(shots_dir, f"{tab}_{rom}_B.png"))
        dab = diff(a, bimg)
        res["dAB"] = "" if dab is None else f"{dab:.1f}"
        why = []
        if bad:
            why.append(bad[0].strip()[:150])
        if res["load"] != "ok":
            why.append("in-session load failed")
        if dab is not None and dab > DIFF_FAIL:
            why.append(f"resume picture differs ({dab:.1f})")
        if dac is not None and dac > DIFF_FAIL:
            why.append(f"load picture differs ({dac:.1f})")
        if a is None:
            why.append("no screenshot support (compare by webcam)")
        res["verdict"] = "FAIL" if (bad or res["load"] != "ok" or (dab or 0) > DIFF_FAIL or (dac or 0) > DIFF_FAIL) else "PASS"
        res["why"] = "; ".join(why)
        return res
    finally:
        # back to the launcher, remove what the test created, restore the marker
        to_launcher(b)
        after = ls(b, sdir)
        for name in sorted(set(after) - set(before)):
            b.send(f"rm {sdir}/{name}", wait=r"^CTL rm", timeout=5, echo=False)
        if had_marker:
            b.send(f"rm {marker}", wait=r"^CTL rm", timeout=5, echo=False)       # the test's own marker
            b.send(f"mv {parked}|{marker}", wait=r"^CTL mv", timeout=5, echo=False)
        left = set(ls(b, sdir)) - set(before)
        if left:
            res["why"] = (res["why"] + "; " if res["why"] else "") + "left over: " + ", ".join(sorted(left))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tabs", default="")
    ap.add_argument("--roms", default="")
    ap.add_argument("--out", default=None)
    ap.add_argument("--port", default="/dev/ttyACM0")
    a = ap.parse_args()
    b = Board(a.port)
    if not to_launcher(b):
        sys.exit("the board does not answer from the launcher")
    tabs = [t for t in (a.tabs.split(",") if a.tabs else sorted(ls_dirs(b, "/sd/roms"))) if t]
    day = datetime.date.today().isoformat()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "mamebench", "results", f"{day}-saveload.md")
    shots_dir = os.path.join(os.path.dirname(out), f"{day}-saveload-shots")
    os.makedirs(shots_dir, exist_ok=True)
    rows, notes = [], []
    for tab in tabs:
        if tab in NATIVE:
            notes.append(f"- {tab}: own saves, not tested")
            continue
        if tab not in APPS:
            notes.append(f"- {tab}: no emulator in board_ctl.APPS, not tested")
            continue
        roms = sorted(n for n in ls(b, f"/sd/roms/{tab}") if not n.startswith("."))
        if tab == "neogeo":
            roms = [r for r in roms if r != "neogeo.zip"]       # the BIOS
        if a.roms:
            roms = [r for r in roms if r in a.roms.split(",")]
        for rom in roms:
            res = check_rom(b, tab, rom, shots_dir)
            rows.append(res)
            print(f"{tab:7s} {rom[:40]:40s} save {res['save']:6s} {str(res['bytes']):>7s} resume {res['resume']:6s} "
                  f"load {res['load']:6s} dAB {res['dAB']:>5s} dAC {res['dAC']:>5s} {res['verdict']} {res['why']}", flush=True)
    with open(out, "a") as f:
        f.write(f"# Save / load check {datetime.datetime.now():%Y-%m-%d %H:%M}\n\n")
        f.write("| tab | ROM | save | bytes | resume | load | diff A-B | diff A-C | verdict | notes |\n|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['tab']} | {r['rom']} | {r['save']} | {r['bytes']} | {r['resume']} | {r['load']} | {r['dAB']} | {r['dAC']} | {r['verdict']} | {r['why']} |\n")
        if notes:
            f.write("\n" + "\n".join(notes) + "\n")
        f.write("\n")
    print("report:", out)


def ls_dirs(b, path):
    out = []
    for l in b.send(f"ls {path}", wait=r"^CTL ls (done|failed)", timeout=8, echo=False):
        m = re.match(r"CTL ls d\s+\d+ (.+)$", l)
        if m:
            out.append(m.group(1))
    return out


if __name__ == "__main__":
    main()
