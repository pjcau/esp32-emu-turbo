#!/usr/bin/env python3
"""USB D+/D- Impedance Verification from JLCPCB 4-layer stackup parameters.

Computes actual single-ended and differential impedance for USB traces
and verifies they're within tolerance for USB Full Speed (12 Mbps).

JLCPCB JLC04161H-7628 stackup:
  F.Cu:    35um (1oz)
  Prepreg: h=0.2104mm, Er=4.6
  In1.Cu:  17.5um (0.5oz)
  Core:    1.065mm, Er=4.6
  In2.Cu:  17.5um (0.5oz)
  Prepreg: h=0.2104mm, Er=4.6
  B.Cu:    35um (1oz)

USB Full Speed target: 90 ohm +/-10% differential (81-99 ohm).
ESP32-S3 USB FS at 12 Mbps is forgiving:
  WARN if outside 60-120 ohm, FAIL if outside 40-150 ohm.
"""

import math
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

# JLCPCB JLC04161H-7628 stackup parameters
STACKUP = {
    "F.Cu": {"t": 0.035, "h_to_ref": 0.2104, "ref_plane": "In1.Cu"},
    "B.Cu": {"t": 0.035, "h_to_ref": 0.2104, "ref_plane": "In2.Cu"},
    "In1.Cu": {"t": 0.0175, "h_to_ref": 0.2104, "ref_plane": "F.Cu"},
    "In2.Cu": {"t": 0.0175, "h_to_ref": 0.2104, "ref_plane": "B.Cu"},
}
ER = 4.6  # Prepreg dielectric constant

# USB FS impedance thresholds
Z0_PASS_RANGE = (30, 70)          # Single-ended reasonable range
ZDIFF_STRICT = (81, 99)           # USB spec nominal
ZDIFF_FORGIVING = (60, 120)       # USB FS forgiving range
ZDIFF_FAIL = (40, 150)            # Absolute fail limits

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


def info(name, detail=""):
    print(f"  INFO  {name}  {detail}")


def microstrip_z0(w, t, h, er):
    """Compute microstrip impedance using IPC-2141 approximation.

    Z0 = (87 / sqrt(Er + 1.41)) * ln(5.98 * h / (0.8 * w + t))

    Args:
        w: trace width (mm)
        t: copper thickness (mm)
        h: dielectric height to reference plane (mm)
        er: relative permittivity
    Returns:
        impedance in ohms, or None if geometry is invalid
    """
    denom = 0.8 * w + t
    if denom <= 0 or h <= 0:
        return None
    arg = 5.98 * h / denom
    if arg <= 1.0:
        # ln argument must be > 1 for valid impedance
        return None
    return (87.0 / math.sqrt(er + 1.41)) * math.log(arg)


def differential_impedance(z0, s, h):
    """Compute edge-coupled differential impedance.

    Zdiff = 2 * Z0 * (1 - 0.48 * exp(-0.96 * s / h))

    Args:
        z0: single-ended impedance (ohms)
        s: edge-to-edge spacing (mm)
        h: dielectric height (mm)
    Returns:
        differential impedance in ohms
    """
    return 2.0 * z0 * (1.0 - 0.48 * math.exp(-0.96 * s / h))


def segment_length(seg):
    dx = seg["x2"] - seg["x1"]
    dy = seg["y2"] - seg["y1"]
    return math.sqrt(dx * dx + dy * dy)


def find_parallel_segments(segs_dp, segs_dm, tolerance=0.5):
    """Find D+/D- segment pairs running in parallel.

    Returns list of (dp_seg, dm_seg, spacing_mm).
    Parallel means: similar direction, overlapping extent, close spacing.
    """
    pairs = []

    for sp in segs_dp:
        sp_dx = sp["x2"] - sp["x1"]
        sp_dy = sp["y2"] - sp["y1"]
        sp_len = math.sqrt(sp_dx**2 + sp_dy**2)
        if sp_len < 0.1:
            continue

        for sm in segs_dm:
            sm_dx = sm["x2"] - sm["x1"]
            sm_dy = sm["y2"] - sm["y1"]
            sm_len = math.sqrt(sm_dx**2 + sm_dy**2)
            if sm_len < 0.1:
                continue

            # Check if segments are roughly parallel (dot product of unit vectors)
            dot = (sp_dx * sm_dx + sp_dy * sm_dy) / (sp_len * sm_len)
            if abs(dot) < 0.9:
                continue

            # Compute perpendicular distance between segment midpoints
            sp_mx = (sp["x1"] + sp["x2"]) / 2
            sp_my = (sp["y1"] + sp["y2"]) / 2
            sm_mx = (sm["x1"] + sm["x2"]) / 2
            sm_my = (sm["y1"] + sm["y2"]) / 2

            mid_dist = math.sqrt((sp_mx - sm_mx)**2 + (sp_my - sm_my)**2)

            # Parallel segments should be close (within ~2mm for USB)
            if mid_dist < 2.0:
                # Edge-to-edge spacing = center distance - half widths
                edge_spacing = mid_dist - sp.get("width", 0.2) / 2 - sm.get("width", 0.2) / 2
                if edge_spacing > 0:
                    pairs.append((sp, sm, edge_spacing))

    return pairs


def main():
    print("=" * 60)
    print("USB D+/D- Impedance Verification (JLCPCB Stackup)")
    print("=" * 60)

    cache = load_cache(PCB_FILE)
    nets = {n["id"]: n["name"] for n in cache["nets"]}
    net_ids = {n["name"]: n["id"] for n in cache["nets"]}

    # Find USB net IDs
    dp_id = net_ids.get("USB_D+")
    dm_id = net_ids.get("USB_D-")

    if dp_id is None or dm_id is None:
        check("USB_D+/USB_D- nets found", False,
              f"USB_D+={'found' if dp_id else 'missing'}, "
              f"USB_D-={'found' if dm_id else 'missing'}")
        print(f"\nResults: {PASS} passed, {FAIL} failed")
        return 1

    check("USB_D+/USB_D- nets found", True)

    # Get all segments for USB nets
    dp_segs = [s for s in cache["segments"] if s["net"] == dp_id]
    dm_segs = [s for s in cache["segments"] if s["net"] == dm_id]

    info(f"USB_D+ segments: {len(dp_segs)}")
    info(f"USB_D- segments: {len(dm_segs)}")

    if not dp_segs and not dm_segs:
        check("USB traces exist", False, "no routed USB segments found")
        print(f"\nResults: {PASS} passed, {FAIL} failed")
        return 1

    # Analyze trace widths per layer
    all_usb_segs = dp_segs + dm_segs
    layer_widths = defaultdict(list)
    layer_lengths = defaultdict(float)

    for seg in all_usb_segs:
        layer_widths[seg["layer"]].append(seg["width"])
        layer_lengths[seg["layer"]] += segment_length(seg)

    print(f"\n-- USB Trace Geometry --")
    for layer in sorted(layer_widths.keys()):
        widths = layer_widths[layer]
        avg_w = sum(widths) / len(widths)
        min_w = min(widths)
        max_w = max(widths)
        total_len = layer_lengths[layer]
        print(f"  {layer}: {len(widths)} segments, "
              f"width={min_w:.3f}-{max_w:.3f}mm (avg {avg_w:.3f}mm), "
              f"length={total_len:.2f}mm")

    # Compute impedance for each layer
    print(f"\n-- Single-Ended Impedance --")
    z0_values = {}

    for layer, widths in sorted(layer_widths.items()):
        if layer not in STACKUP:
            warn(f"Unknown layer {layer} for USB traces")
            continue

        params = STACKUP[layer]
        avg_w = sum(widths) / len(widths)
        h = params["h_to_ref"]
        t = params["t"]

        z0 = microstrip_z0(avg_w, t, h, ER)
        if z0 is None:
            warn(f"{layer} impedance calculation failed",
                 f"w={avg_w:.3f}mm, h={h:.4f}mm, t={t:.4f}mm")
            continue

        z0_values[layer] = z0
        ref = params["ref_plane"]
        info(f"{layer}: Z0 = {z0:.1f} ohm "
             f"(w={avg_w:.3f}mm, h={h:.4f}mm, t={t:.4f}mm, Er={ER}, ref={ref})")

        in_range = Z0_PASS_RANGE[0] <= z0 <= Z0_PASS_RANGE[1]
        check(f"{layer} Z0 in reasonable range ({Z0_PASS_RANGE[0]}-{Z0_PASS_RANGE[1]} ohm)",
              in_range, f"Z0={z0:.1f} ohm")

    # Differential impedance
    print(f"\n-- Differential Impedance --")

    # Find parallel D+/D- pairs on the same layer
    dp_by_layer = defaultdict(list)
    dm_by_layer = defaultdict(list)
    for s in dp_segs:
        dp_by_layer[s["layer"]].append(s)
    for s in dm_segs:
        dm_by_layer[s["layer"]].append(s)

    found_diff_pair = False
    for layer in sorted(set(dp_by_layer.keys()) & set(dm_by_layer.keys())):
        pairs = find_parallel_segments(dp_by_layer[layer], dm_by_layer[layer])
        if not pairs:
            info(f"{layer}: no parallel D+/D- pairs found (single-ended routing)")
            continue

        found_diff_pair = True
        spacings = [p[2] for p in pairs]
        avg_s = sum(spacings) / len(spacings)
        z0 = z0_values.get(layer)

        if z0 is None:
            warn(f"{layer}: cannot compute Zdiff (no Z0 available)")
            continue

        h = STACKUP[layer]["h_to_ref"]
        zdiff = differential_impedance(z0, avg_s, h)

        info(f"{layer}: Zdiff = {zdiff:.1f} ohm "
             f"(Z0={z0:.1f}, spacing={avg_s:.3f}mm, {len(pairs)} pair(s))")

        # Check against thresholds
        if ZDIFF_FAIL[0] <= zdiff <= ZDIFF_FAIL[1]:
            if ZDIFF_FORGIVING[0] <= zdiff <= ZDIFF_FORGIVING[1]:
                check(f"{layer} Zdiff in USB FS forgiving range", True)
                if not (ZDIFF_STRICT[0] <= zdiff <= ZDIFF_STRICT[1]):
                    warn(f"{layer} Zdiff outside strict USB spec ({ZDIFF_STRICT[0]}-{ZDIFF_STRICT[1]} ohm)",
                         f"Zdiff={zdiff:.1f} ohm (OK for USB FS)")
            else:
                warn(f"{layer} Zdiff outside forgiving range ({ZDIFF_FORGIVING[0]}-{ZDIFF_FORGIVING[1]} ohm)",
                     f"Zdiff={zdiff:.1f} ohm (may work for USB FS)")
                check(f"{layer} Zdiff not catastrophic", True)
        else:
            check(f"{layer} Zdiff within absolute limits", False,
                  f"Zdiff={zdiff:.1f} ohm (outside {ZDIFF_FAIL[0]}-{ZDIFF_FAIL[1]} ohm)")

    if not found_diff_pair:
        info("No differential pairs found — USB routed as single-ended")
        info("USB Full Speed (12 Mbps) can work with single-ended routing")
        info("if trace lengths are short (<50mm) and matched")

        # Check D+/D- length matching
        dp_total = sum(segment_length(s) for s in dp_segs)
        dm_total = sum(segment_length(s) for s in dm_segs)
        if dp_total > 0 and dm_total > 0:
            mismatch_pct = abs(dp_total - dm_total) / max(dp_total, dm_total) * 100
            info(f"D+ total length: {dp_total:.2f}mm")
            info(f"D- total length: {dm_total:.2f}mm")
            info(f"Length mismatch: {mismatch_pct:.1f}%")
            check("USB D+/D- length mismatch < 20%", mismatch_pct < 20,
                  f"mismatch={mismatch_pct:.1f}%")
        else:
            check("USB D+/D- both have traces", dp_total > 0 and dm_total > 0,
                  f"D+={dp_total:.1f}mm, D-={dm_total:.1f}mm")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
