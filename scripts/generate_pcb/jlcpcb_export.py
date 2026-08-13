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
    IP5306_ENC, BUCK_ENC, PAM8403_ENC,
    INDUCTOR_ENC, JST_BAT_ENC,
    PWR_SWITCH_ENC, LED_CHARGE_ENC, LED_FULL_ENC,
    MENU_ENC, SPEAKER_ENC,
)
from .routing import D1_POS, D1_ROT


# ── JLCPCB rotation corrections (from JLCKicadTools cpl_rotations_db.csv) ──
# Only entries that differ from the default (180°) are listed.
# These values combine with the bottom-side mirror to produce correct
# JLCPCB pick-and-place orientation.
_JLCPCB_ROT_CORRECTIONS = [
    # SOT-23-5 MUST come before the generic "^SOT-23" rule below.
    # Our SOT-23-5 footprint (footprints.sot23_5) is a verbatim copy of the
    # JLCPCB/EasyEDA reference land pattern for C78988, i.e. it is already
    # in JLCPCB's own library frame — unlike SOT-23-3 / SOT-23-6, which use
    # the KiCad-standard frame and therefore need the -90 correction.
    # verify_easyeda_footprint reports delta_row = 0 for U3, confirming the
    # frames match, so the default correction (180, cancels the bottom-side
    # mirror) is the correct one here.
    (r"^SOT-23-5", 180),
    # SOT-23-6 MUST also come before the generic "^SOT-23" rule below, and
    # for the reason that rule's own comment already gives further down:
    # EasyEDA draws SOT-23-3 with pads 1/2 in a COLUMN and SOT-23-6 with
    # them in a ROW, an inconsistency internal to its library. The -90
    # below is the compensation for the column frame, so applying it to
    # SOT-23-6 as well subtracts a rotation that was never there.
    #
    # Measured, not argued — the two parts differ only in this term:
    #     Q1  SOT-23-3  C15127  row_board=180  row_ee=270  cpl=90  OK
    #     U4  SOT-23-6  C7519   row_board=180  row_ee=  0  cpl=90  FAIL
    # Same row_board, row_ee exactly 90 apart, so one blanket correction
    # cannot be right for both. Dropping to the default 180 moves U4's
    # emitted angle by +270 to cpl=0, which is what the law derives.
    # This is the split the regex needed, not a per-part delta.
    (r"^SOT-23-6", 180),
    # ESOP (exposed-pad SOP) needs its OWN rule because "ESOP-8" cannot match
    # "^SOP-" — the anchor is blocked by the leading E — so U2 (IP5306,
    # C181692) fell through every rule to _JLCPCB_ROT_DEFAULT (180) and was
    # emitted at cpl=0. Same one-letter miss that put U4's SOT-23-6 on the
    # SOT-23-3 rule. The copper is correct; only the pick-and-place angle was.
    #
    # cpl=0 does not seat AT ALL: the lead row runs along Y while the pads run
    # along X, so all 8 leads land on bare soldermask (worst offset 5.012 mm,
    # 0 of 8 leads touching copper) and the part is held only by EP paste.
    #
    # 90 is the OTHER wrong answer and it is the dangerous one, because it
    # solders. It puts pin i onto pad i+4: VIN onto the KEY pad, BAT+ (an
    # unfused 4.2 V cell) onto LED1 which is an open-drain indicator sink, LX
    # onto LED2 — with BAT and VOUT connected to nothing.
    #
    # 90 is the value the rotation law derives for this cell, and the law is
    # wrong here — see _LAW_EXCEPTIONS in verify_cpl_rotation_law.py. At
    # cpl=270 every pin lands on its own pad (0.090 mm uniform) and every net
    # is right: VIN->VBUS, KEY->IP5306_KEY, BAT->BAT+, SW->LX, VOUT->+5V,
    # EP->GND, the three LED pins left open. Exactly one rotation is sane.
    (r"^ESOP-", 90),             # ESOP-8 (exposed pad) — emits cpl=270
    (r"^SOP-(?!18_|4_)", 270),   # SOP packages (except SOP-18, SOP-4)
    (r"^SOIC-", 270),            # SOIC packages
    (r"^TSSOP-", 270),           # TSSOP packages
    (r"^SSOP-", 270),            # SSOP packages
    # SOT-23-3. Was -90, which is 180 out, and it reached only D1 and Q1 —
    # SOT-23-5 and SOT-23-6 match their own rules above. Derived the same way
    # U2 was, against the U2 anchor that prototypes #1 and #2 confirm:
    #
    #   D1 (BAT54C, C37704) at KiCad 180: -90 emitted 270, which lands every
    #     lead on bare mask (3.120 mm). At 90 the part seats (0.187 mm) with
    #     the two anodes on BTN_START / BTN_SELECT and the common cathode on
    #     MENU_K — which is the diode-OR the schematic draws.
    #   Q1 (P-MOSFET SOT-23-3, was C10487) at KiCad 0: -90 emitted 90, also all-on-mask
    #     (2.933 mm). At 270 it seats exactly (0.000 mm) with G/S/D on
    #     RPP_GATE / BAT_IN / BAT+.
    #
    # Both want the SAME family constant, which is what makes this one
    # constant rather than two per-part deltas. Unlike U2's case there is no
    # solderable-but-wrong option here: a 180 error on a SOT-23-3 puts the
    # single leg where the pair is, so it simply does not assemble.
    #
    # "Boards R4-R8 power up through Q1" is NOT evidence against this. U2
    # shipped at an angle that cannot seat and those boards charge anyway,
    # because JLCPCB corrected it at assembly — confirmed on protos #1 and #2.
    # The same correction explains Q1. See H4 in docs/known-issues.md.
    (r"^SOT-23", 90),            # SOT-23-3 (D1, Q1) — see above
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
    "J1": (0, 0),         # USB-C: footprint now matches JLCPCB C2765186 exactly
    "J4": (0, 0),         # FPC: footprint now matches JLCPCB C2856812 exactly
    "SW16": (0, 0),     # MSK12C02: footprint now matches JLCPCB C431540 exactly
    "J3": (0, -3.5),     # JST PH 2P: model origin offset from pad center at 180° rotation
    # J5 PJ-327A: the footprint origin is the jack's FRONT FACE (so the
    # board-edge placement math stays readable); the CPL wants the pad
    # centroid, 6.0mm inboard and 0.4mm east (3 of the 5 pads sit on
    # the +x column). Verify on the JLC 3D preview at order time
    # (first-article-check, orientation family: connector).
    "J5": (0.4, -6.0),
}

# ── Per-component rotation DELTAS (added on top of the formula) ──
#
# These are ADDITIVE corrections, not absolute angles. Read this before
# touching an entry.
#
# This table used to be `_JLCPCB_ROT_OVERRIDES` and it returned an ABSOLUTE
# CPL angle, discarding `rot` and `layer` entirely. That is how D1 was able
# to carry a frozen 270° that was 180° out for months: the emitted angle no
# longer tracked the placement. Rotating an overridden part in the layout
# changed the copper but NOT the CPL, so the part would be assembled at the
# old orientation with no gate able to notice.
#
# As deltas, a layout rotation propagates automatically and the entry keeps
# meaning one thing only: "this LCSC part's tape orientation differs from
# what the package-family formula predicts, by exactly this much".
#
# Converted 2026-07-25. The emitted CPL is byte-identical to the previous
# absolute table — verified against release_jlcpcb/cpl.csv.
#
# "U5" entry REMOVED in the same change: PAM8403 (C5122557) is SOP-16, the
# formula already yields 180° via the `^SOP-` → 270 correction, and the old
# absolute override restated that same 180°. Its delta was 0, i.e. it was
# dead code that also skewed verify_dfa's effective-rotation comparison by
# subtracting a compensation that never existed.
_JLCPCB_ROT_DELTAS = {
    # J4 (FPC-40P, C2856812) — KEPT, emitted cpl = 270.
    #
    # This entry was briefly deleted on the theory that its justification was
    # only an eyeballed 3D overlay (404f31a) and that the rotation law's 90
    # should win. That was wrong, and it is recorded here so the same removal
    # is not attempted a third time. Two checks that do NOT depend on any
    # KiCad-to-JLCPCB angle convention:
    #
    #   1. Cable side. J4's contacts must face the FPC slot. On the copper the
    #      signal pads sit at LOWER x than the mount tabs — verify_dfm_v2's
    #      "J4 signal pads face toward FPC slot" asserts exactly that — and
    #      board.py puts FPC_SLOT at x 125.5-128.5 with J4's body at
    #      133.5-136.5, so the slot is on J4's -X side. At cpl=270 the
    #      contacts land on x=133.712 and the tabs on x=136.288: contacts
    #      toward the slot. At cpl=90 the two swap, and the ribbon would have
    #      to enter from +X, off the right board edge.
    #   2. Seating. Loading the LCSC reference into pcbnew, flipping to B.Cu
    #      and rotating, the matching orientation has a worst residual of
    #      0.002 mm across all 42 pads; the 180-away alternative contacts
    #      0 of 42 (a 2.576 mm contact/tab swap onto 1.0 mm pads).
    #
    # The convention that made 90 look right is the disputed one:
    # CPL_bottom = (180 - O) is what kicad-jlcpcb-tools (fabrication.py) and
    # KiBot (fil_rot_footprint, mirror_bottom) both implement, and it predicts
    # J4's 270 and U5's independently confirmed 180. Nothing implements the
    # CPL = -O that 90 would require.
    #
    # Do NOT confuse this with the connector_pad = 41 - panel_pin netlist
    # mapping in POLARITY_AUDIT.md. That one is correct and must not be
    # "fixed"; it is a different axis.
    "J4": 180,
    # "C2" override REMOVED: C2 (22uF tantalum, AMS1117 output cap) no longer
    # exists. It was the most dangerous polarized part on the board and it
    # destroyed prototype #1 when assembled reversed
    # (website/docs/rework/incident-c2-reversed.md). The SY8089 buck uses
    # C30, a non-polarized 22uF MLCC, on its output instead.
    # U3 needs NO override: footprints.sot23_5 is a verbatim copy of the
    # EasyEDA/JLCPCB reference land pattern for C78988 (delta_row = 0), so
    # the SOT-23-5 entry in _JLCPCB_ROT_CORRECTIONS (180) is sufficient.
    # D1 (BAT54C, C37704): override REMOVED 2026-07-25 — re-derived while
    # relocating D1 for R5-CRIT-6.
    #   Old state: KiCad rot 0° + override 270°.
    #
    #   The reference part is Q1 (P-MOSFET SOT-23-3; C10487 at the time,
    #   same package as today's AO3401A C15127) and ONLY Q1:
    #     * same library footprint — both use footprints.sot23_3()
    #     * same layer (bottom) and same KiCad rotation (0°) as D1 was
    #     * same EasyEDA land pattern, confirmed by LIVE refetch (the
    #       earlier HTTP 403 was transient rate-limiting from concurrent
    #       agents, not an outage — C37704 returns pad 1 (1.24, 0.95),
    #       pad 2 (1.24, -0.95), pad 3 (-1.24, 0), byte-identical to the
    #       archive in hardware/datasheets/POLARITY_AUDIT.md).
    #   Rigid-rotation fit of the FULL 3-pad constellation, centroid
    #   aligned, pin numbering PRESERVED (max pad error vs sot23_3()):
    #             rot   0°      90°       180°     270°
    #     C37704       2.210   0.187 ✓   2.210    3.120  mm
    #     C10487 (Q1)  2.074   0.000 ✓   2.074    2.933  mm
    #   Both land on the same 90°, and no pin PERMUTATION is required — so
    #   this is a drawing-convention difference between EasyEDA's library
    #   and ours, NOT a polarity defect. (Derived independently twice.)
    #   Q1 emits the plain formula result, 90°, with no override, and is
    #   empirically validated — boards R4-R8 (8+ prototypes) power up
    #   through Q1, so its physical polarity is proven. That evidence now
    #   lives in POLARITY_AUDIT.md; it used to sit in
    #   verify_easyeda_footprint.py's allowlist, but that entry was deleted
    #   once the computed proof above made it dead code.
    #   _jlcpcb_rotation() is linear in `rot`, so identical footprint +
    #   identical land pattern + identical layer ⇒ identical CPL angle.
    #   D1's 270° at KiCad 0° was therefore 180° out (introduced
    #   empirically in c7514e7 "180° → 270° per JLCPCB", no geometry).
    #   It was never caught by assembly because D1's anodes were unrouted
    #   on every board built so far — that is R5-CRIT-6 itself.
    #
    #   NOT a reference part: U4 (USBLC6-2SC6, C7519). An earlier version
    #   of this comment cited it as a second confirmation; that was wrong.
    #   Per POLARITY_AUDIT.md, C7519's EasyEDA footprint puts pads 1-2-3 on
    #   the TOP row (pad 1 at (-0.95,+1.15)), which MATCHES our sot23_6()
    #   (pad 1 at (-0.95,+1.10)) — no rotation offset, unlike D1/Q1. U4
    #   arrives at 90° by a different route and says nothing about D1.
    #
    #   Do NOT reason about this from row/column layout alone. EasyEDA
    #   simply draws SOT-23-3 with pads 1/2 in a column and SOT-23-6 with
    #   pads 1/2/3 in a row — an inconsistency internal to its own library.
    #   JLCPCB's 0° reference is the part's orientation in ITS parts library
    #   (tape-and-reel), which is why _JLCPCB_ROT_CORRECTIONS is keyed by
    #   package FAMILY and not by footprint drawing.
    #
    #   D1 is now placed at KiCad 180°, for which the same formula yields
    #   270° — the emitted CPL angle is unchanged, but it is now derived
    #   and the physical part finally matches its footprint.
    #   (EasyEDA could not be re-fetched live: the API returns HTTP 403 for
    #   every LCSC id, so scripts/.easyeda_cache/ cannot be repopulated —
    #   POLARITY_AUDIT.md is the archived copy of that reference.)
    # "LED2".."LED6" (C19171391) deltas REMOVED 2026-08-12 — the 180 was
    # the fourth wrong derivation of H6, and phase A on the v4.6.1 order
    # preview caught it before payment.
    #
    # What every derivation agreed on (and the cache proves): at the
    # part's own library zero the PHYSICAL CATHODE (green mark, silk
    # notch, model colour patch) is on the LEFT (-x) end. Our copper
    # wants the cathode on the LEFT pad (GND) for every LED_0805 on this
    # board. So the part is already correct at the family formula's 0°.
    #
    # The 180 rested on "opposite pin-1 conventions force a 180° CPL
    # delta". That premise silently assumes the machine aligns THEIR pin
    # number 1 onto OUR pad number 1. Nothing in the chain does that:
    # the CPL angle is a rigid rotation of the part from its library
    # zero (the same purely geometric semantics the J4 entry above
    # documents for kicad-jlcpcb-tools and KiBot — no term in the
    # formula reads our pad numbers, which exist only to bind nets in
    # KiCad). Pin NUMBERS are labels; only geometry is assembled. The
    # two vendors number the same physical layout oppositely, so the
    # numbering difference needs NO compensation — with 180 applied the
    # cathode lands on LEDn_RA (the anode net) and all five LEDs are
    # reverse-biased and dark.
    #
    # Evidence chain (2026-08-12, hardware-audit-bugs.md R33 phase A):
    #   1. Cache geometry: C19171391 pad2/cathode at x=-1.05, silk and
    #      3D colour patch at the same -x end (H6's own table).
    #   2. JLC order-preview render at CPL 180 shows the green cathode
    #      mark on the +x / LEDn_RA end for LED2-LED6 — the composed
    #      their-zero + CPL-angle frame, i.e. what the machine builds.
    #   3. The viewer's fidelity is hardware-anchored by U2: its render
    #      reproduces the proto #1/#2-confirmed ESOP-8 orientation.
    #   4. The two prior 180 justifications contradict each other on the
    #      datasheet (gate: "pin 1 = cathode, author error" vs H6: "pin
    #      1 = anode, no error") while agreeing on the number — a
    #      conclusion that survives its premise flipping is not derived.
    # Empirical confirmation pending on the first v4.6.2 article:
    # verify_easyeda_footprint._PENDING_VALIDATION carries the LED2-6
    # entries and the exact power-up test. If they come back dark, the
    # delta returns AND this comment gets a fifth chapter.
}

# Diagnostic-LED series resistors. Both values were ALREADY on the BOM, so
# the bank adds zero new part numbers — only quantity on two existing lines.
# Red C19171391 at these currents sits around Vf = 2.0 V:
#   5.1 k on a 5 V rail  -> (5.000 - 2.0) / 5100 = 0.59 mA   (C27834, R1/R2)
#   1 k   on +3V3        -> (3.327 - 2.0) / 1000 = 1.33 mA   (C17513, R17/R18)
# 1 k on the 5 V rails would have been 2.9 mA — above the 2 mA ceiling for
# parts meant to be DNP-able bench indicators, and 3x the drain budget.
# 10 k on +3V3 would have been 0.13 mA, below the visibility floor.
DIAG_R_VALUES = {"R28": "5.1k", "R29": "5.1k", "R30": "1k", "R31": "1k"}


def _jlcpcb_rotation(rot, layer, footprint_name, ref=None):
    """Compute JLCPCB CPL rotation from KiCad rotation.

    The placement formula always runs; a `_JLCPCB_ROT_DELTAS` entry is then
    ADDED to its result. Nothing bypasses the formula, so the emitted angle
    always tracks the part's rotation in the layout.
    """
    if layer != "bottom":
        angle = rot % 360  # Top side: no mirror, no package correction
    else:
        # Bottom-side mirror (community-validated formula)
        angle = (rot - 180) % 360

        # Per-footprint correction (from database)
        correction = _JLCPCB_ROT_DEFAULT
        for pattern, corr in _JLCPCB_ROT_CORRECTIONS:
            if re.match(pattern, footprint_name):
                correction = corr
                break
        angle = (angle + correction) % 360

    # Per-part tape-orientation delta, applied on top of the formula
    if ref:
        angle = (angle + _JLCPCB_ROT_DELTAS.get(ref, 0)) % 360

    return angle


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
    p.append(("LED2", "Red",  # C19171391 is red (YLED0805R); "Green" was a BOM-label error
              "LED_0805", x, y, 0, "top"))

    # Diagnostic LED bank (workstream H) — TOP side, two rows. The series
    # resistors are on the top side too, which makes them the only top-side
    # resistors on the board; see routing/_shared.py DIAG_* for why B.Cu was
    # not an option here.
    from scripts.generate_pcb.routing import DIAG_LEDS, DIAG_X, DIAG_R_Y, DIAG_LED_Y
    for _r, _led, _rail, _ra, _lbl in DIAG_LEDS:
        p.append((_r, DIAG_R_VALUES[_r], "R_0805",
                  DIAG_X[_r], DIAG_R_Y, 180, "top"))
        p.append((_led, "Red", "LED_0805",
                  DIAG_X[_r], DIAG_LED_Y, 0, "top"))

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
    p.append(("SW16", "SS-12D00G3",
              "SS-12D00G3", x, y, 0, "bottom"))

    # Speaker (SPK1) — manual assembly, not in BOM, excluded from CPL

    # IP5306 power IC (moved left to avoid slot)
    ix, iy = enc_to_pcb(*IP5306_ENC)
    p.append(("U2", "IP5306",
              "ESOP-8", ix, iy, 0, "bottom"))

    # U3 SY8089AAAC synchronous buck (SOT-23-5), replaces the AMS1117 LDO.
    # rot 180 puts IN/FB on the west side, inside the In2.Cu +5V pour.
    bkx, bky = enc_to_pcb(*BUCK_ENC)
    p.append(("U3", "SY8089AAAC",
              "SOT-23-5", bkx, bky, 180, "bottom"))

    # PAM8403 audio amp (rotated 90° for routing to speaker below)
    px, py = enc_to_pcb(*PAM8403_ENC)
    p.append(("U5", "PAM8403",
              "SOP-16", px, py, 90, "bottom"))

    # Inductor (near IP5306)
    lx, ly = enc_to_pcb(*INDUCTOR_ENC)
    p.append(("L1", "1uH",
              "SMD-4x4x2", lx, ly, 0, "bottom"))

    # L2: SY8089 buck output inductor (2.2uH, SWPA4030S2R2MT / C36409)
    from scripts.generate_pcb.routing import L2_POS
    p.append(("L2", "2.2uH",
              "IND-SMD-4.0x4.0", L2_POS[0], L2_POS[1], 0, "bottom"))

    # JST battery connector
    jx, jy = enc_to_pcb(*JST_BAT_ENC)
    p.append(("J3", "JST-PH-2P-SMD",
              "JST-PH-2P-SMD", jx, jy, 180, "bottom"))

    # Reset and Boot buttons (back side, right of USB-C)
    from scripts.generate_pcb.board import RESET_ENC, BOOT_ENC
    x, y = enc_to_pcb(*RESET_ENC)
    p.append(("SW15", "SW_Push",
              "SW-SMD-5.1x5.1", x, y, 0, "bottom"))
    x, y = enc_to_pcb(*BOOT_ENC)
    p.append(("SW14", "SW_Push",
              "SW-SMD-5.1x5.1", x, y, 0, "bottom"))

    # BAT54C dual Schottky diode — menu combo (START+SELECT).
    # Rotation must track board.py / routing._init_pads(): D1 is placed at
    # 180° so the SOT-23 two-pad row faces the BTN_START / BTN_SELECT
    # columns (R5-CRIT-6 relocation).
    p.append(("D1", "BAT54C",
              "SOT-23", D1_POS[0], D1_POS[1], D1_ROT, "bottom"))

    # P-MOSFET reverse polarity protection (v4.0)
    from scripts.generate_pcb.routing import Q1_POS, Q1_ROT, R24_POS, R24_ROT
    # Q1_ROT is 180, not 0: the drain has to face the cell (R31-HIGH-1).
    # That is the same KiCad angle as D1, the board's other SOT-23-3, so
    # both leave here at cpl 90 through the "^SOT-23" correction.
    p.append(("Q1", "AO3401A",
              "SOT-23", Q1_POS[0], Q1_POS[1], Q1_ROT, "bottom"))
    p.append(("R24", "100k", "R_0805",
              R24_POS[0], R24_POS[1], R24_ROT, "bottom"))

    # ── Passive components (back side) ────────────────────────────
    # All passives have >= 3mm center-to-center spacing.
    # Layout rows (Y increases downward in KiCad):
    #   y=35   IP5306 support caps (C17)
    #   y=37.5 IP5306 support caps (C18)
    #   y=42   ESP32 decoupling (C3, C4)
    #   y=46   Pull-up resistors (R4-R15) x=43..98
    #   y=50   Debounce caps (C5-C16) x=43..98
    # R9-MED-4 (2026-04-11): R19 and C20 removed — they were on the dead
    # BTN_MENU net never wired to MENU_K. Menu button works via D1 OR-gate.

    # USB-C CC resistors — use actual routing.py positions
    from scripts.generate_pcb.routing import R1_POS, R2_POS
    p.append(("R1", "5.1k", "R_0805",
              R1_POS[0], R1_POS[1], 0, "bottom"))
    p.append(("R2", "5.1k", "R_0805",
              R2_POS[0], R2_POS[1], 0, "bottom"))

    # USB ESD protection — TVS + 22Ω series resistors
    from scripts.generate_pcb.routing import U4_POS, R22_POS, R23_POS
    p.append(("U4", "USBLC6-2SC6", "SOT-23-6",
              U4_POS[0], U4_POS[1], 0, "bottom"))
    p.append(("R22", "22", "R_0402",
              R22_POS[0], R22_POS[1], 90, "bottom"))
    p.append(("R23", "22", "R_0402",
              R23_POS[0], R23_POS[1], 90, "bottom"))

    # ESP32 decoupling (y=42, below ESP32 body edge at 40.25)
    p.append(("C3", "100nF", "C_0805", 69.5, 42, 0, "bottom"))  # DFM: synced with board.py
    p.append(("C4", "100nF", "C_0805", 92, 42, 0, "bottom"))  # DFM: synced with board.py
    from scripts.generate_pcb.routing import C26_POS
    p.append(("C26", "100nF", "C_0805",
              C26_POS[0], C26_POS[1], 90, "bottom"))  # ESP32 VDD bypass

    # EN RC delay network (R25-CRIT-1 respin fix): 10k pull-up + 100nF
    # reset cap on the EN trace east of U1 pin 3 (module datasheet p.28
    # figure 7). Positions from routing to stay board.py-synced.
    from scripts.generate_pcb.routing import R3_POS, C31_POS
    p.append(("R3", "10k", "R_0805",
              R3_POS[0], R3_POS[1], 90, "bottom"))   # EN pull-up to +3V3
    p.append(("C31", "100nF", "C_0805",
              C31_POS[0], C31_POS[1], 90, "bottom"))  # EN reset cap to GND

    # Backlight series resistor (R25-HIGH-1 respin fix): LED-A now fed
    # from +5V through 20R so the backlight current is defined (~90 mA
    # for the 6-LED family class).
    from scripts.generate_pcb.routing import R27_POS
    p.append(("R27", "20", "R_1206",
              R27_POS[0], R27_POS[1], 90, "bottom"))

    # VBUS PTC fuse (R3-HIGH-4 fix): in series between J1 and IP5306 VIN
    # (hold 2A / trip 4A — the IP5306 charges at ~2A from a 5V source).
    from scripts.generate_pcb.routing import F1_POS
    p.append(("F1", "2A", "F_1812",
              F1_POS[0], F1_POS[1], 270, "bottom"))

    # LED current-limiting resistors (B.Cu, above LEDs on F.Cu)
    # Must match board.py: R17 at (25, 65), R18 at (32, 65)
    p.append(("R17", "1k", "R_0805", 25, 65, 0, "bottom"))
    p.append(("R18", "1k", "R_0805", 32, 65, 0, "bottom"))

    # ── Button pull-up resistors (y=46, x=43..98, 5mm spacing) ──
    # Shifted left to avoid IP5306 at x=110
    # R14 is DNP (GPIO45/BTN_L strapping pin — internal pull-up used instead)
    # R9-MED-4: R19 deleted (was on dead BTN_MENU net).
    pull_up_refs = [f"R{i}" for i in range(4, 16)]
    for i, ref in enumerate(pull_up_refs):
        if ref == "R14":
            continue  # DNP: GPIO45 VDD_SPI strapping, no external pull-up
        p.append((ref, "10k", "R_0805",
                  43 + i * 5, 46, 0, "bottom"))

    # ── SW16 respin: Q2 high-side +5V load switch + gate network ──
    # R16 (the old 100k IP5306_KEY pull-up to +5V) is DELETED — on the new
    # LOAD-side +5V it would have inverted into a pull-DOWN in the OFF
    # state and held KEY asserted. C33 takes over its site.
    #
    # SW17 is deliberately ABSENT from this list. It is the DNP manual KEY
    # wake button: its footprint and copper exist so the C33 RC can be
    # bypassed on the bench, but JLCPCB must not populate it, and the CPL
    # is the file that decides that. It is carried in the BOM marked DNP
    # (see the DNP block in the BOM writer) and nowhere else.
    from scripts.generate_pcb.routing import (
        Q2_POS, Q2_ROT, R32_POS, R32_ROT, C32_POS, C32_ROT,
        R33_POS, R33_ROT, R34_POS, R34_ROT, C33_POS, C33_ROT,
    )
    p.append(("Q2", "AO3401A", "SOT-23-3", *Q2_POS, Q2_ROT, "bottom"))
    p.append(("R32", "22k", "R_0805", *R32_POS, R32_ROT, "bottom"))
    p.append(("C32", "1uF", "C_0805", *C32_POS, C32_ROT, "bottom"))
    p.append(("R33", "1k", "R_0805", *R33_POS, R33_ROT, "bottom"))
    p.append(("R34", "1M", "R_0805", *R34_POS, R34_ROT, "bottom"))
    p.append(("C33", "4.7uF", "C_0805", *C33_POS, C33_ROT, "bottom"))

    # ── Button debounce caps (y=50, x=43..98, 5mm spacing) ──
    # R9-MED-4: C20 deleted (was on dead BTN_MENU net).
    debounce_refs = [f"C{i}" for i in range(5, 17)]
    for i, ref in enumerate(debounce_refs):
        p.append((ref, "100nF", "C_0805",
                  43 + i * 5, 50, 0, "bottom"))

    # ── IP5306 support caps (away from mounting hole at 105,37.5) ──
    p.append(("C17", "10uF", "C_0805", 110, 35, 0, "bottom"))
    p.append(("C18", "10uF", "C_0805", 116, 49, 0, "bottom"))  # BAT decoupling near IP5306
    p.append(("C27", "10uF", "C_0805", 108, 39, 0, "bottom"))  # VOUT HF decoupling near IP5306
    # C28 REMOVED from assembly: was at (86,26) UNDER ESP32 module body.
    # Local decoupling = C3+C4+C26 (300nF); rail bulk = C30 (22uF MLCC at
    # the buck output). NB the original justification cited "C2 22uF
    # tantalum", a part deleted in the SY8089 redesign — the ESP32-local
    # bulk gap is a RECORDED as-built limitation (known-issues RESPIN,
    # verify_decoupling_adequacy tracks it against the DNP list).
    # Relocate in v2 PCB respin to a position outside module footprint —
    # that relocation also resolves the vbench D5 dispute on C28.

    # C19 near inductor L1
    p.append(("C19", "22uF", "C_1206",
              lx, ly + 6, 0, "bottom"))

    # ── Headphone jack (J5) + auto-mute chain ──
    # Positions live in routing/_shared.py (single source, same values
    # board.py places). J5 rot 180 = front face on the bottom board
    # edge, barrel overhanging like J1.
    from scripts.generate_pcb.routing import (
        J5_POS, J5_ROT, Q3_POS, Q3_ROT,
        R35_POS, R36_POS, C34_POS, C35_POS, R39_POS,
        R37_POS, R38_POS, R40_POS,
    )
    p.append(("J5", "PJ-327A", "PJ-327A", *J5_POS, J5_ROT, "bottom"))
    p.append(("Q3", "2N7002", "SOT-23-3", *Q3_POS, Q3_ROT, "bottom"))
    p.append(("R35", "150R", "R_0805", *R35_POS, 90, "bottom"))
    p.append(("R36", "470R", "R_0805", *R36_POS, 90, "bottom"))
    p.append(("C34", "47nF", "C_0805", *C34_POS, 90, "bottom"))
    p.append(("C35", "47uF", "C_0805", *C35_POS, 90, "bottom"))
    p.append(("R39", "4.7k", "R_0805", *R39_POS, 90, "bottom"))
    p.append(("R37", "33R", "R_0805", *R37_POS, 0, "bottom"))
    p.append(("R38", "33R", "R_0805", *R38_POS, 180, "bottom"))
    p.append(("R40", "220k", "R_0805", *R40_POS, 90, "bottom"))

    # ── PAM8403 passives (B.Cu, around U5) ──
    p.append(("C21", "100nF", "C_0805", 38.0, 23.5, 0, "bottom"))
    p.append(("C22", "0.47u", "C_0805", 33.175, 20.0, 90, "bottom"))
    p.append(("C23", "1uF", "C_0805", 38.0, 29.5, 90, "bottom"))
    p.append(("C24", "1uF", "C_0805", 29.365, 22.0, 90, "bottom"))
    p.append(("C25", "1uF", "C_0805", 31.5, 37.5, 90, "bottom"))
    p.append(("R20", "20k", "R_0805", 38.0, 26.5, 0, "bottom"))
    p.append(("R21", "20k", "R_0805", 38.0, 32.5, 0, "bottom"))

    # ── U3 SY8089 buck passives ──
    # C2 (22uF tantalum) is GONE: it was the AMS1117 output cap and it
    # destroyed prototype #1 when assembled reversed. A 1 MHz buck needs a
    # low-ESR MLCC (C30) anyway — 2.9 ohm ESR tantalum is unusable here.
    from scripts.generate_pcb.routing import (
        C1_POS, C29_POS, C30_POS, R25_POS, R26_POS,
    )
    p.append(("C1", "22uF", "C_1206",
              C1_POS[0], C1_POS[1], 180, "bottom"))    # C_IN  (datasheet: >=10uF ceramic on IN)
    p.append(("C30", "22uF", "C_1206",
              C30_POS[0], C30_POS[1], 90, "bottom"))   # C_OUT (datasheet: >=22uF X5R ceramic)
    p.append(("R25", "100k", "R_0805",
              R25_POS[0], R25_POS[1], 180, "bottom"))    # FB upper
    p.append(("R26", "22k", "R_0805",
              R26_POS[0], R26_POS[1], 180, "bottom"))    # FB lower -> 0.6*(1+100/22)=3.327V
    p.append(("C29", "22pF", "C_0805",
              C29_POS[0], C29_POS[1], 180, "bottom"))    # feed-forward across R25

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
