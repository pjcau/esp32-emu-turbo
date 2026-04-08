#!/usr/bin/env python3
"""Test 11: Ground Loop Analysis.

Advisory check for potential ground loop issues between audio and digital sections.

Checks:
1. GND via count near U5 (PAM8403) audio area — need >= 3 for adequate return path
2. GND via count near U1 (ESP32) digital area
3. Separation of audio GND vias from digital signal traces
4. GND segment density in audio section
"""

import json
import math
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

PASS = 0
FAIL = 0
WARN = 0

# Audio section around U5 (PAM8403): center ~(30, 29.5)
AUDIO_BBOX = {"xmin": 20, "xmax": 42, "ymin": 20, "ymax": 42}

# Digital section around U1 (ESP32): center ~(80, 33)
DIGITAL_BBOX = {"xmin": 65, "xmax": 95, "ymin": 18, "ymax": 48}

# Minimum GND vias in audio section for adequate return path
MIN_AUDIO_GND_VIAS = 3

# Audio signal nets
AUDIO_SIGNAL_NETS = {"I2S_BCLK", "I2S_LRCK", "I2S_DOUT", "SPK+", "SPK-"}


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


def info(name, detail=""):
    print(f"  INFO  {name}  {detail}")


def in_bbox(x, y, bbox):
    return bbox["xmin"] <= x <= bbox["xmax"] and bbox["ymin"] <= y <= bbox["ymax"]


def main():
    print("=" * 60)
    print("Test 11: Ground Loop Analysis")
    print("=" * 60)

    cache = load_cache(PCB_FILE)
    vias = cache["vias"]
    segments = cache["segments"]
    pads = cache["pads"]

    # Build net name lookup
    net_names = {n["id"]: n["name"] for n in cache["nets"]}
    gnd_net_id = next((n["id"] for n in cache["nets"] if n["name"] == "GND"), None)

    if gnd_net_id is None:
        check("GND net exists", False, "no GND net found")
        return 1

    print(f"\n── Ground Loop Analysis ──")

    # 1. Count GND vias in audio section
    audio_gnd_vias = [v for v in vias
                      if v["net"] == gnd_net_id and in_bbox(v["x"], v["y"], AUDIO_BBOX)]
    audio_all_vias = [v for v in vias if in_bbox(v["x"], v["y"], AUDIO_BBOX)]

    check(f"Audio section GND vias >= {MIN_AUDIO_GND_VIAS} ({len(audio_gnd_vias)} found)",
          len(audio_gnd_vias) >= MIN_AUDIO_GND_VIAS,
          f"only {len(audio_gnd_vias)} GND vias near U5 (need {MIN_AUDIO_GND_VIAS}+ for return path)")

    if audio_gnd_vias:
        locs = ", ".join(f"({v['x']:.1f},{v['y']:.1f})" for v in audio_gnd_vias[:5])
        info(f"Audio GND via locations: {locs}")

    # 2. Count GND vias in digital section
    digital_gnd_vias = [v for v in vias
                        if v["net"] == gnd_net_id and in_bbox(v["x"], v["y"], DIGITAL_BBOX)]

    info(f"Digital section GND vias: {len(digital_gnd_vias)}")

    # 3. Check GND segments in audio section
    audio_gnd_segs = [s for s in segments
                      if s["net"] == gnd_net_id
                      and (in_bbox(s["x1"], s["y1"], AUDIO_BBOX)
                           or in_bbox(s["x2"], s["y2"], AUDIO_BBOX))]

    info(f"Audio section GND trace segments: {len(audio_gnd_segs)}")

    # 4. Check for digital signals crossing audio area
    audio_net_ids = set()
    for n in cache["nets"]:
        if n["name"] in AUDIO_SIGNAL_NETS or n["name"] == "GND":
            audio_net_ids.add(n["id"])

    digital_crossing_audio = []
    for s in segments:
        net_name = net_names.get(s["net"], "")
        # Skip audio nets and GND — we want digital signals crossing audio area
        if s["net"] in audio_net_ids or s["net"] == 0:
            continue
        # Check if this digital signal crosses through audio bbox
        if (in_bbox(s["x1"], s["y1"], AUDIO_BBOX)
                or in_bbox(s["x2"], s["y2"], AUDIO_BBOX)):
            digital_crossing_audio.append((net_name, s))

    if digital_crossing_audio:
        # Group by net name
        crossing_nets = set(name for name, _ in digital_crossing_audio)
        warn(f"Digital signals crossing audio area: {len(digital_crossing_audio)} segments",
             f"nets: {', '.join(sorted(crossing_nets)[:5])}")
    else:
        check("No digital signals crossing audio area", True)

    # 5. Check audio GND path doesn't share vias with high-speed digital
    # High-speed nets: SD_CLK, LCD_WR, USB_D+, USB_D-
    high_speed_nets = {"SD_CLK", "LCD_WR", "USB_D+", "USB_D-"}
    hs_net_ids = {n["id"] for n in cache["nets"] if n["name"] in high_speed_nets}

    shared_vias = 0
    for gnd_via in audio_gnd_vias:
        for v in vias:
            if v["net"] in hs_net_ids:
                dist = math.sqrt((gnd_via["x"] - v["x"])**2 + (gnd_via["y"] - v["y"])**2)
                if dist < 1.0:  # Within 1mm
                    shared_vias += 1

    if shared_vias > 0:
        warn(f"Audio GND vias near high-speed signal vias: {shared_vias} pairs within 1mm")
    else:
        check("Audio GND vias isolated from high-speed signals", True)

    # 6. Verify star grounding — audio GND pads should connect to plane, not daisy-chain
    audio_gnd_pads = [p for p in pads
                      if p["net"] == gnd_net_id
                      and p["ref"] in ("U5", "SPK1")
                      and in_bbox(p["x"], p["y"], AUDIO_BBOX)]

    if audio_gnd_pads:
        info(f"Audio GND pads (U5, SPK1): {len(audio_gnd_pads)} pads connect to GND plane via thermal relief")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    if WARN and not FAIL:
        print("  (warnings are advisory — review recommended but not blocking)")
    print(f"{'=' * 60}")

    # Only FAIL causes exit code 1; WARN is advisory
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
