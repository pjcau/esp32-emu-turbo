"""Generate JLCPCB CPL (Component Placement List) from board data.

JLCPCB rotation corrections:
  KiCad and JLCPCB use different conventions for bottom-side components.
  KiCad flips around the Y-axis; JLCPCB uses a different reference frame.
  The community-validated fix is:
    1. Bottom-side mirror: rot = (rot - 180) % 360
    2. Per-footprint correction from the JLCKicadTools/KiBot databases
    3. Default correction of 180° (cancels mirror) for unmatched footprints

  Refs:
    - https://github.com/Bouni/kicad-jlcpcb-tools/issues/636
    - https://github.com/matthewlai/JLCKicadTools (cpl_rotations_db.csv)
    - https://kibot.readthedocs.io/en/v1.8.0/notes_position.html
"""

import csv
import os
import re

from .board import (
    enc_to_pcb,
    ESP32_ENC, FPC_ENC, USBC_ENC, SD_ENC,
    DPAD_ENC, DPAD_OFFSETS, ABXY_ENC, ABXY_OFFSETS,
    SS_ENC, SS_OFFSETS, SHOULDER_L_ENC, SHOULDER_R_ENC,
    IP5306_ENC, AMS1117_ENC, PAM8403_ENC,
    INDUCTOR_ENC, JST_BAT_ENC,
    PWR_SWITCH_ENC, LED_CHARGE_ENC, LED_FULL_ENC,
    MENU_ENC, SPEAKER_ENC,
)


# ── JLCPCB rotation corrections (from JLCKicadTools cpl_rotations_db.csv) ──
# Only entries that differ from the default (180°) are listed.
# These values combine with the bottom-side mirror to produce correct
# JLCPCB pick-and-place orientation.
_JLCPCB_ROT_CORRECTIONS = [
    (r"^SOP-(?!18_|4_)", 270),   # SOP packages (except SOP-18, SOP-4)
    (r"^SOIC-", 270),            # SOIC packages
    (r"^TSSOP-", 270),           # TSSOP packages
    (r"^SSOP-", 270),            # SSOP packages
    (r"^SOT-23", -90),           # SOT-23 family
    (r"^LQFP-", 270),            # LQFP packages
    (r"^TQFP-", 270),            # TQFP packages
    (r"^DFN-", 270),             # DFN packages
]
_JLCPCB_ROT_DEFAULT = 180  # Cancels bottom mirror → preserves original rotation

# ── JLCPCB position corrections (mm) ──
# Compensate for KiCad footprint origin vs JLCPCB component library origin.
# JLCPCB places 3D model at CPL coordinates — if footprint origin != pad center,
# the model appears offset. These corrections align CPL with actual pad centers.
_JLCPCB_POS_CORRECTIONS = {
    "U1": (0, 3.62),      # ESP32: body center → pin center (confirmed working)
    "J4": (-1.85, 0),     # FPC: footprint origin → pad center (pads at x=-1.85 after rotation)
    "SW_PWR": (0, -1.5),  # MSK12C02: shift up so 3D model pins align with pads
}

# ── Per-component rotation overrides (bypass formula) ──
# Use when a specific LCSC part's 3D model has non-standard orientation.
# The JLCPCB C5122557 (PAM8403) 3D model's default orientation differs
# from the generic SOP correction database. Tested empirically.
_JLCPCB_ROT_OVERRIDES = {
    "U5": 90,    # PAM8403 (C5122557) — 90° pre-rotation + X-mirror requires CPL=90
}


def _jlcpcb_rotation(rot, layer, footprint_name, ref=None):
    """Compute JLCPCB CPL rotation from KiCad rotation."""
    # Per-component override (bypass formula entirely)
    if ref and ref in _JLCPCB_ROT_OVERRIDES:
        return _JLCPCB_ROT_OVERRIDES[ref]

    if layer != "bottom":
        return rot  # Top side: no correction needed

    # Bottom-side mirror (community-validated formula)
    rot = (rot - 180) % 360

    # Per-footprint correction (from database)
    correction = _JLCPCB_ROT_DEFAULT
    for pattern, corr in _JLCPCB_ROT_CORRECTIONS:
        if re.match(pattern, footprint_name):
            correction = corr
            break

    return (rot + correction) % 360


def _build_placements():
    """Build placement list: (ref, val, pkg, x, y, rot, layer).

    Layout:
      TOP (F.Cu)  — face buttons (D-pad, ABXY, Start, Select, Menu)
                    + charging LEDs (bottom-left)
      BOTTOM (B.Cu) — everything else: ESP32, ICs, connectors,
                      speaker, power switch, passives, battery connector
                      + L/R shoulder buttons (rotated 90°, aligned to top edge)

    All passives have >= 3mm center-to-center spacing and are placed
    OUTSIDE IC courtyard zones.
    """
    p = []

    # ══════════════════════════════════════════════════════════════
    # TOP SIDE (F.Cu): face buttons + LEDs
    # ══════════════════════════════════════════════════════════════

    # D-pad SW1-4
    for i, (dx, dy) in enumerate(DPAD_OFFSETS):
        bx, by = DPAD_ENC
        x, y = enc_to_pcb(bx + dx, by + dy)
        p.append((f"SW{i+1}", "SW_Push",
                  "SW-SMD-5.1x5.1", x, y, 0, "top"))

    # ABXY SW5-8
    for i, (dx, dy) in enumerate(ABXY_OFFSETS):
        bx, by = ABXY_ENC
        x, y = enc_to_pcb(bx + dx, by + dy)
        p.append((f"SW{i+5}", "SW_Push",
                  "SW-SMD-5.1x5.1", x, y, 0, "top"))

    # Start/Select SW9-10
    for i, (dx, dy) in enumerate(SS_OFFSETS):
        bx, by = SS_ENC
        x, y = enc_to_pcb(bx + dx, by + dy)
        p.append((f"SW{i+9}", "SW_Push",
                  "SW-SMD-5.1x5.1", x, y, 0, "top"))

    # Menu button SW13
    x, y = enc_to_pcb(*MENU_ENC)
    p.append(("SW13", "SW_Push",
              "SW-SMD-5.1x5.1", x, y, 0, "top"))

    # Charging LEDs (front side, bottom-left)
    x, y = enc_to_pcb(*LED_CHARGE_ENC)
    p.append(("LED1", "Red",
              "LED_0805", x, y, 0, "top"))
    x, y = enc_to_pcb(*LED_FULL_ENC)
    p.append(("LED2", "Green",
              "LED_0805", x, y, 0, "top"))

    # ══════════════════════════════════════════════════════════════
    # BOTTOM SIDE (B.Cu): everything else + shoulder buttons
    # ══════════════════════════════════════════════════════════════

    # Shoulder L/R (back side, rotated 90°, aligned to top edge)
    x, y = enc_to_pcb(*SHOULDER_L_ENC)
    p.append(("SW11", "SW_Push",
              "SW-SMD-5.1x5.1", x, y, 90, "bottom"))
    x, y = enc_to_pcb(*SHOULDER_R_ENC)
    p.append(("SW12", "SW_Push",
              "SW-SMD-5.1x5.1", x, y, 90, "bottom"))

    # ESP32-S3 module (center, back)
    x, y = enc_to_pcb(*ESP32_ENC)
    p.append(("U1", "ESP32-S3-WROOM-1-N16R8",
              "Module_ESP32-S3", x, y, 0, "bottom"))

    # FPC display connector (back side, right of slot, vertical)
    x, y = enc_to_pcb(*FPC_ENC)
    p.append(("J4", "FPC-40P-0.5mm",
              "FPC-40P-0.5mm", x, y, 90, "bottom"))

    # USB-C connector (back side)
    x, y = enc_to_pcb(*USBC_ENC)
    p.append(("J1", "USB-C-16P",
              "USB-C-SMD-16P", x, y, 0, "bottom"))

    # SD card slot (back side, bottom-right)
    x, y = enc_to_pcb(*SD_ENC)
    p.append(("U6", "Micro-SD-TF-01A",
              "TF-01A", x, y, 0, "bottom"))

    # Power slide switch (back side, horizontal — toggle faces toward board edge)
    x, y = enc_to_pcb(*PWR_SWITCH_ENC)
    p.append(("SW_PWR", "SS-12D00G3",
              "SS-12D00G3", x, y, 0, "bottom"))

    # Speaker (SPK1) — manual assembly, not in BOM, excluded from CPL

    # IP5306 power IC (moved left to avoid slot)
    ix, iy = enc_to_pcb(*IP5306_ENC)
    p.append(("U2", "IP5306",
              "ESOP-8", ix, iy, 0, "bottom"))

    # AMS1117 LDO (near IP5306)
    amx, amy = enc_to_pcb(*AMS1117_ENC)
    p.append(("U3", "AMS1117-3.3",
              "SOT-223", amx, amy, 0, "bottom"))

    # PAM8403 audio amp (rotated 90° for routing to speaker below)
    px, py = enc_to_pcb(*PAM8403_ENC)
    p.append(("U5", "PAM8403",
              "SOP-16", px, py, 90, "bottom"))

    # Inductor (near IP5306)
    lx, ly = enc_to_pcb(*INDUCTOR_ENC)
    p.append(("L1", "1uH",
              "SMD-4x4x2", lx, ly, 0, "bottom"))

    # JST battery connector
    jx, jy = enc_to_pcb(*JST_BAT_ENC)
    p.append(("J3", "JST-PH-2P",
              "JST-PH-2P-Vertical", jx, jy, 0, "bottom"))

    # ── Passive components (back side) ────────────────────────────
    # All passives have >= 3mm center-to-center spacing.
    # Layout rows (Y increases downward in KiCad):
    #   y=35   IP5306 support caps (C17)
    #   y=37.5 IP5306 support caps (C18)
    #   y=42   ESP32 decoupling (R3, C3, C4)
    #   y=46   Pull-up resistors (R4-R15, R19) x=43..103
    #   y=50   Debounce caps (C5-C16, C20) x=43..103

    # USB-C CC resistors
    ux, uy = enc_to_pcb(*USBC_ENC)
    p.append(("R1", "5.1k", "R_0805",
              ux - 6, uy - 5, 0, "bottom"))
    p.append(("R2", "5.1k", "R_0805",
              ux + 6, uy - 5, 0, "bottom"))

    # ESP32 decoupling (y=42, below ESP32 body edge at 40.25)
    p.append(("R3", "10k", "R_0805", 65, 42, 0, "bottom"))
    p.append(("C3", "100nF", "C_0805", 69.5, 42, 0, "bottom"))  # DFM: synced with board.py
    p.append(("C4", "100nF", "C_0805", 92, 42, 0, "bottom"))  # DFM: synced with board.py

    # LED current-limiting resistors (B.Cu, above LEDs on F.Cu)
    # Must match board.py: R17 at (25, 65), R18 at (32, 65)
    p.append(("R17", "1k", "R_0805", 25, 65, 0, "bottom"))
    p.append(("R18", "1k", "R_0805", 32, 65, 0, "bottom"))

    # ── Button pull-up resistors (y=46, x=43..103, 5mm spacing) ──
    # Shifted left to avoid IP5306 at x=110
    pull_up_refs = [f"R{i}" for i in range(4, 16)] + ["R19"]
    for i, ref in enumerate(pull_up_refs):
        p.append((ref, "10k", "R_0805",
                  43 + i * 5, 46, 0, "bottom"))

    # R16: IP5306 KEY pull-down (near IP5306/L1)
    p.append(("R16", "100k", "R_0805",
              ix + 5, iy + 10, 0, "bottom"))

    # ── Button debounce caps (y=50, x=43..103, 5mm spacing) ──
    debounce_refs = [f"C{i}" for i in range(5, 17)] + ["C20"]
    for i, ref in enumerate(debounce_refs):
        p.append((ref, "100nF", "C_0805",
                  43 + i * 5, 50, 0, "bottom"))

    # ── IP5306 support caps (away from mounting hole at 105,37.5) ──
    p.append(("C17", "10uF", "C_0805", 110, 35, 0, "bottom"))
    p.append(("C18", "10uF", "C_0805", 118, 55, 0, "bottom"))  # DFM: synced with board.py

    # C19 near inductor L1
    p.append(("C19", "22uF", "C_1206",
              lx, ly + 6, 0, "bottom"))

    # ── AMS1117 support caps (±7mm spacing for DFM clearance) ──
    p.append(("C1", "10uF", "C_0805",
              amx - 3, amy - 7, 0, "bottom"))  # DFM: match board.py (moved from amx-1)
    p.append(("C2", "22uF", "C_1206",
              amx, amy + 7, 0, "bottom"))

    return p


def export_cpl(output_dir: str):
    """Write CPL.csv for JLCPCB pick-and-place.

    Applies JLCPCB-specific corrections:
      - Position offsets for components with non-standard origins (ESP32)
      - Rotation corrections for bottom-side convention differences
    """
    placements = _build_placements()
    path = os.path.join(output_dir, "cpl.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "Designator", "Val", "Package",
            "Mid X", "Mid Y", "Rotation", "Layer",
        ])
        for ref, val, pkg, x, y, rot, layer in placements:
            # Apply JLCPCB position correction
            if ref in _JLCPCB_POS_CORRECTIONS:
                dx, dy = _JLCPCB_POS_CORRECTIONS[ref]
                x += dx
                y += dy

            # Apply JLCPCB rotation correction
            rot = _jlcpcb_rotation(rot, layer, pkg, ref=ref)

            w.writerow([
                ref, val, pkg,
                f"{x:.2f}mm", f"{y:.2f}mm",
                rot, layer.capitalize(),
            ])
    print(f"  CPL: {path} ({len(placements)} components)")
    return path
