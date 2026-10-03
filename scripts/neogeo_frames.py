#!/usr/bin/env python3
"""neogeo_frames.py: build and run the x86 harness (retro-go/mame-go/tools/neoframes.c).

    scripts/neogeo_frames.py run <sysdir> <game.zip> <frames> [neoframes options...]
    scripts/neogeo_frames.py compare <sysdir> <game.zip> <frames> [neoframes options...]
    scripts/neogeo_frames.py mix <sysdir> <game.zip> <frames> [neoframes options...]
    scripts/neogeo_frames.py pal <sysdir> <game.zip> <frames> [neoframes options...]
    scripts/neogeo_frames.py ref <reference-exe> <sysdir> <game.zip> <frames> [neoframes options...]
    scripts/neogeo_frames.py count <sysdir> <game.zip> <frames> [neoframes options...]

`run` prints the harness output. `compare` builds the harness twice, with
NEOBAND=0 (full-frame renderer) and NEOBAND=1 (band renderer, V1 of the Arcade
60 fps plan), runs both with the same input and reports the first frame whose
hash differs, or "IDENTICAL". `mix` runs the band build twice, with the frame's
sound mix where it was (NEOMIX1=0, inside the YM2610 stream update) and inside
the sound board's job (the default, core 1 on the board), and requires the same
picture AND the same samples, with sound actually playing. `pal` does the same for the palette work
of step O2: the band build with PALFAST=0 (every colour walked every frame)
against the default with PALCHECK=1 (the palettes kept across frames, each
frame's array checked against the full rebuild); same picture required. `ref`
is for a change with no switch (the sprite plotter): the band build of the
current tree against a harness built BEFORE the change (copy
build/neoframes/band/neoframes aside before pulling); same picture and same
samples required. `count` proves the exact skip of wait loops that count
(m68kcpu.c): the band build with M68KCOUNT=0 against the default; same picture
and same samples required, and it prints how many of the 68000's cycles each
run skipped, so a run where the skip never fired is seen. <sysdir> is the MAME system directory (BIOS
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


def run(exe, args, env=None, audio=None):
    """Runs the harness; returns it and {frame: picture hash}. `audio`, a dict,
    receives {frame: running sample hash} and "all": (hash, samples, nonzero)."""
    r = subprocess.run([exe, *args], capture_output=True, text=True,
                       env=dict(os.environ, **env) if env else None)
    hashes = {}
    for l in r.stdout.splitlines():
        p = l.split()
        if p and p[0] == "FRAME":
            hashes[int(p[1])] = p[4]
        elif audio is not None and p and p[0] == "AUDIO":
            if p[1] == "all":
                audio["all"] = (p[2], int(p[4]), int(p[6]))
            else:
                audio[int(p[1])] = p[3]
    return r, hashes


def count(args):
    """The exact skip of counting wait loops: same picture, same samples, fewer cycles."""
    exe = build("band", ["-DNEOBAND=1"])
    a0, a1 = {}, {}
    r0, h0 = run(exe, args, env={"M68KCOUNT": "0", "IDLESTAT": "1"}, audio=a0)
    r1, h1 = run(exe, args, env={"M68KCOUNT": "1", "IDLESTAT": "1"}, audio=a1)
    if r0.returncode or r1.returncode:
        sys.stderr.write(r0.stderr + r1.stderr)
        print("harness failed: off", r0.returncode, "on", r1.returncode); return 1
    skipped = []
    for name, r in (("off", r0), ("on ", r1)):
        line = [l for l in r.stderr.splitlines() if l.startswith("IDLESTAT cycles")]
        print("skip %s: %s" % (name, line[0] if line else "no IDLESTAT line"))
        m = line and __import__("re").search(r"skipped as idle (\d+)", line[0])
        skipped.append(int(m.group(1)) if m else -1)
    if not h0:
        print("no frames hashed"); return 1
    bad = [n for n in sorted(h0) if h1.get(n) != h0[n]]
    bada = [n for n in sorted(k for k in a0 if k != "all") if a1.get(n) != a0[n]]
    print("frames hashed", len(h0), "| picture differs on", len(bad), "| sound differs from frame", bada[0] if bada else "-")
    if bad:
        print("first picture difference at frame %d: off %s on %s" % (bad[0], h0[bad[0]], h1.get(bad[0])))
    if bad or bada or len(h1) != len(h0) or a0.get("all") != a1.get("all"):
        return 1
    if skipped[1] <= skipped[0]:
        print("IDENTICAL, but the skip removed no extra cycles in this run: nothing proven for this game")
        return 0
    print("IDENTICAL")
    return 0


def ref(ref_exe, args):
    """The current band build against a reference harness built before a change."""
    if not os.path.isfile(ref_exe):
        print("no reference harness at", ref_exe); return 1
    exe = build("band", ["-DNEOBAND=1"])
    if os.path.samefile(ref_exe, exe) or open(ref_exe, "rb").read() == open(exe, "rb").read():
        print("the reference harness is the current build: nothing proven"); return 1
    a0, a1 = {}, {}
    r0, h0 = run(ref_exe, args, audio=a0)
    r1, h1 = run(exe, args, audio=a1)
    sys.stderr.write(r0.stderr + r1.stderr)
    if r0.returncode or r1.returncode:
        print("harness failed: reference", r0.returncode, "current", r1.returncode); return 1
    if not h0:
        print("no frames hashed"); return 1
    bad = [n for n in sorted(h0) if h1.get(n) != h0[n]]
    bada = [n for n in sorted(k for k in a0 if k != "all") if a1.get(n) != a0[n]]
    print("frames hashed", len(h0), "| picture differs on", len(bad), "| sound differs from frame", bada[0] if bada else "-")
    if bad:
        print("first difference at frame %d: reference %s current %s" % (bad[0], h0[bad[0]], h1.get(bad[0])))
        print("dump both with: --dump <dir>@%d" % bad[0])
    if bad or bada or len(h1) != len(h0):
        return 1
    print("IDENTICAL")
    return 0


def pal(args):
    """The palette kept across frames and the sparse palette_recalc_8(): same picture."""
    exe = build("band", ["-DNEOBAND=1"])
    r0, h0 = run(exe, args, env={"PALFAST": "0"})
    r1, h1 = run(exe, args, env={"PALFAST": "1", "PALCHECK": "1", "PALSTAT": "1"})
    sys.stderr.write(r0.stderr + r1.stderr)
    for l in r1.stdout.splitlines():
        if l.startswith(("PALCHECK", "PALSTAT")):
            print(l)
    if r0.returncode or r1.returncode:
        print("harness failed: PALFAST=0", r0.returncode, "PALFAST=1", r1.returncode); return 1
    if not h0:
        print("no frames hashed"); return 1
    kept = [l for l in r1.stdout.splitlines() if l.startswith("PALCHECK ok:")]
    stat = [l for l in r1.stdout.splitlines() if l.startswith("PALSTAT")]
    if not kept and not stat:
        # 16-bit games (the raster ones: Metal Slug 2, KOF95) reach neither
        # neoband_palette() nor palette_recalc_8(): the change does not touch them
        print("NOT APPLICABLE: this game runs neither changed function (16-bit palette path); the picture is still compared")
    elif not kept or int(kept[0].split()[2]) == 0:
        print("no frame took the kept-palette path: nothing proven"); return 1
    bad = [n for n in sorted(h0) if h1.get(n) != h0[n]]
    print("frames hashed", len(h0), "| picture differs on", len(bad))
    if bad:
        print("first difference at frame %d: %s vs %s" % (bad[0], h0[bad[0]], h1.get(bad[0])))
        return 1
    print("IDENTICAL")
    return 0


def mix(args):
    """The sound mix moved into the sound board's job: same picture, same samples."""
    exe = build("band", ["-DNEOBAND=1"])
    a0, a1 = {}, {}
    r0, h0 = run(exe, args, env={"NEOMIX1": "0"}, audio=a0)
    r1, h1 = run(exe, args, env={"NEOMIX1": "1"}, audio=a1)
    sys.stderr.write(r0.stderr + r1.stderr)
    if r0.returncode or r1.returncode:
        print("harness failed: mix on core 0", r0.returncode, "in the job", r1.returncode); return 1
    for name, r, want in (("NEOMIX1=0", r0, "(Z80 + YM2610)"), ("NEOMIX1=1", r1, "(Z80 + YM2610 + mix)")):
        if want not in r.stdout + r.stderr:
            print("%s: the run did not report '%s': the switch did not take" % (name, want)); return 1
    if not h0 or "all" not in a0 or "all" not in a1:
        print("no frames or no samples hashed"); return 1
    if a0["all"][1] == 0 or a0["all"][2] == 0:
        print("the reference run is silent (%d samples, %d non-zero): nothing proven" % a0["all"][1:]); return 1
    badv = [n for n in sorted(h0) if h1.get(n) != h0[n]]
    bada = [n for n in sorted(k for k in a0 if k != "all") if a1.get(n) != a0[n]]
    print("frames hashed", len(h0), "| picture differs on", len(badv), "| samples", a0["all"][1],
          "non-zero", a0["all"][2], "| sound differs from frame", bada[0] if bada else "-")
    if badv:
        print("first picture difference at frame %d: %s vs %s" % (badv[0], h0[badv[0]], h1.get(badv[0])))
    if bada:
        print("first sound difference at frame %d: %s vs %s" % (bada[0], a0[bada[0]], a1.get(bada[0])))
    if badv or bada or a0["all"] != a1["all"]:
        return 1
    print("IDENTICAL")
    return 0


def main():
    if len(sys.argv) < 5 or sys.argv[1] not in ("run", "compare", "mix", "pal", "ref", "count"):
        print(__doc__); return 2
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "mix":
        return mix(args)
    if cmd == "pal":
        return pal(args)
    if cmd == "ref":
        return ref(args[0], args[1:])
    if cmd == "count":
        return count(args)
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
