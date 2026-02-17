#!/usr/bin/env python3
"""Inject KiCad standard 3D model references into PCB footprints.

Reads a .kicad_pcb file and adds (model ...) entries to every footprint
that matches the mapping table. The output is written to a new file
(default: same dir, suffixed with '-3d') so the source PCB is untouched.

Usage:
    python3 inject-3d-models.py <input.kicad_pcb> [output.kicad_pcb]
"""
import re
import sys
from pathlib import Path

# KiCad 3D model base variable (KICAD9 var resolves in KiCad 9.x/10 nightly)
M = "${KICAD9_3DMODEL_DIR}"

# Footprint name → 3D model path mapping
# Paths use KiCad environment variable so they work in Docker and GUI
MODEL_MAP = {
    "R_0805":       f"{M}/Resistor_SMD.3dshapes/R_0805_2012Metric.step",
    "C_0805":       f"{M}/Capacitor_SMD.3dshapes/C_0805_2012Metric.step",
    "C_1206":       f"{M}/Capacitor_SMD.3dshapes/C_1206_3216Metric.step",
    "LED_0805":     f"{M}/LED_SMD.3dshapes/LED_0805_2012Metric.step",
    "SOT-223":      f"{M}/Package_TO_SOT_SMD.3dshapes/SOT-223.step",
    "ESOP-8":       f"{M}/Package_SO.3dshapes/SOIC-8_3.9x4.9mm_P1.27mm.step",
    "SOP-16":       f"{M}/Package_SO.3dshapes/SOIC-16_3.9x9.9mm_P1.27mm.step",
    "ESP32-S3-WROOM-1-N16R8": f"{M}/RF_Module.3dshapes/ESP32-WROOM-32.step",
    "USB-C-16P":    f"{M}/Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step",
    "JST-PH-2P":   f"{M}/Connector_JST.3dshapes/JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical.step",
    "SS-12D00G3":   f"{M}/Button_Switch_SMD.3dshapes/SW_SPDT_PCM12.step",
    "SW-SMD-5.1x5.1": f"{M}/Button_Switch_SMD.3dshapes/SW_SPST_TL3342.step",
    # No good match — skip these:
    # "SMD-4x4x2"  → Crystal (no exact 4x4 match in library)
    # "FPC-40P-0.5mm" → FPC connector (no exact 40P match)
    # "TF-01A"      → SD card module (no standard model)
    # "Speaker-22mm" → Speaker (no standard model)
    # "MountingHole:MountingHole_2.5mm" → Just a hole
}

MODEL_TEMPLATE = """		(model "{path}"
			(offset (xyz 0 0 0))
			(scale (xyz 1 1 1))
			(rotate (xyz 0 0 0))
		)
"""


def inject_models(pcb_text: str) -> tuple[str, dict]:
    """Add (model ...) entries to footprints. Returns (modified_text, stats)."""
    stats = {"matched": 0, "skipped": 0, "already_has_model": 0}

    # Find each footprint block and inject model before its closing paren
    # Pattern: (footprint "NAME" ... ) at the top level of the file
    lines = pcb_text.split("\n")
    output = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect footprint opening
        fp_match = re.match(r'(\s*)\(footprint "([^"]*)"', line)
        if fp_match:
            indent = fp_match.group(1)
            fp_name = fp_match.group(2)

            # Collect all lines of this footprint block
            depth = 0
            fp_lines = []
            start_i = i
            while i < len(lines):
                fp_lines.append(lines[i])
                depth += lines[i].count("(") - lines[i].count(")")
                i += 1
                if depth <= 0:
                    break

            fp_block = "\n".join(fp_lines)

            # Check if already has a model
            if "(model " in fp_block:
                stats["already_has_model"] += 1
                output.extend(fp_lines)
                continue

            # Find matching 3D model
            model_path = MODEL_MAP.get(fp_name)
            if model_path:
                # Insert model entry before the last closing paren
                model_entry = MODEL_TEMPLATE.format(path=model_path).rstrip()
                # Insert before the last line (which is the closing paren)
                fp_lines.insert(-1, model_entry)
                stats["matched"] += 1
            else:
                stats["skipped"] += 1

            output.extend(fp_lines)
            continue

        output.append(line)
        i += 1

    return "\n".join(output), stats


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.kicad_pcb> [output.kicad_pcb]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_stem(input_path.stem + "-3d")

    print(f"Reading: {input_path}")
    pcb_text = input_path.read_text()

    result, stats = inject_models(pcb_text)

    output_path.write_text(result)
    print(f"Written: {output_path}")
    print(f"  Matched: {stats['matched']} footprints")
    print(f"  Skipped: {stats['skipped']} (no model mapping)")
    print(f"  Already had model: {stats['already_has_model']}")


if __name__ == "__main__":
    main()
