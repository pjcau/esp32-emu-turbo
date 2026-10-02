#!/usr/bin/env python3
"""neogeo_frames.py: build and run the x86 harness (retro-go/mame-go/tools/neoframes.c).

    scripts/neogeo_frames.py run <sysdir> <game.zip> <frames> [neoframes options...]
    scripts/neogeo_frames.py compare <sysdir> <game.zip> <frames> [neoframes options...]

`run` prints the harness output. `compare` builds the harness twice, with
NEOBAND=0 (full-frame renderer) and NEOBAND=1 (band renderer, V1 of the Arcade
60 fps plan), runs both with the same input and reports the first frame whose
hash differs, or "IDENTICAL". <sysdir> is the MAME system directory (BIOS
`neogeo.zip` next to the game is found by mame-go itself; neospr/ files prepared
by neogeo_prepare.py are used when present).

Env: NEOFRAMES_BUILD (default build/neoframes) holds the objects per variant.
"""
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import neogeo_prepare as prep

ROOT = prep.ROOT
TOOL = os.path.join(ROOT, "retro-go", "mame-go", "tools", "neoframes.c")
BUILD = os.environ.get("NEOFRAMES_BUILD", os.path.join(ROOT, "build", "neoframes"))


def build(variant, flags):
    return prep.build(os.path.join(BUILD, variant), tool=TOOL, name="neoframes", extra_flags=flags)


def run(exe, args):
    r = subprocess.run([exe, *args], capture_output=True, text=True)
    hashes = {}
    for l in r.stdout.splitlines():
        p = l.split()
        if p and p[0] == "FRAME":
            hashes[int(p[1])] = p[4]
    return r, hashes


def main():
    if len(sys.argv) < 5 or sys.argv[1] not in ("run", "compare"):
        print(__doc__); return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "run":
        exe = build("full", [])
        r, _ = run(exe, args)
        sys.stdout.write(r.stdout); sys.stderr.write(r.stderr)
        return r.returncode
    full = build("full", ["-DNEOBAND=0"])
    band = build("band", ["-DNEOBAND=1"])
    rf, hf = run(full, args)
    rb, hb = run(band, args)
    sys.stderr.write(rf.stderr + rb.stderr)
    if rf.returncode or rb.returncode:
        print("harness failed: full", rf.returncode, "band", rb.returncode); return 1
    if not hf:
        print("no frames hashed"); return 1
    bad = [n for n in sorted(hf) if hb.get(n) != hf[n]]
    print("frames hashed", len(hf), "| band differs on", len(bad))
    if bad:
        n = bad[0]
        print("first difference at frame %d: full %s band %s" % (n, hf[n], hb.get(n)))
        print("dump both with: --dump <dir>@%d" % n)
        return 1
    print("IDENTICAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
