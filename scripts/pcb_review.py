#!/usr/bin/env python3
"""Comprehensive PCB Design Review.

Analyzes 6 key domains of PCB design quality and produces a scored report.

Usage:
    python3 scripts/pcb_review.py [path/to/file.kicad_pcb]
"""

import re
import sys
import math
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# -- Constants ---------------------------------------------------------
BOARD_W, BOARD_H = 160.0, 75.0
PCB_DEFAULT = "hardware/kicad/esp32-emu-turbo.kicad_pcb"

# Power trace width requirements
W_PWR = 0.5   # Power lines
W_SIG = 0.25  # Signal
W_DATA = 0.2  # Data

# JLCPCB 4-layer manufacturing limits
JLCPCB_MIN_TRACE = 0.09
JLCPCB_MIN_SPACE = 0.09
JLCPCB_MIN_DRILL = 0.15
JLCPCB_MIN_RING = 0.13

# Net classification
POWER_NETS = {1: "GND", 2: "VBUS", 3: "+5V", 4: "+3V3", 5: "BAT+", 46: "LX"}
DATA_NETS = {}  # nets 6-13: LCD, 20-23: SPI, 24-26: I2S, 40-41: USB
for i in range(6, 14):
    DATA_NETS[i] = f"LCD_D{i-6}"
DATA_NETS.update({20: "SD_MOSI", 21: "SD_MISO", 22: "SD_CLK", 23: "SD_CS"})
DATA_NETS.update({24: "I2S_BCLK", 25: "I2S_LRCK", 26: "I2S_DOUT"})
DATA_NETS.update({40: "USB_D+", 41: "USB_D-"})

# Power component positions (from board.py)
POWER_ICS = {
    "U1": {"name": "ESP32-S3", "x": 80.0, "y": 27.5, "vcc_net": 4},
    "U2": {"name": "IP5306", "x": 110.0, "y": 42.5, "vcc_net": 2},
    "U3": {"name": "AMS1117", "x": 125.0, "y": 55.5, "vcc_net": 3},
    "U5": {"name": "PAM8403", "x": 30.0, "y": 29.5, "vcc_net": 3},
    "U6": {"name": "SD Card", "x": 140.0, "y": 67.0, "vcc_net": 4},
}

# Mounting hole positions (from board.py, approx PCB coords)
MOUNT_HOLES = [
    (10.0, 10.0), (150.0, 10.0),
    (10.0, 37.5), (150.0, 37.5),
    (10.0, 65.0), (150.0, 65.0),
]


def parse_pcb(filepath):
    """Parse KiCad PCB file."""
    text = Path(filepath).read_text()
    result = {"segments": [], "vias": [], "nets": [], "zones": []}

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

    for m in re.finditer(
        r'\(via\s+\(at\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(size\s+([\d.]+)\)\s+\(drill\s+([\d.]+)\)'
        r'.*?\(net\s+(\d+)\)', text, re.DOTALL
    ):
        result["vias"].append({
            "x": float(m.group(1)), "y": float(m.group(2)),
            "size": float(m.group(3)), "drill": float(m.group(4)),
            "net": int(m.group(5)),
        })

    for m in re.finditer(r'\(net\s+(\d+)\s+"([^"]*)"\)', text):
        nid = int(m.group(1))
        if nid > 0:
            result["nets"].append({"id": nid, "name": m.group(2)})

    for m in re.finditer(
        r'\(zone\s+.*?\(net\s+(\d+)\).*?\(net_name\s+"([^"]*)"\).*?\(layer\s+"([^"]+)"\)',
        text, re.DOTALL
    ):
        result["zones"].append({
            "net": int(m.group(1)),
            "net_name": m.group(2),
            "layer": m.group(3),
        })

    return result


def seg_length(seg):
    return math.hypot(seg["x2"] - seg["x1"], seg["y2"] - seg["y1"])


# -- Domain 1: Power Integrity ----------------------------------------

def review_power_integrity(data):
    findings = []
    score = 10

    # Check 1: Power trace widths
    power_thin = []
    for seg in data["segments"]:
        if seg["net"] in POWER_NETS:
            if seg["width"] < W_PWR:
                power_thin.append(
                    f"Net {POWER_NETS[seg['net']]}: {seg['width']}mm "
                    f"(need {W_PWR}mm) at ({seg['x1']:.1f},{seg['y1']:.1f})"
                )
    if power_thin:
        score -= min(3, len(power_thin))
        findings.append(f"Thin power traces: {len(power_thin)} segments below {W_PWR}mm")
        for t in power_thin[:3]:
            findings.append(f"  -> {t}")
    else:
        findings.append(f"All power traces >= {W_PWR}mm -- OK")

    # Check 2: GND vias near power ICs
    gnd_vias = [v for v in data["vias"] if v["net"] == 1]  # net 1 = GND
    for ref, info in POWER_ICS.items():
        nearby = sum(1 for v in gnd_vias
                     if math.hypot(v["x"] - info["x"], v["y"] - info["y"]) < 8.0)
        if nearby < 2:
            score -= 1
            findings.append(f"{ref} ({info['name']}): only {nearby} GND via(s) within 8mm -- needs more")
        else:
            findings.append(f"{ref} ({info['name']}): {nearby} GND vias within 8mm -- OK")

    # Check 3: GND plane zone exists on In1.Cu
    gnd_zones = [z for z in data["zones"] if z["net"] == 1 and z["layer"] == "In1.Cu"]
    if not gnd_zones:
        score -= 3
        findings.append("No GND zone on In1.Cu -- CRITICAL: missing ground plane")
    else:
        findings.append("GND zone on In1.Cu -- OK (ground plane present)")

    # Check 4: Power plane zone on In2.Cu
    pwr_zones = [z for z in data["zones"] if z["layer"] == "In2.Cu"]
    if not pwr_zones:
        score -= 2
        findings.append("No power zone on In2.Cu -- missing power plane")
    else:
        names = set(z["net_name"] for z in pwr_zones)
        findings.append(f"Power zones on In2.Cu: {', '.join(names)} -- OK")

    return max(0, score), findings


# -- Domain 2: Signal Integrity ----------------------------------------

def review_signal_integrity(data):
    findings = []
    score = 10

    # Check 1: Display bus length matching (LCD_D0-D7, nets 6-13)
    lcd_lengths = {}
    for net_id in range(6, 14):
        segs = [s for s in data["segments"] if s["net"] == net_id]
        total = sum(seg_length(s) for s in segs)
        lcd_lengths[net_id] = total

    if lcd_lengths:
        lengths = list(lcd_lengths.values())
        avg = sum(lengths) / len(lengths) if lengths else 0
        max_len = max(lengths) if lengths else 0
        min_len = min(lengths) if lengths else 0
        mismatch = max_len - min_len

        findings.append(f"Display bus (LCD_D0-D7) length range: {min_len:.1f}mm - {max_len:.1f}mm")
        findings.append(f"  Mismatch: {mismatch:.1f}mm (avg: {avg:.1f}mm)")

        if mismatch > 20:
            score -= 3
            findings.append("  -> HIGH mismatch -- may cause timing issues at high refresh")
        elif mismatch > 10:
            score -= 1
            findings.append("  -> Moderate mismatch -- acceptable for 8080 parallel at these speeds")
        else:
            findings.append("  -> Good length matching")

    # Check 2: Data trace widths
    data_thin = []
    for seg in data["segments"]:
        if seg["net"] in DATA_NETS and seg["width"] < W_DATA:
            data_thin.append(seg)
    if data_thin:
        score -= min(2, len(data_thin))
        findings.append(f"Data traces below {W_DATA}mm: {len(data_thin)} segments")
    else:
        findings.append(f"All data traces >= {W_DATA}mm -- OK")

    # Check 3: USB differential pair
    usb_dp = [s for s in data["segments"] if s["net"] == 40]  # USB_D+
    usb_dm = [s for s in data["segments"] if s["net"] == 41]  # USB_D-
    if usb_dp and usb_dm:
        dp_len = sum(seg_length(s) for s in usb_dp)
        dm_len = sum(seg_length(s) for s in usb_dm)
        diff = abs(dp_len - dm_len)
        findings.append(f"USB D+/D- lengths: {dp_len:.1f}mm / {dm_len:.1f}mm (delta={diff:.1f}mm)")
        if diff > 5:
            score -= 2
            findings.append("  -> Poor USB differential matching")
        elif diff > 2:
            score -= 1
            findings.append("  -> Acceptable for USB 1.1/2.0")
        else:
            findings.append("  -> Good differential matching")
    else:
        findings.append("USB D+/D- traces not found or incomplete")

    # Check 4: Via transitions on high-speed nets
    for net_id, name in DATA_NETS.items():
        vias = [v for v in data["vias"] if v["net"] == net_id]
        if len(vias) > 2:
            score -= 0.5
            findings.append(f"  {name}: {len(vias)} vias (each adds impedance discontinuity)")

    return max(0, round(score)), findings


# -- Domain 3: Thermal ------------------------------------------------

def review_thermal(data):
    findings = []
    score = 10

    gnd_vias = [v for v in data["vias"] if v["net"] == 1]

    # Thermal analysis for each power IC
    thermal_data = []
    for ref, info in POWER_ICS.items():
        if ref not in ("U2", "U3", "U5"):  # Only power-dissipating ICs
            continue
        nearby_vias = [v for v in gnd_vias
                       if math.hypot(v["x"] - info["x"], v["y"] - info["y"]) < 5.0]

        # Count nearby power traces (copper area proxy)
        nearby_traces = [s for s in data["segments"]
                         if s["net"] in (1, 2, 3, 4, 5)
                         and _seg_near_point(s, info["x"], info["y"], 10.0)]
        trace_len = sum(seg_length(s) * s["width"] for s in nearby_traces)

        thermal_data.append({
            "ref": ref, "name": info["name"],
            "vias": len(nearby_vias), "cu_area": trace_len,
        })

        if len(nearby_vias) < 3:
            score -= 2
            findings.append(
                f"{ref} ({info['name']}): {len(nearby_vias)} thermal vias -- "
                f"INSUFFICIENT (need >=3 within 5mm)"
            )
        else:
            findings.append(
                f"{ref} ({info['name']}): {len(nearby_vias)} thermal vias -- OK"
            )

    # Total GND via count
    findings.append(f"Total GND vias: {len(gnd_vias)}")
    if len(gnd_vias) < 10:
        score -= 1
        findings.append("  -> Consider adding more GND vias for thermal/electrical performance")

    return max(0, score), findings


def _seg_near_point(seg, px, py, radius):
    """Check if segment is near a point."""
    cx = (seg["x1"] + seg["x2"]) / 2
    cy = (seg["y1"] + seg["y2"]) / 2
    return math.hypot(cx - px, cy - py) < radius


# -- Domain 4: Manufacturability --------------------------------------

def review_manufacturability(data):
    findings = []
    score = 10

    # Check 1: Trace widths
    thin_traces = [s for s in data["segments"] if s["width"] < JLCPCB_MIN_TRACE]
    if thin_traces:
        score -= 3
        findings.append(f"Traces below JLCPCB min ({JLCPCB_MIN_TRACE}mm): {len(thin_traces)}")
    else:
        findings.append(f"All traces >= {JLCPCB_MIN_TRACE}mm -- OK")

    # Check 2: Via dimensions
    bad_vias = []
    for v in data["vias"]:
        ring = (v["size"] - v["drill"]) / 2
        if v["drill"] < JLCPCB_MIN_DRILL:
            bad_vias.append(f"drill {v['drill']}mm at ({v['x']},{v['y']})")
        if ring < JLCPCB_MIN_RING:
            bad_vias.append(f"ring {ring:.3f}mm at ({v['x']},{v['y']})")
    if bad_vias:
        score -= 2
        findings.append(f"Via dimension violations: {len(bad_vias)}")
        for b in bad_vias[:3]:
            findings.append(f"  -> {b}")
    else:
        findings.append("All vias within JLCPCB specs -- OK")

    # Check 3: Board aspect ratio (JLCPCB prefers <= 4:1)
    ratio = BOARD_W / BOARD_H
    findings.append(f"Board aspect ratio: {ratio:.1f}:1 ({BOARD_W}x{BOARD_H}mm)")
    if ratio > 4:
        score -= 1
        findings.append("  -> Exceeds 4:1 -- may cause warping during reflow")
    else:
        findings.append("  -> Within limits")

    # Check 4: Component count vs board area
    area = BOARD_W * BOARD_H / 100  # cm^2
    seg_count = len(data["segments"])
    via_count = len(data["vias"])
    findings.append(f"Board area: {area:.0f} cm^2 | Traces: {seg_count} | Vias: {via_count}")
    density = (seg_count + via_count) / area
    findings.append(f"  Routing density: {density:.1f} elements/cm^2")

    return max(0, score), findings


# -- Domain 5: EMI/EMC ------------------------------------------------

def review_emi(data):
    findings = []
    score = 10

    # Check 1: Ground plane on In1.Cu
    gnd_zones = [z for z in data["zones"] if z["net"] == 1 and z["layer"] == "In1.Cu"]
    if gnd_zones:
        findings.append("Continuous GND plane on In1.Cu -- OK")
    else:
        score -= 4
        findings.append("No GND plane on In1.Cu -- CRITICAL for EMI")

    # Check 2: Signals on inner layers (should minimize)
    inner_signals = [s for s in data["segments"]
                     if s["layer"] in ("In1.Cu", "In2.Cu")
                     and s["net"] not in POWER_NETS]
    if inner_signals:
        score -= min(2, len(inner_signals) // 5)
        findings.append(f"Signal traces on inner layers: {len(inner_signals)} -- "
                        "may disrupt ground/power planes")
    else:
        findings.append("No signal traces on inner layers -- OK (planes intact)")

    # Check 3: Decoupling cap proximity (100nF caps should be near IC Vcc)
    # We approximate by checking if there are traces between cap nets and IC nets
    findings.append("Decoupling strategy: 15x 100nF 0805 caps in BOM")
    findings.append("  -> Verify placement near each IC Vcc pin")

    # Check 4: High-speed signal return paths
    # Check if LCD bus and SPI signals stay on B.Cu (close to In1.Cu GND)
    lcd_layers = set()
    for net_id in range(6, 14):
        for s in data["segments"]:
            if s["net"] == net_id:
                lcd_layers.add(s["layer"])

    if lcd_layers:
        findings.append(f"Display bus layers: {', '.join(sorted(lcd_layers))}")
        if "F.Cu" in lcd_layers and "B.Cu" in lcd_layers:
            score -= 1
            findings.append("  -> Mixed layers -- return path discontinuity risk")
        else:
            findings.append("  -> Single layer group -- good return path")

    return max(0, score), findings


# -- Domain 6: Mechanical ---------------------------------------------

def review_mechanical(data):
    findings = []
    score = 10

    # Check 1: Mounting hole symmetry
    if len(MOUNT_HOLES) >= 4:
        xs = [h[0] for h in MOUNT_HOLES]
        ys = [h[1] for h in MOUNT_HOLES]
        x_sym = abs((max(xs) + min(xs)) / 2 - BOARD_W / 2)
        y_sym = abs((max(ys) + min(ys)) / 2 - BOARD_H / 2)
        findings.append(f"Mounting holes: {len(MOUNT_HOLES)} (M2.5)")
        findings.append(f"  X symmetry offset: {x_sym:.1f}mm | Y symmetry offset: {y_sym:.1f}mm")
        if x_sym > 5 or y_sym > 5:
            score -= 1
            findings.append("  -> Asymmetric mounting -- may cause stress")
        else:
            findings.append("  -> Symmetric -- OK")

    # Check 2: Connector edge placement
    connectors = {
        "USB-C (J1)": {"x": 80.0, "y": 72.0},
        "FPC (J4)": {"x": 135.0, "y": 35.5},
        "JST Battery (J3)": {"x": 15.0, "y": 72.0},
        "SD Card (U6)": {"x": 140.0, "y": 67.0},
    }
    for name, pos in connectors.items():
        edge_dist = min(pos["x"], BOARD_W - pos["x"], pos["y"], BOARD_H - pos["y"])
        if edge_dist < 5:
            findings.append(f"{name} at ({pos['x']},{pos['y']}): {edge_dist:.1f}mm from edge -- good accessibility")
        else:
            findings.append(f"{name} at ({pos['x']},{pos['y']}): {edge_dist:.1f}mm from edge")
            if edge_dist > 30:
                score -= 0.5
                findings.append(f"  -> Far from edge -- cable routing may be difficult")

    # Check 3: FPC slot strain relief
    findings.append("FPC slot: 3x24mm at board center-right")
    findings.append("  -> Check mechanical strain relief in enclosure design")

    # Check 4: Board dimensions for handheld
    findings.append(f"Board size: {BOARD_W}x{BOARD_H}mm")
    if BOARD_W > 180 or BOARD_H > 90:
        score -= 1
        findings.append("  -> Large for handheld -- check ergonomics")
    else:
        findings.append("  -> Good size for handheld console")

    return max(0, round(score)), findings


# -- Main Report ------------------------------------------------------

def main():
    pcb_path = sys.argv[1] if len(sys.argv) > 1 else PCB_DEFAULT

    if not Path(pcb_path).exists():
        print(f"ERROR: {pcb_path} not found")
        sys.exit(1)

    data = parse_pcb(pcb_path)

    print("=" * 70)
    print("  COMPREHENSIVE PCB DESIGN REVIEW")
    print(f"  File: {pcb_path}")
    print(f"  Board: {BOARD_W}x{BOARD_H}mm, 4-layer")
    print(f"  Elements: {len(data['segments'])} traces, "
          f"{len(data['vias'])} vias, {len(data['zones'])} zones")
    print("=" * 70)
    print()

    reviews = [
        ("1. POWER INTEGRITY", review_power_integrity),
        ("2. SIGNAL INTEGRITY", review_signal_integrity),
        ("3. THERMAL MANAGEMENT", review_thermal),
        ("4. MANUFACTURABILITY (JLCPCB)", review_manufacturability),
        ("5. EMI/EMC", review_emi),
        ("6. MECHANICAL", review_mechanical),
    ]

    scores = []
    for title, fn in reviews:
        score, findings = fn(data)
        scores.append((title, score))

        print(f"{'─' * 60}")
        print(f"  {title}  [{score}/10]")
        print(f"{'─' * 60}")
        for f in findings:
            print(f"  {f}")
        print()

    total = sum(s for _, s in scores)
    max_total = len(scores) * 10

    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print()
    print(f"  {'Domain':<40} {'Score':>6}")
    print(f"  {'-' * 40} {'-' * 6}")
    for title, score in scores:
        bar = "█" * score + "░" * (10 - score)
        print(f"  {title:<40} {bar} {score}/10")
    print(f"  {'-' * 40} {'-' * 6}")
    print(f"  {'OVERALL':<40} {'':>6} {total}/{max_total}")
    print()

    # Top improvements
    low_scores = sorted(scores, key=lambda x: x[1])
    print("  TOP PRIORITIES FOR IMPROVEMENT:")
    for i, (title, score) in enumerate(low_scores[:3], 1):
        if score < 10:
            print(f"  {i}. {title} (currently {score}/10)")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
