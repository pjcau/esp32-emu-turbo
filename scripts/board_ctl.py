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
    board_ctl.py volume 5               # set (or with no value read) the volume, 0-100
    board_ctl.py cat /sd/crash.log      # print a text file from the card
    board_ctl.py shot out.png           # screenshot of the running emulator (PNG)
    board_ctl.py get /sd/file local     # download a file from the card
    board_ctl.py acap 4 out.wav         # the audio samples as submitted (digital, no microphone)
    board_ctl.py raw "lcd off"          # stop sending frames to the panel (bench), "lcd on" back
    board_ctl.py script bench.txt       # one command per line, "sleep N" allowed
    board_ctl.py put ~/roms/x.sfc "/sd/roms/snes/x.sfc"   # upload (raw bytes + CRC32 over the console; from the launcher)
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
    "sms": "retro-core", "gg": "retro-core", "pce": "retro-core",
    "gba": "gbsp", "gen": "gwenesis", "md": "gwenesis", "doom": "prboom-go",
    "sg1": "retro-core", "col": "retro-core",
    "ngp": "retro-extra", "a26": "retro-extra", "arcade3d": "retro-extra", "lnx": "retro-core", "duke3d": "duke3d-go", "arcade": "mame-go", "neogeo": "mame-go", "cps1": "mame-go",
    "wolf3d": "wolf3d-go", "quake": "quake-go", "opentyrian": "opentyrian-go", "cannonball": "cannonball",
}
ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Board:
    def __init__(self, port, baud=115200):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        self.ser.reset_input_buffer()
        # App the key presses are meant for, set by launch(). If the app
        # crashed back to the launcher, blind presses there open "File
        # properties -> Delete selected file?" and confirm it: on 2026-09-27
        # a DOOM play script deleted 9 ROMs from the card that way. So once a
        # game was launched, every key/hold first checks the running app.
        self.expect_app = None

    def current_app(self):
        for l in self.send("ping", timeout=1.5, echo=False):
            m = re.search(r"app=(\S+)", l)
            if m:
                return m.group(1)
        return None

    def _check_app(self):
        if self.expect_app is None:
            return
        app = self.current_app()
        if app != self.expect_app:
            self.ser.write(b"release\n")
            raise RuntimeError(f"key presses stopped: running app is {app!r}, expected {self.expect_app!r} "
                               "(crashed back to the launcher?)")

    def readline(self):
        # the 50 ms timeout returns whatever arrived: keep a partial line until
        # its newline comes (long base64 lines of `get`/`adump` were cut in two)
        chunk = self.ser.readline().decode("utf-8", "replace")
        self._partial = getattr(self, "_partial", "") + chunk
        if not self._partial.endswith("\n"):
            return ""
        line, self._partial = self._partial, ""
        return ANSI.sub("", line).rstrip("\r\n")

    def send(self, line, wait=r"^CTL ", timeout=2.0, echo=True):
        """Send one command, return the CTL lines received before timeout."""
        if line.startswith(("key ", "hold ")):
            self._check_app()
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
        self.expect_app = part

    def put(self, local, remote, binary=True):
        """Upload a file to the card: 'putb <size> <path>' then the raw bytes
        (falls back to 'put' + base64 on firmware without putb). The board
        answers with the CRC32 of what it received; a mismatch is a failure."""
        import base64
        import zlib
        data = open(local, "rb").read()
        cmd = "putb" if binary else "put"
        reply = self.send(f"{cmd} {len(data)} {remote}", wait=r"^CTL (put (ready|failed)|err)", timeout=5)
        if binary and any(l.startswith("CTL err") for l in reply):
            return self.put(local, remote, binary=False)
        if not any(l.startswith("CTL put ready") for l in reply):
            return False
        # USB flow control paces the writes. Replies are only drained, never
        # waited for, while streaming: a blocking readline cost 50 ms per chunk
        # (40 KB/s) and stalls again on a half-arrived [debug] log line.
        t0, rx, result = time.time(), "", None

        def scan(rx):
            *lines, rest = rx.split("\n")
            for l in lines:
                if "CTL put " in l:
                    l = ANSI.sub("", l[l.index("CTL put "):]).rstrip("\r")
                    m = re.match(r"CTL put (?:done )?(\d+)", l)
                    print(l, f"({int(m.group(1)) / 1024 / (time.time() - t0):.0f} KB/s)" if m else "")
                    for w in ("done", "short", "failed"):
                        if l.startswith("CTL put " + w):
                            return rest, l if w == "done" else False
            return rest, None

        step = 16384 if binary else 3072
        for off in range(0, len(data), step):
            piece = data[off:off + step]
            self.ser.write(piece if binary else base64.b64encode(piece) + b"\n")
            if self.ser.in_waiting:
                rx, result = scan(rx + self.ser.read(self.ser.in_waiting).decode("utf-8", "replace"))
                if result is not None:
                    break
        deadline = time.time() + 10
        while result is None and time.time() < deadline:
            rx, result = scan(rx + self.ser.read(max(1, self.ser.in_waiting)).decode("utf-8", "replace"))
        done = bool(result)
        m = re.search(r"crc ([0-9a-f]{8})", result or "")
        if done and m and int(m.group(1), 16) != zlib.crc32(data):
            print(f"CRC MISMATCH: board {m.group(1)}, file {zlib.crc32(data):08x}", file=sys.stderr)
            done = False
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
            m = re.search(r"PROF n=(\d+) drawn=(\d+) wall=(\d+)ms fps=(\d+) busy=(\d+)%", l)
            if m:
                n += 1
                for k, v in zip(("n", "drawn", "wall", "fps", "busy"), m.groups()):
                    fields.setdefault(k, []).append(int(v))
                # rg_system's fps under-reports; n frames per wall ms is the real emulated rate
                fields.setdefault("efps", []).append(int(m.group(1)) * 1000 / int(m.group(3)))
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


def fetch(b, remote, piece=7200, tries=4):
    """A file from the card through `get`, piece by piece; a piece that
    arrives short (a USB line lost) is asked again."""
    import base64
    data = b""
    while True:
        for _ in range(tries):
            lines = b.send(f"get {remote} {len(data)} {piece}", wait=r"^CTL get (done|failed)", timeout=20, echo=False)
            got, ok = b"", bool(lines) and "done" in lines[-1]
            for l in lines:
                if l.startswith("CTL g "):
                    try:
                        got += base64.b64decode(l[6:])
                    except Exception:
                        ok = False
            m = re.search(r"CTL get done (\d+)", lines[-1]) if lines else None
            if ok and m and int(m.group(1)) == len(got):
                break
        else:
            raise SystemExit(f"get {remote}: piece at {len(data)} failed {tries} times")
        data += got
        if len(got) < piece:
            return data


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
    elif a.cmd in ("key", "hold") and b.current_app() == "launcher" and not os.environ.get("BOARD_CTL_LAUNCHER_KEYS"):
        # the launcher's file menu can delete ROMs: navigate it on purpose only
        sys.exit("refusing key presses in the launcher (set BOARD_CTL_LAUNCHER_KEYS=1 to allow)")
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
    elif a.cmd == "mv":   # board_ctl.py mv "/sd/a b.zip" "/sd/dir/a b.zip"
        b.send(f"mv {a.args[0]}|{a.args[1]}", wait=r"^CTL mv", timeout=5)
    elif a.cmd == "rm":
        b.send("rm " + " ".join(a.args), wait=r"^CTL rm", timeout=5)
    elif a.cmd == "shot":   # board_ctl.py shot out.png : screenshot of the running emulator
        remote = "/sd/shot.raw"   # raw RGB565 + width/height (mame-go screenshot handler)
        b.send("shot " + remote, wait=r"^CTL shot", timeout=20)
        import struct
        data = fetch(b, remote)
        out = a.args[0] if a.args else "shot.png"
        if len(data) > 4:
            from PIL import Image
            w, h = struct.unpack("<HH", data[:4])
            px = data[4:4 + w * h * 2]
            img = Image.new("RGB", (w, h))
            img.putdata([((v >> 11) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3)
                         for v in struct.unpack("<%dH" % (w * h), px)])
            img.save(out)
            print(f"{w}x{h} -> {out}")
        else:
            print("no screenshot")
    elif a.cmd == "get":    # board_ctl.py get /sd/file local
        data = fetch(b, a.args[0])
        open(a.args[1], "wb").write(data)
        print(f"{len(data)} bytes -> {a.args[1]}")
    elif a.cmd == "cat":
        for l in b.send("cat " + " ".join(a.args), wait=r"^CTL cat (done|failed)", timeout=10, echo=False):
            print(l[8:] if l.startswith("CTL cat ") else l)
    elif a.cmd == "acap":
        # acap SECONDS OUT.wav : the samples exactly as the emulator submits them
        import base64, wave
        secs = int(a.args[0]) if a.args else 3
        out = a.args[1] if len(a.args) > 1 else "capture.wav"
        b.send(f"acap {secs}", wait=r"^CTL acap", timeout=3, echo=False)
        time.sleep(secs + 1)
        data, rate = bytearray(), 32000
        for l in b.send("adump", wait=r"^CTL adump done", timeout=120, echo=False):
            if l.startswith("CTL a "):
                data += base64.b64decode(l[6:].strip())
            elif l.startswith("CTL adump done"):
                rate = int(l.split()[4])
        w = wave.open(out, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(data)); w.close()
        print(f"{out}: {len(data) // 2} samples at {rate} Hz")
    elif a.cmd == "volume":
        b.send("volume " + (a.args[0] if a.args else ""), wait=r"^CTL volume", timeout=3)
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
