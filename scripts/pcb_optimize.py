#!/usr/bin/env python3
"""PCB Layout Optimization Analysis.

Analyzes the generated .kicad_pcb file and scores the layout across
five categories: trace length, copper balance, thermal vias, via
optimization, and parallel trace (crosstalk) detection.

Usage:
    python3 scripts/pcb_optimize.py [path/to/file.kicad_pcb]

Exit code is always 0 (advisory tool, not pass/fail).
"""

import re
import sys
import math
from pathlib import Path
from collections import defaultdict

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Board dimensions ─────────────────────────────────────────────
BOARD_W = 160.0  # mm
BOARD_H = 75.0   # mm

# ── Power components requiring thermal vias ──────────────────────
POWER_COMPONENTS = {
    "U2": {"name": "IP5306", "x": 110.0, "y": 42.5, "power_w": 1.5},
    "U3": {"name": "AMS1117", "x": 125.0, "y": 55.5, "power_w": 0.8},
    "U5": {"name": "PAM8403", "x": 30.0, "y": 29.5, "power_w": 1.0},
}

# ── Data signal net IDs for crosstalk analysis ───────────────────
# LCD_D0-D7 = nets 6-13, SD SPI = nets 20-23, I2S = nets 24-26
DATA_SIGNAL_NETS = set(range(6, 14)) | set(range(20, 24)) | set(range(24, 27))


# =====================================================================
#  PCB Parsing
# =====================================================================

def parse_pcb(filepath):
    """Parse KiCad PCB file - segments, vias, zones, nets."""
    text = Path(filepath).read_text()

    result = {
        "segments": [],
        "vias": [],
        "zones": [],
        "nets": {},
    }

    # Extract segments: (segment (start X Y) (end X Y) (width W) (layer L) (net N))
    for m in re.finditer(
        r'\(segment\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(end\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(width\s+([\d.]+)\)\s+'
        r'\(layer\s+"([^"]+)"\)\s+'
        r'\(net\s+(\d+)\)', text
    ):
        result["segments"].append({
            "x1": float(m.group(1)), "y1": float(m.group(2)),
            "x2": float(m.group(3)), "y2": float(m.group(4)),
            "width": float(m.group(5)),
            "layer": m.group(6),
            "net": int(m.group(7)),
        })

    # Extract vias with net: (via (at X Y) (size S) (drill D) ... (net N))
    for m in re.finditer(
        r'\(via\s+\(at\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(size\s+([\d.]+)\)\s+'
        r'\(drill\s+([\d.]+)\).*?\(net\s+(\d+)\)', text
    ):
        result["vias"].append({
            "x": float(m.group(1)), "y": float(m.group(2)),
            "size": float(m.group(3)),
            "drill": float(m.group(4)),
            "net": int(m.group(5)),
        })

    # Extract net declarations: (net ID "NAME")
    for m in re.finditer(r'\(net\s+(\d+)\s+"([^"]*)"\)', text):
        nid = int(m.group(1))
        name = m.group(2)
        if nid > 0 and name:
            result["nets"][nid] = name

    # Extract zones: (zone ... (net N) ... (net_name "NAME") ... (layer "L"))
    for m in re.finditer(
        r'\(zone\s+.*?\(net\s+(\d+)\).*?\(net_name\s+"([^"]*)"\).*?'
        r'\(layer\s+"([^"]+)"\)', text
    ):
        result["zones"].append({
            "net": int(m.group(1)),
            "net_name": m.group(2),
            "layer": m.group(3),
        })

    return result


# =====================================================================
#  Analysis 1: Trace Length
# =====================================================================

def analyze_trace_length(data):
    """Analyze total trace length per net and flag long traces."""
    net_segments = defaultdict(list)
    for seg in data["segments"]:
        length = math.hypot(seg["x2"] - seg["x1"], seg["y2"] - seg["y1"])
        net_segments[seg["net"]].append({
            "length": length,
            "seg": seg,
        })

    total_length = sum(s["length"] for segs in net_segments.values() for s in segs)
    total_count = len(data["segments"])

    # Build per-net summary
    net_summary = []
    for net_id, segs in sorted(net_segments.items()):
        net_name = data["nets"].get(net_id, f"net_{net_id}")
        total = sum(s["length"] for s in segs)
        longest = max(s["length"] for s in segs)
        net_summary.append({
            "net_id": net_id,
            "name": net_name,
            "segments": len(segs),
            "total_length": total,
            "longest_seg": longest,
        })

    # Sort by total length descending
    net_summary.sort(key=lambda x: x["total_length"], reverse=True)

    # Flag issues
    flags = []
    for ns in net_summary:
        if ns["total_length"] > 80.0:
            flags.append(
                f"Net \"{ns['name']}\" total length {ns['total_length']:.1f}mm > 80mm"
            )
        if ns["longest_seg"] > 40.0:
            flags.append(
                f"Net \"{ns['name']}\" has segment {ns['longest_seg']:.1f}mm > 40mm"
            )

    # Score: 20 if no flags, -2 per flag, min 0
    score = max(0, 20 - 2 * len(flags))

    return {
        "score": score,
        "total_count": total_count,
        "total_length": total_length,
        "top_nets": net_summary[:10],
        "flags": flags,
    }


# =====================================================================
#  Analysis 2: Copper Balance
# =====================================================================

def analyze_copper_balance(data):
    """Analyze trace length distribution across copper layers."""
    layer_length = defaultdict(float)
    for seg in data["segments"]:
        length = math.hypot(seg["x2"] - seg["x1"], seg["y2"] - seg["y1"])
        layer_length[seg["layer"]] += length

    total = sum(layer_length.values())
    if total == 0:
        return {"score": 0, "layers": {}, "flags": ["No traces found"]}

    # Compute percentages
    layer_pct = {}
    for layer in ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]:
        length = layer_length.get(layer, 0.0)
        pct = (length / total * 100) if total > 0 else 0.0
        layer_pct[layer] = {"length": length, "pct": pct}

    # Zone info
    zone_layers = defaultdict(list)
    for z in data["zones"]:
        zone_layers[z["layer"]].append(z["net_name"])

    flags = []

    # Check F.Cu vs B.Cu balance
    fcu = layer_length.get("F.Cu", 0.0)
    bcu = layer_length.get("B.Cu", 0.0)
    if fcu > 0 and bcu > 0:
        ratio = abs(fcu - bcu) / max(fcu, bcu)
        if ratio > 0.50:
            heavier = "F.Cu" if fcu > bcu else "B.Cu"
            flags.append(
                f"F.Cu vs B.Cu imbalance: {ratio*100:.0f}% difference "
                f"({heavier} is heavier)"
            )

    # Score: 20 if delta < 15%, scale down proportionally
    if fcu > 0 and bcu > 0:
        ratio = abs(fcu - bcu) / max(fcu, bcu)
        if ratio < 0.15:
            score = 20
        elif ratio < 0.50:
            # Linear scale from 20 to 10 between 15% and 50%
            score = int(20 - (ratio - 0.15) / 0.35 * 10)
        else:
            score = max(0, 10 - int((ratio - 0.50) * 20))
    else:
        score = 10  # Only one layer used

    return {
        "score": score,
        "total": total,
        "layers": layer_pct,
        "zones": dict(zone_layers),
        "flags": flags,
    }


# =====================================================================
#  Analysis 3: Thermal Via Analysis
# =====================================================================

def analyze_thermal_vias(data):
    """Check GND via density near power components."""
    # GND vias (net 1)
    gnd_vias = [v for v in data["vias"] if v["net"] == 1]

    results = {}
    flags = []

    for ref, info in POWER_COMPONENTS.items():
        cx, cy = info["x"], info["y"]
        nearby = 0
        for v in gnd_vias:
            dist = math.hypot(v["x"] - cx, v["y"] - cy)
            if dist <= 5.0:
                nearby += 1

        adequate = nearby >= 3
        results[ref] = {
            "name": info["name"],
            "power_w": info["power_w"],
            "vias_nearby": nearby,
            "adequate": adequate,
        }
        if not adequate:
            flags.append(
                f"{ref} ({info['name']}, {info['power_w']}W): "
                f"only {nearby} GND via(s) within 5mm (need >= 3)"
            )

    # Score: 20 if all adequate, -5 per uncapped IC, min 0
    uncapped = sum(1 for r in results.values() if not r["adequate"])
    score = max(0, 20 - 5 * uncapped)

    return {
        "score": score,
        "total_gnd_vias": len(gnd_vias),
        "components": results,
        "flags": flags,
    }


# =====================================================================
#  Analysis 4: Via Count per Net
# =====================================================================

def analyze_via_count(data):
    """Analyze via distribution across nets."""
    net_vias = defaultdict(int)
    for v in data["vias"]:
        net_vias[v["net"]] += 1

    total_vias = len(data["vias"])

    # Build summary sorted by count descending
    via_summary = []
    for net_id, count in sorted(net_vias.items(), key=lambda x: x[1], reverse=True):
        net_name = data["nets"].get(net_id, f"net_{net_id}")
        via_summary.append({
            "net_id": net_id,
            "name": net_name,
            "count": count,
        })

    # Flag nets with > 4 vias (excluding GND which naturally has many)
    flags = []
    excess_count = 0
    for vs in via_summary:
        if vs["net_id"] == 1:
            continue  # GND is expected to have many vias
        if vs["count"] > 4:
            flags.append(
                f"Net \"{vs['name']}\" has {vs['count']} vias (> 4, check if needed)"
            )
            excess_count += vs["count"] - 4

    # Score: 20 if max 4 vias/net (non-GND), -1 per excess via, min 0
    score = max(0, 20 - excess_count)

    return {
        "score": score,
        "total_vias": total_vias,
        "top_nets": via_summary[:10],
        "flags": flags,
    }


# =====================================================================
#  Analysis 5: Parallel Trace Detection (Crosstalk Risk)
# =====================================================================

def _is_horizontal(seg):
    """Check if segment is approximately horizontal."""
    return abs(seg["y2"] - seg["y1"]) < 0.01

def _is_vertical(seg):
    """Check if segment is approximately vertical."""
    return abs(seg["x2"] - seg["x1"]) < 0.01

def analyze_parallel_traces(data):
    """Detect parallel data traces that may cause crosstalk."""
    # Filter to data signal segments only
    data_segs = [s for s in data["segments"] if s["net"] in DATA_SIGNAL_NETS]

    # Group by layer
    by_layer = defaultdict(list)
    for seg in data_segs:
        by_layer[seg["layer"]].append(seg)

    crosstalk_pairs = []

    for layer, segs in by_layer.items():
        # Check horizontal pairs
        h_segs = [s for s in segs if _is_horizontal(s)]
        for i in range(len(h_segs)):
            for j in range(i + 1, len(h_segs)):
                s1, s2 = h_segs[i], h_segs[j]
                if s1["net"] == s2["net"]:
                    continue

                # Check if they overlap in X range
                x1_min, x1_max = min(s1["x1"], s1["x2"]), max(s1["x1"], s1["x2"])
                x2_min, x2_max = min(s2["x1"], s2["x2"]), max(s2["x1"], s2["x2"])
                overlap = min(x1_max, x2_max) - max(x1_min, x2_min)
                if overlap <= 0:
                    continue

                # Check Y gap
                gap = abs(s1["y1"] - s2["y1"])
                max_width = max(s1["width"], s2["width"])
                if gap < 3 * max_width:
                    net1 = data["nets"].get(s1["net"], f"net_{s1['net']}")
                    net2 = data["nets"].get(s2["net"], f"net_{s2['net']}")
                    crosstalk_pairs.append({
                        "net1": net1,
                        "net2": net2,
                        "layer": layer,
                        "gap_mm": gap,
                        "overlap_mm": overlap,
                        "direction": "horizontal",
                    })

        # Check vertical pairs
        v_segs = [s for s in segs if _is_vertical(s)]
        for i in range(len(v_segs)):
            for j in range(i + 1, len(v_segs)):
                s1, s2 = v_segs[i], v_segs[j]
                if s1["net"] == s2["net"]:
                    continue

                # Check if they overlap in Y range
                y1_min, y1_max = min(s1["y1"], s1["y2"]), max(s1["y1"], s1["y2"])
                y2_min, y2_max = min(s2["y1"], s2["y2"]), max(s2["y1"], s2["y2"])
                overlap = min(y1_max, y2_max) - max(y1_min, y2_min)
                if overlap <= 0:
                    continue

                # Check X gap
                gap = abs(s1["x1"] - s2["x1"])
                max_width = max(s1["width"], s2["width"])
                if gap < 3 * max_width:
                    net1 = data["nets"].get(s1["net"], f"net_{s1['net']}")
                    net2 = data["nets"].get(s2["net"], f"net_{s2['net']}")
                    crosstalk_pairs.append({
                        "net1": net1,
                        "net2": net2,
                        "layer": layer,
                        "gap_mm": gap,
                        "overlap_mm": overlap,
                        "direction": "vertical",
                    })

    # Deduplicate (same pair may appear multiple times)
    seen = set()
    unique_pairs = []
    for p in crosstalk_pairs:
        key = tuple(sorted([p["net1"], p["net2"]])) + (p["layer"],)
        if key not in seen:
            seen.add(key)
            unique_pairs.append(p)

    # Score: 20 if no risks, -3 per pair, min 0
    score = max(0, 20 - 3 * len(unique_pairs))

    return {
        "score": score,
        "data_segments": len(data_segs),
        "pairs": unique_pairs,
        "flags": [
            f"{p['net1']} || {p['net2']} on {p['layer']} "
            f"({p['direction']}, gap={p['gap_mm']:.2f}mm, "
            f"overlap={p['overlap_mm']:.1f}mm)"
            for p in unique_pairs
        ],
    }


# =====================================================================
#  Report Output
# =====================================================================

def print_header(filepath):
    """Print the report header."""
    print()
    print("=" * 65)
    print("  PCB LAYOUT OPTIMIZATION ANALYSIS")
    print(f"  File: {filepath}")
    print("=" * 65)
    print()


def print_section(number, title, score, max_score=20):
    """Print a section header with score."""
    label = f"{number}. {title}"
    score_str = f"[{score}/{max_score}]"
    padding = 65 - len(label) - len(score_str) - 3
    print(f"  {label}{'.' * max(1, padding)}{score_str}")


def print_trace_length_report(result):
    """Print trace length analysis results."""
    print_section(1, "TRACE LENGTH ANALYSIS", result["score"])
    print(f"     Total traces: {result['total_count']} segments, "
          f"{result['total_length']:.0f}mm total length")
    print()

    # Top nets table
    if result["top_nets"]:
        print("     Top nets by length:")
        print("     | {:12s} | {:>8s} | {:>12s} | {:>11s} | {:7s} |".format(
            "Net", "Segments", "Total Length", "Longest Seg", "Status"))
        print("     |{:s}|{:s}|{:s}|{:s}|{:s}|".format(
            "-" * 14, "-" * 10, "-" * 14, "-" * 13, "-" * 9))
        for ns in result["top_nets"][:5]:
            status = "WARN" if ns["total_length"] > 80 or ns["longest_seg"] > 40 else "OK"
            print("     | {:12s} | {:>8d} | {:>10.1f}mm | {:>9.1f}mm | {:7s} |".format(
                ns["name"][:12], ns["segments"],
                ns["total_length"], ns["longest_seg"], status))
        print()

    if result["flags"]:
        print(f"     Flags: {len(result['flags'])}")
        for f in result["flags"]:
            print(f"       - {f}")
    else:
        print("     No issues detected.")
    print()


def print_copper_balance_report(result):
    """Print copper balance analysis results."""
    print_section(2, "COPPER BALANCE", result["score"])
    print(f"     Total routed length: {result['total']:.0f}mm")
    print()

    print("     | {:8s} | {:>12s} | {:>6s} | {:20s} |".format(
        "Layer", "Trace Length", "Share", "Zone Fills"))
    print("     |{:s}|{:s}|{:s}|{:s}|".format(
        "-" * 10, "-" * 14, "-" * 8, "-" * 22))

    for layer in ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]:
        info = result["layers"].get(layer, {"length": 0.0, "pct": 0.0})
        zones = ", ".join(result.get("zones", {}).get(layer, ["-"]))
        if not zones:
            zones = "-"
        print("     | {:8s} | {:>10.1f}mm | {:>5.1f}% | {:20s} |".format(
            layer, info["length"], info["pct"], zones[:20]))
    print()

    if result["flags"]:
        for f in result["flags"]:
            print(f"     - {f}")
    else:
        print("     Balance is within acceptable range.")
    print()


def print_thermal_via_report(result):
    """Print thermal via analysis results."""
    print_section(3, "THERMAL VIA ANALYSIS", result["score"])
    print(f"     Total GND vias on board: {result['total_gnd_vias']}")
    print()

    print("     | {:4s} | {:10s} | {:>6s} | {:>10s} | {:>5s} | {:8s} |".format(
        "Ref", "Component", "Power", "GND Vias", "Req", "Status"))
    print("     |{:s}|{:s}|{:s}|{:s}|{:s}|{:s}|".format(
        "-" * 6, "-" * 12, "-" * 8, "-" * 12, "-" * 7, "-" * 10))

    for ref in sorted(result["components"].keys()):
        comp = result["components"][ref]
        status = "OK" if comp["adequate"] else "LOW"
        print("     | {:4s} | {:10s} | {:>5.1f}W | {:>10d} | {:>5s} | {:8s} |".format(
            ref, comp["name"], comp["power_w"],
            comp["vias_nearby"], ">=3", status))
    print()

    if result["flags"]:
        for f in result["flags"]:
            print(f"     - {f}")
    else:
        print("     All power components have adequate thermal vias.")
    print()


def print_via_count_report(result):
    """Print via count analysis results."""
    print_section(4, "VIA COUNT PER NET", result["score"])
    print(f"     Total vias: {result['total_vias']}")
    print()

    if result["top_nets"]:
        print("     Top nets by via count:")
        print("     | {:12s} | {:>5s} | {:8s} |".format("Net", "Vias", "Status"))
        print("     |{:s}|{:s}|{:s}|".format("-" * 14, "-" * 7, "-" * 10))
        for vs in result["top_nets"][:8]:
            is_gnd = vs["net_id"] == 1
            status = "OK (GND)" if is_gnd else ("WARN" if vs["count"] > 4 else "OK")
            print("     | {:12s} | {:>5d} | {:8s} |".format(
                vs["name"][:12], vs["count"], status))
        print()

    if result["flags"]:
        print(f"     Flags: {len(result['flags'])}")
        for f in result["flags"]:
            print(f"       - {f}")
    else:
        print("     Via distribution is optimal.")
    print()


def print_parallel_trace_report(result):
    """Print parallel trace analysis results."""
    print_section(5, "PARALLEL TRACE DETECTION (CROSSTALK)", result["score"])
    print(f"     Data signal segments analyzed: {result['data_segments']}")
    print()

    if result["pairs"]:
        print(f"     Crosstalk risk pairs: {len(result['pairs'])}")
        for f in result["flags"][:10]:
            print(f"       - {f}")
        if len(result["flags"]) > 10:
            print(f"       ... and {len(result['flags']) - 10} more")
    else:
        print("     No crosstalk risks detected.")
    print()


# =====================================================================
#  Main
# =====================================================================

def main():
    pcb_path = sys.argv[1] if len(sys.argv) > 1 else \
        "hardware/kicad/esp32-emu-turbo.kicad_pcb"

    if not Path(pcb_path).exists():
        print(f"ERROR: {pcb_path} not found")
        sys.exit(0)

    # Parse PCB
    data = parse_pcb(pcb_path)
    print_header(pcb_path)
    print(f"  Parsed: {len(data['segments'])} segments, "
          f"{len(data['vias'])} vias, "
          f"{len(data['nets'])} nets, "
          f"{len(data['zones'])} zones")
    print(f"  Board: {BOARD_W} x {BOARD_H} mm")
    print()

    # Run all analyses
    trace_result = analyze_trace_length(data)
    copper_result = analyze_copper_balance(data)
    thermal_result = analyze_thermal_vias(data)
    via_result = analyze_via_count(data)
    parallel_result = analyze_parallel_traces(data)

    # Print reports
    print("-" * 65)
    print()
    print_trace_length_report(trace_result)
    print_copper_balance_report(copper_result)
    print_thermal_via_report(thermal_result)
    print_via_count_report(via_result)
    print_parallel_trace_report(parallel_result)

    # Overall score
    total = (trace_result["score"] + copper_result["score"] +
             thermal_result["score"] + via_result["score"] +
             parallel_result["score"])

    print("=" * 65)
    print(f"  OVERALL SCORE: {total}/100")
    print()
    print("  Module Breakdown:")
    print(f"    1. Trace Length      : {trace_result['score']:>2d}/20")
    print(f"    2. Copper Balance    : {copper_result['score']:>2d}/20")
    print(f"    3. Thermal Vias      : {thermal_result['score']:>2d}/20")
    print(f"    4. Via Optimization  : {via_result['score']:>2d}/20")
    print(f"    5. Parallel Traces   : {parallel_result['score']:>2d}/20")
    print("=" * 65)
    print()

    # Advisory exit (always 0)
    sys.exit(0)


if __name__ == "__main__":
    main()
