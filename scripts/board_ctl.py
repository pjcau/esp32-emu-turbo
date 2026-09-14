#!/usr/bin/env python3
"""Drive the ESP32 Emu Turbo board over its USB console (bench remote control).

Counterpart of RG_GAMEPAD_CONSOLE in retro-go/components/retro-go/rg_input.c:
every line sent to the console is a command, every "CTL ..." line back is
its acknowledgement, so a script can select the emulator, launch a ROM,
press buttons and read the SNES_PROF counters without touching the board.

    board_ctl.py ping
    board_ctl.py ls /sd/roms/snes
    board_ctl.py launch snes "/sd/roms/snes/Super Mario World.sfc"
    board_ctl.py key start 150          # press START for 150 ms
    board_ctl.py key a+b 100            # combos with '+'
    board_ctl.py hold right             # held until 'release'
    board_ctl.py release
    board_ctl.py save 0 | load 0        # emulator save-state (slot 0)
    board_ctl.py resume snes "/sd/roms/snes/x.sfc"   # launch + load slot 0 = repeatable benchmark scene
    board_ctl.py resume1 snes "/sd/roms/snes/x.sfc"  # same, slot 1
    board_ctl.py capture 10             # 10 s of PROF lines + averages
    board_ctl.py script bench.txt       # one command per line, "sleep N" allowed
    board_ctl.py put ~/roms/x.sfc "/sd/roms/snes/x.sfc"   # upload (base64 over the console; from the launcher)
    board_ctl.py rm "/sd/roms/snes/x.sfc"
    board_ctl.py launcher | reboot | raw "<line>"

Port: --port or ESP_PORT (default /dev/ttyACM0).
"""
import argparse
import os
import re
import statistics
import sys
import time

import serial

APPS = {  # app short name -> partition (launcher/main/applications.c)
    "nes": "retro-core", "snes": "retro-core", "gb": "retro-core", "gbc": "retro-core",
    "sms": "retro-core", "gg": "retro-core", "pce": "retro-core", "lynx": "retro-core",
    "gw": "retro-core", "msx": "fmsx", "gen": "gwenesis", "md": "gwenesis", "doom": "prboom-go",
}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Board:
    def __init__(self, port, baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.ser.reset_input_buffer()

    def readline(self):
        line = self.ser.readline().decode("utf-8", "replace")
        return ANSI.sub("", line).rstrip("\r\n")

    def send(self, line, wait=r"^CTL ", timeout=2.0, echo=True):
        """Send one command, return the CTL lines received before timeout."""
        self.ser.write((line + "\n").encode())
        self.ser.flush()
        out, deadline = [], time.time() + timeout
        while time.time() < deadline:
            l = self.readline()
            if not l:
                continue
            # replies come from the input task and can land mid-way through a
            # log line printed by the emulator task: cut from the marker
            if "CTL " in l:
                l = l[l.index("CTL "):]
                out.append(l)
                if echo:
                    print(l)
                if not l.startswith("CTL ls ") or l.startswith("CTL ls done") or l.startswith("CTL ls failed"):
                    if wait and re.search(wait, l):
                        break
        if not out:
            print(f"(no CTL reply to '{line}' within {timeout}s)", file=sys.stderr)
        return out

    def key(self, names, ms=100):
        self.send(f"key {names} {ms}")
        time.sleep(ms / 1000 + 0.08)  # release + debounce before the next one

    def launch(self, app, rom, resume=False, slot=0):
        part = APPS.get(app, "retro-core")
        cmd = f"resume{slot}" if resume else "launch"
        self.send(f"{cmd} {part} {app} {rom}", timeout=3)

    def put(self, local, remote):
        """Upload a file to the card: 'put <size> <path>' then base64 text."""
        import base64
        data = open(local, "rb").read()
        if not self.send(f"put {len(data)} {remote}", wait=r"^CTL put (ready|failed)", timeout=5):
            return False
        t0, done = time.time(), False
        for off in range(0, len(data), 3072):
            self.ser.write(base64.b64encode(data[off:off + 3072]) + b"\n")
            l = self.readline()
            if "CTL put " in l:
                print(l[l.index("CTL "):], f"({(off + 3072) / 1024 / (time.time() - t0):.0f} KB/s)")
        deadline = time.time() + 10
        while time.time() < deadline:
            l = self.readline()
            if "CTL put " in l:
                l = l[l.index("CTL "):]
                print(l)
                if any(w in l for w in ("done", "short", "failed")):
                    done = "done" in l
                    break
        print(f"{len(data)} bytes in {time.time() - t0:.1f}s")
        return done

    def wait_boot(self, timeout=15):
        """Wait until the (re)booted app answers ping."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(1.0)
            if self.send("ping", timeout=1.0, echo=False):
                return True
        return False

    def capture(self, seconds, echo=True, summary=True):
        """Collect PROF lines for `seconds`; return per-field averages."""
        fields, deadline = {}, time.time() + seconds
        n = 0
        while time.time() < deadline:
            l = self.readline()
            if not l:
                continue
            if echo and ("PROF" in l or "FPS:" in l):
                print(l)
            m = re.search(r"PROF n=(\d+) drawn=(\d+) .*?fps=(\d+) busy=(\d+)%", l)
            if m:
                n += 1
                for k, v in zip(("n", "drawn", "fps", "busy"), m.groups()):
                    fields.setdefault(k, []).append(int(v))
                for k, v in re.findall(r"(\w[\w()]*)=(\d+)", l.split("us/frame:")[1]):
                    fields.setdefault(k, []).append(int(v))
            m = re.search(r"PROF/drawn-frame: (.*)", l)
            if m:
                for k, v in re.findall(r"(\w+)=([\d.]+)", m.group(1)):
                    fields.setdefault("d." + k, []).append(float(v))
                mm = re.search(r"modes (.*)", m.group(1))
                if mm:  # "modes 0:30 1:0 ... 7:508" = strip-lines per BG mode, per second
                    for k, v in re.findall(r"(\d):(\d+)", mm.group(1)):
                        fields.setdefault("m" + k, []).append(float(v))
        means = {k: statistics.mean(v) for k, v in fields.items() if v}
        if not summary:
            return means
        summary = means
        if n:
            print(f"--- {n} PROF samples over {seconds}s ---")
            keys = ["fps", "drawn", "busy", "main(drawn)", "main(skip)", "R", "mix", "loop",
                    "d.update", "d.clear", "d.sub", "d.main", "d.combine", "d.obj", "d.objsetup",
                    "d.bg0", "d.bg1", "d.bg2", "d.bg3", "d.tiles", "d.blank", "d.conv", "d.strips"]
            print("  ".join(f"{k}={summary[k]:.1f}" for k in keys if k in summary))
        else:
            print("no PROF lines seen (not a SNES_PROF build, or not in the SNES emulator?)")
        return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=os.environ.get("ESP_PORT", "/dev/ttyACM0"))
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    b = Board(a.port)

    if a.cmd == "ping":
        ok = b.send("ping")
        sys.exit(0 if ok else 1)
    elif a.cmd == "ls":
        b.send(f"ls {a.args[0] if a.args else '/sd'}", wait=r"^CTL ls (done|failed)", timeout=10)
    elif a.cmd == "key":
        b.key(a.args[0], int(a.args[1]) if len(a.args) > 1 else 100)
    elif a.cmd == "hold":
        b.send(f"hold {a.args[0]}")
    elif a.cmd == "release":
        b.send("release " + (a.args[0] if a.args else ""))
    elif a.cmd == "launch" or a.cmd.startswith("resume"):
        b.launch(a.args[0], " ".join(a.args[1:]), resume=a.cmd != "launch", slot=int(a.cmd[6:] or 0))
        print("booted" if b.wait_boot() else "no ping after launch", file=sys.stderr)
    elif a.cmd in ("save", "load"):
        b.send(f"{a.cmd} {a.args[0] if a.args else 0}", wait=rf"^CTL {a.cmd} (done|failed)", timeout=10)
    elif a.cmd in ("launcher", "reboot"):
        b.send(a.cmd)
        print("booted" if b.wait_boot() else "no ping after reboot", file=sys.stderr)
    elif a.cmd == "capture":
        b.capture(float(a.args[0]) if a.args else 5)
    elif a.cmd == "put":
        sys.exit(0 if b.put(os.path.expanduser(a.args[0]), " ".join(a.args[1:])) else 1)
    elif a.cmd == "rm":
        b.send("rm " + " ".join(a.args), wait=r"^CTL rm", timeout=5)
    elif a.cmd == "raw":
        b.send(" ".join(a.args), wait=None, timeout=1)
    elif a.cmd == "script":
        for line in open(a.args[0]):
            line = line.split("#")[0].strip()
            if not line:
                continue
            print(f"> {line}")
            parts = line.split()
            if parts[0] == "sleep":
                time.sleep(float(parts[1]))
            elif parts[0] == "key":
                b.key(parts[1], int(parts[2]) if len(parts) > 2 else 100)
            elif parts[0] == "capture":
                b.capture(float(parts[1]) if len(parts) > 1 else 5)
            elif parts[0] in ("launch", "resume"):
                b.launch(parts[1], " ".join(parts[2:]), resume=parts[0] == "resume")
                b.wait_boot()
            elif parts[0] in ("save", "load"):
                b.send(line, wait=rf"^CTL {parts[0]} (done|failed)", timeout=10)
            else:
                b.send(line)
    else:
        ap.error(f"unknown command {a.cmd}")


if __name__ == "__main__":
    main()
