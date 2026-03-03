#!/usr/bin/env python3
"""Violation matrix: parse .kicad_pcb and find ALL pad/via spacing violations.

Reports all pairs with gap < 0.15mm (JLCPCB danger threshold) on F.Cu and B.Cu.
Via data: position, size (outer diameter), drill, net.
Pad data: position, size (x, y), shape, layer, net, ref.

JLCPCB pad name decode reference:
  r18.1102 = 18.11 mil = 0.460mm round
  r27.5591 = 27.56 mil = 0.700mm round
  r35.4331 = 35.43 mil = 0.899mm round
  rect47.2... = 47.24 mil = 1.2mm long FPC pad
"""

import re
import math
import sys
from pathlib import Path

PCB_FILE = Path("/Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo/hardware/kicad/esp32-emu-turbo.kicad_pcb")

DANGER_GAP = 0.12   # < this = JLCPCB danger
WARNING_GAP = 0.15  # < this = JLCPCB warning

# ── Parsing helpers ────────────────────────────────────────────────────────

def parse_pcb(path):
    text = Path(path).read_text(encoding="utf-8")
    vias = _parse_vias(text)
    pads = _parse_pads(text)
    return vias, pads


def _parse_vias(text):
    """Extract all vias."""
    vias = []
    via_pat = re.compile(
        r'\(via\s*'
        r'(?:\([^)]*\)\s*)*'
        r'\(at\s+([\d.+-]+)\s+([\d.+-]+)\)'
        r'.*?'
        r'\(size\s+([\d.]+)\)'
        r'.*?'
        r'\(drill\s+([\d.]+)\)'
        r'.*?'
        r'\(layers\s+"?([^")\s]+)"?\s+"?([^")\s]+)"?\)'
        r'(?:.*?\(net\s+(\d+)\))?',
        re.DOTALL
    )
    for m in via_pat.finditer(text):
        x, y = float(m.group(1)), float(m.group(2))
        size = float(m.group(3))
        drill = float(m.group(4))
        layer1 = m.group(5)
        layer2 = m.group(6)
        net = int(m.group(7)) if m.group(7) else 0
        vias.append({
            "x": x, "y": y,
            "size": size, "drill": drill,
            "layers": {layer1, layer2},
            "net": net,
            "radius": size / 2,
        })
    return vias


def _parse_pads(text):
    """Extract all SMD and THT pads from footprints.

    The KiCad 8+ format has footprints as:
      (footprint "name" (at x y [rot]) (layer "F.Cu") ... )
    or (older style):
      (footprint "name"\n    (layer "F.Cu")\n    ...\n    (at x y)\n ...)
    """
    pads = []

    # Pattern to find footprint header with its position
    # Handles both inline: (footprint "X" (at 1 2 [rot]) ...)
    # and multi-line: (footprint "X"\n  (layer...)\n  (at x y)\n ...)
    fp_header_pat = re.compile(r'\(footprint\s+"([^"]*)"')

    # We'll split the text into footprint blocks
    fp_starts = [(m.start(), m.group(1)) for m in fp_header_pat.finditer(text)]

    # Pad pattern (single-line pad entries in KiCad 8+ format)
    pad_pat = re.compile(
        r'\(pad\s+"?([^"\s)]+)"?\s+(\w+)\s+(\w+)\s*'
        r'\(at\s+([\d.+-]+)\s+([\d.+-]+)(?:\s+([\d.+-]+))?\)\s*'
        r'\(size\s+([\d.]+)\s+([\d.]+)\)'
        r'(?:.*?\(layers\s+([^)]+)\))?'
        r'(?:.*?\(net\s+(\d+))?'
    )

    for idx, (start, fp_name) in enumerate(fp_starts):
        end = fp_starts[idx+1][0] if idx+1 < len(fp_starts) else len(text)
        block = text[start:end]

        # Get footprint reference from property
        ref_m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        ref = ref_m.group(1) if ref_m else fp_name.split(":")[-1]

        # Get footprint position: try inline first
        fp_at_m = re.search(r'\(footprint\s+"[^"]*"\s+\(at\s+([\d.+-]+)\s+([\d.+-]+)(?:\s+([\d.+-]+))?\)', block)
        if not fp_at_m:
            # Try multi-line: (at x y) on its own line (not inside a sub-element)
            # Only match top-level (at ...) — skip nested ones inside properties
            # Find the first (at ...) that's not inside a property
            block_trimmed = re.sub(r'\(property[^)]*(?:\([^)]*\))*[^)]*\)', '', block)
            fp_at_m = re.search(r'\(at\s+([\d.+-]+)\s+([\d.+-]+)(?:\s+([\d.+-]+))?\)', block_trimmed)
        if not fp_at_m:
            continue

        fp_x = float(fp_at_m.group(1))
        fp_y = float(fp_at_m.group(2))
        fp_rot = float(fp_at_m.group(3)) if fp_at_m.group(3) else 0.0

        for pm in pad_pat.finditer(block):
            pad_num = pm.group(1)
            pad_type = pm.group(2)  # smd, thru_hole, np_thru_hole
            pad_shape = pm.group(3)  # rect, roundrect, circle, oval

            # Skip non-plated holes (no copper connection)
            if pad_type == "np_thru_hole":
                continue

            # Pad local position
            lx = float(pm.group(4))
            ly = float(pm.group(5))

            # Rotate pad local coords by footprint rotation
            angle_rad = math.radians(fp_rot)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            rx = lx * cos_a - ly * sin_a
            ry = lx * sin_a + ly * cos_a

            px = fp_x + rx
            py = fp_y + ry

            sx = float(pm.group(7))
            sy = float(pm.group(8))

            layers_str = pm.group(9) or ""
            net = int(pm.group(10)) if pm.group(10) else 0

            # Determine copper layers
            copper_layers = set()
            if "F.Cu" in layers_str:
                copper_layers.add("F.Cu")
            if "B.Cu" in layers_str:
                copper_layers.add("B.Cu")
            if "*.Cu" in layers_str:
                copper_layers.update({"F.Cu", "B.Cu"})

            # Skip pads with no copper layer assignment
            if not copper_layers:
                continue

            pads.append({
                "ref": ref,
                "num": pad_num,
                "type": pad_type,
                "shape": pad_shape,
                "x": px,
                "y": py,
                "sx": sx,
                "sy": sy,
                "layers": copper_layers,
                "net": net,
                # Effective radius = half the larger dimension (conservative for violations)
                "radius": max(sx, sy) / 2,
                "fp_name": fp_name,
            })

    return pads


# ── Gap computation ────────────────────────────────────────────────────────

def via_to_via_gap(v1, v2):
    dx = v1["x"] - v2["x"]
    dy = v1["y"] - v2["y"]
    return math.hypot(dx, dy) - v1["radius"] - v2["radius"]


def via_to_pad_gap(v, p):
    dx = v["x"] - p["x"]
    dy = v["y"] - p["y"]
    return math.hypot(dx, dy) - v["radius"] - p["radius"]


def pad_to_pad_gap(p1, p2):
    dx = p1["x"] - p2["x"]
    dy = p1["y"] - p2["y"]
    return math.hypot(dx, dy) - p1["radius"] - p2["radius"]


# ── Main matrix builder ────────────────────────────────────────────────────

def build_matrix(vias, pads, threshold=WARNING_GAP):
    violations = []

    for layer in ("F.Cu", "B.Cu"):
        l_vias = [v for v in vias if layer in v["layers"]]
        l_pads = [p for p in pads if layer in p["layers"]]

        # Via-to-via
        for i, v1 in enumerate(l_vias):
            for v2 in l_vias[i+1:]:
                gap = via_to_via_gap(v1, v2)
                if gap < threshold:
                    violations.append({
                        "layer": layer,
                        "type": "via-via",
                        "gap": gap,
                        "a_desc": f"via@({v1['x']:.3f},{v1['y']:.3f}) d={v1['size']}mm",
                        "b_desc": f"via@({v2['x']:.3f},{v2['y']:.3f}) d={v2['size']}mm",
                        "nets": (v1["net"], v2["net"]),
                        "same_net": v1["net"] == v2["net"] and v1["net"] != 0,
                        "v_a": v1,
                        "v_b": v2,
                    })

        # Via-to-pad
        for v in l_vias:
            for p in l_pads:
                gap = via_to_pad_gap(v, p)
                if gap < threshold:
                    violations.append({
                        "layer": layer,
                        "type": "via-pad",
                        "gap": gap,
                        "a_desc": f"via@({v['x']:.3f},{v['y']:.3f}) d={v['size']}mm net={v['net']}",
                        "b_desc": f"{p['ref']}[{p['num']}] @({p['x']:.3f},{p['y']:.3f}) {p['sx']}x{p['sy']}mm net={p['net']}",
                        "nets": (v["net"], p["net"]),
                        "same_net": v["net"] == p["net"] and v["net"] != 0,
                        "v_a": v,
                        "p_b": p,
                    })

        # Pad-to-pad
        for i, p1 in enumerate(l_pads):
            for p2 in l_pads[i+1:]:
                gap = pad_to_pad_gap(p1, p2)
                if gap < threshold:
                    violations.append({
                        "layer": layer,
                        "type": "pad-pad",
                        "gap": gap,
                        "a_desc": f"{p1['ref']}[{p1['num']}] @({p1['x']:.3f},{p1['y']:.3f}) {p1['sx']}x{p1['sy']}mm net={p1['net']}",
                        "b_desc": f"{p2['ref']}[{p2['num']}] @({p2['x']:.3f},{p2['y']:.3f}) {p2['sx']}x{p2['sy']}mm net={p2['net']}",
                        "nets": (p1["net"], p2["net"]),
                        "same_net": p1["net"] == p2["net"] and p1["net"] != 0,
                        "p_a": p1,
                        "p_b": p2,
                    })

    return violations


def print_report(violations, vias, pads):
    danger = [v for v in violations if v["gap"] < DANGER_GAP]
    warning = [v for v in violations if DANGER_GAP <= v["gap"] < WARNING_GAP]

    print(f"\n{'='*80}")
    print(f"VIOLATION MATRIX — threshold={WARNING_GAP}mm")
    print(f"{'='*80}")

    d_fc = [v for v in danger if v["layer"] == "F.Cu"]
    d_bc = [v for v in danger if v["layer"] == "B.Cu"]
    w_fc = [v for v in warning if v["layer"] == "F.Cu"]
    w_bc = [v for v in warning if v["layer"] == "B.Cu"]

    print(f"DANGER (<{DANGER_GAP}mm): {len(danger)} total ({len(d_fc)} F.Cu, {len(d_bc)} B.Cu)")
    print(f"WARNING (<{WARNING_GAP}mm): {len(warning)} total ({len(w_fc)} F.Cu, {len(w_bc)} B.Cu)")

    def print_section(lst, title):
        if not lst:
            return
        print(f"\n{'─'*70}")
        print(f"{title} ({len(lst)} items)")
        print(f"{'─'*70}")
        for v in sorted(lst, key=lambda x: x["gap"]):
            same = "[SAME-NET]" if v["same_net"] else "[DIFF-NET ***FIX***]"
            flag = "DANGER" if v["gap"] < DANGER_GAP else "WARN  "
            print(f"  {flag} gap={v['gap']:+.4f}mm {v['type']:10s} {same}")
            print(f"    A: {v['a_desc']}")
            print(f"    B: {v['b_desc']}")

    print_section(d_fc, "F.Cu DANGER")
    print_section(d_bc, "B.Cu DANGER")
    print_section(w_fc, "F.Cu WARNING")
    print_section(w_bc, "B.Cu WARNING")

    # JLCPCB-specific: DANGER items that are DIFF-NET (must fix)
    must_fix = [v for v in danger if not v["same_net"]]
    if must_fix:
        print(f"\n{'='*80}")
        print(f"MUST FIX ({len(must_fix)} items — different net, danger gap)")
        print(f"{'='*80}")
        for v in sorted(must_fix, key=lambda x: x["gap"]):
            print(f"\n  [{v['layer']}] {v['type']} gap={v['gap']:.4f}mm")
            print(f"  A: {v['a_desc']}")
            print(f"  B: {v['b_desc']}")
    else:
        print(f"\n\nAll DANGER items are SAME-NET (per-net connections, JLCPCB may still flag).")
        print("These are via-to-via gaps where both vias are on the same net.")
        print("JLCPCB flags same-net via-to-via DANGER if gap < ~0.09mm (18.11mil roundtrip).")

    # Summary
    print(f"\n\n{'='*80}")
    print("FULL VIA INVENTORY in FPC zone (x=129-142, y=22-52)")
    print(f"{'='*80}")
    fpc_vias = [v for v in vias if 129 <= v["x"] <= 142 and 22 <= v["y"] <= 52]
    for v in sorted(fpc_vias, key=lambda x: (x["x"], x["y"])):
        layers = "/".join(sorted(v["layers"]))
        print(f"  via@({v['x']:7.3f},{v['y']:7.3f}) d={v['size']}mm drill={v['drill']}mm net={v['net']:3d} [{layers}]")

    # FPC pad inventory
    print(f"\n\n{'='*80}")
    print("FPC J4 PADS (B.Cu) in zone x=129-142, y=22-52")
    print(f"{'='*80}")
    fpc_pads = [p for p in pads if p["ref"] == "J4" and "B.Cu" in p["layers"]]
    for p in sorted(fpc_pads, key=lambda x: (x["x"], x["y"])):
        print(f"  J4[{p['num']:2s}] @({p['x']:7.3f},{p['y']:7.3f}) {p['sx']}x{p['sy']}mm net={p['net']:3d}")

    # Via sizes summary
    print(f"\n\nAll via sizes: {sorted(set(v['size'] for v in vias))}")
    print(f"All via drills: {sorted(set(v['drill'] for v in vias))}")
    print(f"Total vias: {len(vias)}")
    print(f"Total pads: {len(pads)}")


if __name__ == "__main__":
    print(f"Parsing: {PCB_FILE}")
    vias, pads = parse_pcb(PCB_FILE)

    fc_vias = sum(1 for v in vias if "F.Cu" in v["layers"])
    bc_vias = sum(1 for v in vias if "B.Cu" in v["layers"])
    fc_pads = sum(1 for p in pads if "F.Cu" in p["layers"])
    bc_pads = sum(1 for p in pads if "B.Cu" in p["layers"])
    print(f"Found {len(vias)} vias, {len(pads)} pads")
    print(f"  Vias: {fc_vias} on F.Cu, {bc_vias} on B.Cu")
    print(f"  Pads: {fc_pads} on F.Cu, {bc_pads} on B.Cu")

    violations = build_matrix(vias, pads, threshold=WARNING_GAP)
    print_report(violations, vias, pads)
