"""Generate JLCPCB CPL (Component Placement List) from board data."""

import csv
import os

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

    # Power slide switch (back side)
    x, y = enc_to_pcb(*PWR_SWITCH_ENC)
    p.append(("SW_PWR", "SS-12D00G3",
              "SS-12D00G3", x, y, 0, "bottom"))

    # Speaker (back side, 22mm)
    x, y = enc_to_pcb(*SPEAKER_ENC)
    p.append(("SPK1", "Speaker-22mm",
              "Speaker-22mm-Pad", x, y, 0, "bottom"))

    # IP5306 power IC (moved left to avoid slot)
    ix, iy = enc_to_pcb(*IP5306_ENC)
    p.append(("U2", "IP5306",
              "ESOP-8", ix, iy, 0, "bottom"))

    # AMS1117 LDO (near IP5306)
    amx, amy = enc_to_pcb(*AMS1117_ENC)
    p.append(("U3", "AMS1117-3.3",
              "SOT-223", amx, amy, 0, "bottom"))

    # PAM8403 audio amp
    px, py = enc_to_pcb(*PAM8403_ENC)
    p.append(("U5", "PAM8403",
              "SOP-16", px, py, 0, "bottom"))

    # Inductor (near IP5306)
    lx, ly = enc_to_pcb(*INDUCTOR_ENC)
    p.append(("L1", "1uH",
              "SMD-4x4x2", lx, ly, 0, "bottom"))

    # JST battery connector
    jx, jy = enc_to_pcb(*JST_BAT_ENC)
    p.append(("J3", "JST-PH-2P",
              "JST-PH-2P-Vertical", jx, jy, 0, "bottom"))

    # ── Passive components (back side) ────────────────────────────

    # USB-C CC resistors
    ux, uy = enc_to_pcb(*USBC_ENC)
    p.append(("R1", "5.1k", "R_0805",
              ux - 6, uy - 5, 0, "bottom"))
    p.append(("R2", "5.1k", "R_0805",
              ux + 6, uy - 5, 0, "bottom"))

    # ESP32 decoupling (below ESP32 module, 18x25.5mm body)
    ex, ey = enc_to_pcb(*ESP32_ENC)
    p.append(("R3", "10k", "R_0805",
              ex - 15, ey + 16, 0, "bottom"))
    p.append(("C3", "100nF", "C_0805",
              ex - 10, ey + 16, 0, "bottom"))
    p.append(("C4", "100nF", "C_0805",
              ex + 10, ey + 16, 0, "bottom"))

    # LED current-limiting resistors (on back, near ESP32)
    p.append(("R17", "1k", "R_0805",
              ex - 5, ey + 16, 0, "bottom"))
    p.append(("R18", "1k", "R_0805",
              ex + 5, ey + 16, 0, "bottom"))

    # ── Button pull-up resistors (centered row below ESP32, y=44) ──
    # 13 resistors at 5mm spacing, centered at x=80 (x=50..110)
    pull_up_refs = [f"R{i}" for i in range(4, 16)] + ["R19"]
    for i, ref in enumerate(pull_up_refs):
        p.append((ref, "10k", "R_0805",
                  50 + i * 5, 44, 0, "bottom"))

    # R16: IP5306 KEY pull-down (near new IP5306/L1 position)
    p.append(("R16", "100k", "R_0805",
              ix + 5, iy + 10, 0, "bottom"))

    # ── Button debounce caps (centered row below pull-ups, y=48) ──
    # 13 caps at 5mm spacing, centered at x=80 (x=50..110)
    debounce_refs = [f"C{i}" for i in range(5, 17)] + ["C20"]
    for i, ref in enumerate(debounce_refs):
        p.append((ref, "100nF", "C_0805",
                  50 + i * 5, 48, 0, "bottom"))

    # ── IP5306 support caps (near new IP5306 position) ──
    p.append(("C17", "10uF", "C_0805",
              ix - 6, iy - 5, 0, "bottom"))
    p.append(("C18", "10uF", "C_0805",
              ix + 6, iy - 5, 0, "bottom"))

    # C19 near inductor L1
    p.append(("C19", "22uF", "C_1206",
              lx, ly + 6, 0, "bottom"))

    # ── AMS1117 support caps (near new AMS1117 position) ──
    p.append(("C1", "10uF", "C_0805",
              amx, amy - 5, 0, "bottom"))
    p.append(("C2", "22uF", "C_1206",
              amx, amy + 5, 0, "bottom"))

    return p


def export_cpl(output_dir: str):
    """Write CPL.csv for JLCPCB pick-and-place."""
    placements = _build_placements()
    path = os.path.join(output_dir, "cpl.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "Designator", "Val", "Package",
            "Mid X", "Mid Y", "Rotation", "Layer",
        ])
        for ref, val, pkg, x, y, rot, layer in placements:
            w.writerow([
                ref, val, pkg,
                f"{x:.2f}mm", f"{y:.2f}mm",
                rot, layer.capitalize(),
            ])
    print(f"  CPL: {path} ({len(placements)} components)")
    return path
