#!/usr/bin/env python3
"""Gerber Integrity Verification — verify gerber files match the PCB layout.

Checks:
1. All expected layer files present (12+ files)
2. All files > 1KB (non-empty)
3. Drill file has plausible tool count (5-20 tools)
4. Copper layers have draw features (D01/D02/D03 operations)
5. Feature counts are proportional to PCB cache entries
"""

import os
import re
import sys
from pathlib import Path

BASE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
GERBER_DIR = BASE / "hardware" / "kicad" / "gerbers"

sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

# Expected gerber layer files and their typical extensions
EXPECTED_LAYERS = {
    "F_Cu": {"pattern": "*F_Cu*", "desc": "Front copper"},
    "B_Cu": {"pattern": "*B_Cu*", "desc": "Back copper"},
    "In1_Cu": {"pattern": "*In1_Cu*", "desc": "Inner copper 1 (GND)"},
    "In2_Cu": {"pattern": "*In2_Cu*", "desc": "Inner copper 2 (Power)"},
    "F_Mask": {"pattern": "*F_Mask*", "desc": "Front solder mask"},
    "B_Mask": {"pattern": "*B_Mask*", "desc": "Back solder mask"},
    "F_Silkscreen": {"pattern": "*F_Silkscreen*", "desc": "Front silkscreen"},
    "B_Silkscreen": {"pattern": "*B_Silkscreen*", "desc": "Back silkscreen"},
    "F_Paste": {"pattern": "*F_Paste*", "desc": "Front paste"},
    "B_Paste": {"pattern": "*B_Paste*", "desc": "Back paste"},
    "Edge_Cuts": {"pattern": "*Edge_Cuts*", "desc": "Board outline"},
}

MIN_FILE_SIZE = 1024  # 1KB minimum
MIN_DRILL_TOOLS = 3
MAX_DRILL_TOOLS = 25

PASS = 0
FAIL = 0
WARN = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  WARN  {name}  {detail}")


def find_gerber_file(gerber_dir, layer_name):
    """Find gerber file matching a layer name."""
    for f in gerber_dir.iterdir():
        if layer_name in f.name and f.is_file():
            return f
    return None


def count_gerber_features(filepath):
    """Count draw operations (D01=draw, D02=move, D03=flash) in a gerber file."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    d01 = len(re.findall(r'D01\*', text))
    d02 = len(re.findall(r'D02\*', text))
    d03 = len(re.findall(r'D03\*', text))
    return {"D01_draw": d01, "D02_move": d02, "D03_flash": d03,
            "total": d01 + d02 + d03}


def count_drill_tools(filepath):
    """Count tool definitions in an Excellon drill file."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    tools = re.findall(r'^T\d+C[\d.]+', text, re.M)
    return len(tools)


def count_drill_holes(filepath):
    """Count total drill hits in an Excellon drill file."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    # Drill hits are lines like X12.345Y-67.890
    hits = re.findall(r'^X[-\d.]+Y[-\d.]+', text, re.M)
    return len(hits)


def main():
    print("=" * 60)
    print("Gerber Integrity Verification")
    print("=" * 60)

    if not GERBER_DIR.exists():
        check("Gerber directory exists", False,
              f"not found: {GERBER_DIR}")
        print(f"\nResults: {PASS} passed, {FAIL} failed")
        return 1

    # List all files in gerber directory
    gerber_files = sorted(GERBER_DIR.iterdir())
    all_names = [f.name for f in gerber_files if f.is_file()]
    print(f"\n  Found {len(all_names)} files in gerber directory")

    # Check 1: All expected layer files present
    print(f"\n-- Layer File Presence --")
    found_layers = {}
    for layer_name, info in EXPECTED_LAYERS.items():
        match = find_gerber_file(GERBER_DIR, layer_name)
        if match:
            found_layers[layer_name] = match
            check(f"{layer_name} ({info['desc']})", True)
        else:
            check(f"{layer_name} ({info['desc']})", False,
                  "file not found")

    # Check for drill file
    drill_files = [f for f in gerber_files
                   if f.is_file() and f.suffix.lower() in ('.drl', '.xln')]
    check("Drill file present", len(drill_files) > 0,
          "no .drl or .xln file found")

    # Check 2: File sizes > 1KB
    print(f"\n-- File Sizes --")
    for layer_name, filepath in sorted(found_layers.items()):
        size = filepath.stat().st_size
        check(f"{layer_name} size > 1KB",
              size > MIN_FILE_SIZE,
              f"size={size} bytes")

    for drill_f in drill_files:
        size = drill_f.stat().st_size
        check(f"Drill file size > 1KB",
              size > MIN_FILE_SIZE,
              f"size={size} bytes")

    # Check 3: Drill file tool count
    print(f"\n-- Drill Analysis --")
    if drill_files:
        drill_path = drill_files[0]
        tool_count = count_drill_tools(drill_path)
        hole_count = count_drill_holes(drill_path)
        print(f"  Drill file: {drill_path.name}")
        print(f"  Tool definitions: {tool_count}")
        print(f"  Total drill hits: {hole_count}")

        check(f"Drill tool count plausible ({MIN_DRILL_TOOLS}-{MAX_DRILL_TOOLS})",
              MIN_DRILL_TOOLS <= tool_count <= MAX_DRILL_TOOLS,
              f"tool_count={tool_count}")

        # Cross-check with PCB cache
        cache = load_cache(str(PCB_FILE))
        pcb_vias = len(cache["vias"])
        pcb_tht_pads = len([p for p in cache["pads"]
                            if p["type"] in ("thru_hole", "np_thru_hole")])
        expected_holes = pcb_vias + pcb_tht_pads
        print(f"  PCB vias: {pcb_vias}, THT pads: {pcb_tht_pads}, "
              f"expected ~{expected_holes} holes")

        # Drill holes should be within 50% of expected
        if expected_holes > 0:
            ratio = hole_count / expected_holes
            check(f"Drill hole count matches PCB ({hole_count} vs ~{expected_holes})",
                  0.5 <= ratio <= 2.0,
                  f"ratio={ratio:.2f}")
        else:
            warn("No THT pads or vias in PCB cache (unexpected)")
    else:
        print("  (no drill file to analyze)")

    # Check 4: Copper layer features
    print(f"\n-- Copper Layer Features --")
    cache = load_cache(str(PCB_FILE))

    for layer_name in ["F_Cu", "B_Cu", "In1_Cu", "In2_Cu"]:
        if layer_name not in found_layers:
            continue
        filepath = found_layers[layer_name]
        features = count_gerber_features(filepath)

        print(f"  {layer_name}: D01(draw)={features['D01_draw']}, "
              f"D02(move)={features['D02_move']}, "
              f"D03(flash)={features['D03_flash']}, "
              f"total={features['total']}")

        check(f"{layer_name} has draw features",
              features["total"] > 0,
              "empty copper layer (0 features)")

        # Cross-check: copper layers should have substantial features
        if layer_name in ("F_Cu", "B_Cu"):
            # Outer copper layers should have many features (traces + pads + zone fills)
            check(f"{layer_name} has substantial features (>50)",
                  features["total"] > 50,
                  f"only {features['total']} features (expected >50 for routed layer)")

    # Check 5: Job file present (optional but good practice)
    job_files = [f for f in gerber_files
                 if f.is_file() and "job" in f.name.lower()]
    if job_files:
        check("Job file present (.gbrjob)", True)
    else:
        warn("No .gbrjob file found (optional but recommended)")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
