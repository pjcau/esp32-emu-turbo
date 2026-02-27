#!/usr/bin/env python3
"""PCB parse cache — parse .kicad_pcb once, cache as JSON for all consumers.

Provides:
  build_cache(pcb_path) — parse PCB, write .pcb_cache.json
  load_cache(pcb_path)  — load JSON (auto-rebuilds if stale/missing)

Cache invalidation: SHA-256 hash of .kicad_pcb stored in JSON.
If the file changes, the cache auto-rebuilds on next load_cache() call.

Usage:
    from pcb_cache import load_cache
    cache = load_cache()
    # cache["segments"], cache["vias"], cache["pads"], cache["nets"], ...
"""

import hashlib
import json
import math
import re
import time
from pathlib import Path

_DEFAULT_PCB = Path(__file__).parent.parent / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
_CACHE_VERSION = 1


# ── Helpers ──────────────────────────────────────────────────────────

def _sha256(path):
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _rotate(x, y, angle_deg):
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    return (x * c - y * s, x * s + y * c)


# ── Canonical parser ─────────────────────────────────────────────────

def parse_pcb_full(path=None):
    """Canonical PCB parser — extracts ALL data into a single dict.

    Adapted from analyze_pad_distances.parse_pcb() (pads, vias, segments)
    extended with zone parsing from short_circuit_analysis.py.

    Returns dict with: nets, pads, vias, segments, zones, refs,
    filled_polygons, stats.
    """
    if path is None:
        path = _DEFAULT_PCB
    text = Path(path).read_text(encoding="utf-8")

    nets = []
    pads = []
    vias = []
    segments = []
    zones = []
    refs = set()

    # ── Net declarations ──────────────────────────────────────────
    for m in re.finditer(r'^\s+\(net\s+(\d+)\s+"([^"]*)"\)', text, re.M):
        nets.append({"id": int(m.group(1)), "name": m.group(2)})

    # ── Footprints → pads + refs ──────────────────────────────────
    i = 0
    while True:
        idx = text.find("(footprint ", i)
        if idx == -1:
            break
        depth = 0
        j = idx
        while j < len(text):
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        fp_block = text[idx:j + 1]
        i = j + 1

        at_m = re.search(
            r'\(footprint\s+"[^"]*"\s+\(at\s+([-\d.]+)\s+([-\d.]+)'
            r'(?:\s+([-\d.]+))?\)',
            fp_block)
        if not at_m:
            continue
        fp_x = float(at_m.group(1))
        fp_y = float(at_m.group(2))
        fp_rot = float(at_m.group(3)) if at_m.group(3) else 0.0

        ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', fp_block)
        ref = ref_m.group(1) if ref_m else "?"
        if (ref and ref != "?" and not ref.startswith('#')
                and '?' not in ref and not re.match(r'^[A-Z]+$', ref)):
            refs.add(ref)

        # Extract pad sub-blocks
        k = 0
        while True:
            pidx = fp_block.find("(pad ", k)
            if pidx == -1:
                break
            pdepth = 0
            pk = pidx
            while pk < len(fp_block):
                if fp_block[pk] == '(':
                    pdepth += 1
                elif fp_block[pk] == ')':
                    pdepth -= 1
                    if pdepth == 0:
                        break
                pk += 1
            pad_block = fp_block[pidx:pk + 1]
            k = pk + 1

            pad_m = re.match(
                r'\(pad\s+"([^"]*)"\s+(\S+)\s+(\S+)'
                r'\s+\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)',
                pad_block)
            if not pad_m:
                continue

            pnum = pad_m.group(1)
            ptype = pad_m.group(2)   # smd, thru_hole, np_thru_hole
            pshape = pad_m.group(3)  # rect, circle, oval, roundrect
            plx = float(pad_m.group(4))
            ply = float(pad_m.group(5))
            pad_rot_local = float(pad_m.group(6)) if pad_m.group(6) else 0.0

            size_m = re.search(r'\(size\s+([\d.]+)\s+([\d.]+)\)', pad_block)
            if not size_m:
                continue
            pw = float(size_m.group(1))
            ph = float(size_m.group(2))

            drill_m = re.search(r'\(drill\s+([\d.]+)\)', pad_block)
            drill = float(drill_m.group(1)) if drill_m else 0.0

            layers_m = re.search(r'\(layers\s+([^)]+)\)', pad_block)
            layers_str = layers_m.group(1) if layers_m else ""

            copper_layers = []
            if '"F.Cu"' in layers_str or 'F.Cu' in layers_str:
                copper_layers.append("F.Cu")
            if '"B.Cu"' in layers_str or 'B.Cu' in layers_str:
                copper_layers.append("B.Cu")
            if '"*.Cu"' in layers_str or '*.Cu' in layers_str:
                copper_layers.extend(["F.Cu", "B.Cu"])
            copper_layers = list(set(copper_layers))
            if not copper_layers:
                continue

            # Absolute position
            total_rot = fp_rot + pad_rot_local
            if total_rot != 0:
                rlx, rly = _rotate(plx, ply, total_rot)
            else:
                rlx, rly = plx, ply
            abs_x = fp_x + rlx
            abs_y = fp_y + rly

            # Rotate pad size for 90/270 deg
            eff_rot = total_rot % 360
            if (eff_rot in (90, 270) or
                    (eff_rot not in (0, 180) and abs(eff_rot % 180 - 90) < 5)):
                pw, ph = ph, pw

            # Net
            net_m = re.search(r'\(net\s+(\d+)\s+"[^"]*"\)', pad_block)
            if not net_m:
                net_m = re.search(r'\(net\s+(\d+)\)', pad_block)
            pad_net = int(net_m.group(1)) if net_m else 0

            for clayer in copper_layers:
                pads.append({
                    "ref": ref, "num": pnum,
                    "x": round(abs_x, 4), "y": round(abs_y, 4),
                    "w": round(pw, 4), "h": round(ph, 4),
                    "shape": pshape, "layer": clayer,
                    "net": pad_net,
                    "fp_x": round(fp_x, 4), "fp_y": round(fp_y, 4),
                    "type": ptype, "drill": round(drill, 4),
                })

    # ── Vias ──────────────────────────────────────────────────────
    for m in re.finditer(
        r'\(via\s+\(at\s+([-\d.]+)\s+([-\d.]+)\)\s+'
        r'\(size\s+([\d.]+)\)\s+\(drill\s+([\d.]+)\)'
        r'(?:[^)]*\(net\s+(\d+)\))?',
        text
    ):
        vias.append({
            "x": round(float(m.group(1)), 4),
            "y": round(float(m.group(2)), 4),
            "size": round(float(m.group(3)), 4),
            "drill": round(float(m.group(4)), 4),
            "net": int(m.group(5)) if m.group(5) else 0,
        })

    # ── Segments ──────────────────────────────────────────────────
    for m in re.finditer(
        r'\(segment\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+'
        r'\(end\s+([-\d.]+)\s+([-\d.]+)\)\s+'
        r'\(width\s+([\d.]+)\)\s+'
        r'\(layer\s+"([^"]+)"\)'
        r'(?:\s+\(net\s+(\d+)\))?',
        text
    ):
        segments.append({
            "x1": float(m.group(1)), "y1": float(m.group(2)),
            "x2": float(m.group(3)), "y2": float(m.group(4)),
            "width": float(m.group(5)),
            "layer": m.group(6),
            "net": int(m.group(7)) if m.group(7) else 0,
        })

    # ── Zones ─────────────────────────────────────────────────────
    zone_pat = re.compile(
        r'\(zone\s*\n'
        r'\s+\(net\s+(\d+)\)\s*\n'
        r'\s+\(net_name\s+"([^"]+)"\)\s*\n'
        r'\s+\(layer\s+"([^"]+)"\)\s*\n'
        r'[\s\S]*?\(priority\s+(\d+)\)?',
        re.M)
    for m in zone_pat.finditer(text):
        zones.append({
            "net": int(m.group(1)),
            "net_name": m.group(2),
            "layer": m.group(3),
            "priority": int(m.group(4)) if m.group(4) else -1,
        })
    # Fallback
    if not zones:
        for m in re.finditer(
            r'\(zone\s*\n\s+\(net\s+(\d+)\)\s*\n'
            r'\s+\(net_name\s+"([^"]+)"\)\s*\n'
            r'\s+\(layer\s+"([^"]+)"\)',
            text
        ):
            pr = re.search(r'\(priority\s+(\d+)\)',
                           text[m.start():m.start() + 500])
            zones.append({
                "net": int(m.group(1)),
                "net_name": m.group(2),
                "layer": m.group(3),
                "priority": int(pr.group(1)) if pr else -1,
            })

    # ── filled_polygon count ──────────────────────────────────────
    filled_polygons = len(re.findall(r'\(filled_polygon\b', text))

    return {
        "version": _CACHE_VERSION,
        "pcb_hash": "",  # filled by build_cache
        "stats": {
            "pads": len(pads), "vias": len(vias),
            "segments": len(segments), "zones": len(zones),
            "nets": len(nets), "refs": len(refs),
            "filled_polygons": filled_polygons,
        },
        "nets": nets,
        "pads": pads,
        "vias": vias,
        "segments": segments,
        "zones": zones,
        "refs": sorted(refs),
        "filled_polygons": filled_polygons,
    }


# ── Build / Load ─────────────────────────────────────────────────────

def build_cache(pcb_path=None, cache_path=None):
    """Parse PCB and write .pcb_cache.json. Returns the cache dict."""
    if pcb_path is None:
        pcb_path = _DEFAULT_PCB
    pcb_path = Path(pcb_path)
    if cache_path is None:
        cache_path = pcb_path.parent / ".pcb_cache.json"

    t0 = time.time()
    data = parse_pcb_full(pcb_path)
    data["pcb_hash"] = _sha256(pcb_path)

    with open(cache_path, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    ms = (time.time() - t0) * 1000
    s = data["stats"]
    print(f"  Cache built: {cache_path.name} "
          f"({s['pads']}p/{s['vias']}v/{s['segments']}s in {ms:.0f}ms)")
    return data


def load_cache(pcb_path=None, cache_path=None):
    """Load cache JSON, auto-rebuild if hash mismatches or missing."""
    if pcb_path is None:
        pcb_path = _DEFAULT_PCB
    pcb_path = Path(pcb_path)
    if cache_path is None:
        cache_path = pcb_path.parent / ".pcb_cache.json"

    if cache_path.exists():
        with open(cache_path) as f:
            data = json.load(f)
        if (data.get("pcb_hash") == _sha256(pcb_path)
                and data.get("version") == _CACHE_VERSION):
            return data

    # Cache miss or stale — rebuild
    return build_cache(pcb_path, cache_path)


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    pcb = sys.argv[1] if len(sys.argv) > 1 else str(_DEFAULT_PCB)
    data = build_cache(Path(pcb))
    print(f"  Stats: {data['stats']}")
