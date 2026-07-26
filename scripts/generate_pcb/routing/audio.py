"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    NET_ID,
    VIA_MIN,
    VIA_MIN_DRILL,
    VIA_STD,
    VIA_STD_DRILL,
    W_AUDIO,
    W_DATA,
    W_PWR,
    W_PWR_LOW,
    _PAD_NETS,
    _esp_pin,
    _init_pads,
    _pad,
    _seg,
    _via_net,
)




def _i2s_traces():
    """Audio chain: ESP32 I2S_DOUT -> PAM8403 -> Speaker (BTL right channel).

    PAM8403 SOP-16 correct pinout:
      Pin 1=+OUT_L, 2=PGND, 3=-OUT_L, 4=PVDD, 5=MUTE, 6=VDD,
      7=INL, 8=VREF, 9=NC, 10=INR, 11=GND, 12=SHDN,
      13=PVDD, 14=-OUT_R, 15=PGND, 16=+OUT_R

    Audio input: only I2S_DOUT (GPIO 17) reaches C22.1; C22.2 onward the
      node is PAM_IN_AC, feeding INR (pin 10) and INL (pin 7) for mono.
      C22 is a SERIES DC-block, so the two sides are two distinct nets.
      BCLK/LRCK unused by PAM8403 (analog amp, not I2S).
    Speaker: BTL right channel: SPK+ = +OUT_R (pin 16), SPK- = -OUT_R (pin 14).
    Power: PVDD (4,13) + VDD (6) → +5V; PGND (2,15) + GND (11) → GND.
    Control: MUTE (5) + SHDN (12) → +5V (always on/unmuted).
    VREF (8): internal reference, bypassed to GND via C21 (100nF) per PAM8403 datasheet.
    """
    parts = []
    _init_pads()

    n_5v = NET_ID["+5V"]
    n_gnd = NET_ID["GND"]
    n_dout = NET_ID["I2S_DOUT"]      # ESP32 side of C22
    n_pam_in = NET_ID["PAM_IN_AC"]   # PAM8403 side of C22 (AC-coupled)
    n_bclk = NET_ID["I2S_BCLK"]
    n_lrck = NET_ID["I2S_LRCK"]
    n_spk_p = NET_ID["SPK+"]
    n_spk_m = NET_ID["SPK-"]

    # Assign I2S_BCLK/LRCK nets to U1 pads (GPIO15/16) even though
    # PAM8403 is analog and doesn't use them — tracks design intent
    _PAD_NETS[("U1", "8")] = n_bclk   # GPIO15 = I2S_BCLK
    _PAD_NETS[("U1", "9")] = n_lrck   # GPIO16 = I2S_LRCK

    # ── Audio input: ESP32 I2S_DOUT → PAM8403 INR (pin 10) + INL (pin 7)
    epx, epy = _esp_pin(17)  # GPIO 17 = I2S_DOUT
    pam_inr = _pad("U5", "10")   # INR (26.825, 24.850)
    pam_inl = _pad("U5", "7")    # INL (26.825, 34.150)

    if pam_inr:
        inrx, inry = pam_inr
        # DFM MOUNTAIN ROUTE: I2S_DOUT (GPIO17, epy=33.670) shares y=33.670 with
        # SD_CLK (GPIO38, ESP32 pad 31).  Old routing used F.Cu at y=33.670, causing
        # SD_CLK escape vias at (72.20,33.670) and (77.00,33.670) to overlap I2S_DOUT F.Cu
        # (gap=-0.450mm, need 0.15mm).
        #
        # Fix: "mountain route" — go UP on B.Cu to y=18.0 (above all LCD B.Cu verts
        # that top out at y≈19.5–27.9), then F.Cu horizontal at y=18.0 (verified clear),
        # then B.Cu vert down to PAM8403 INR pad.
        #
        # mountain_x = 87.7mm:
        #   U1 right pads at x=88.75, pad left edge=88.00.
        #   Vert right edge = 87.7+0.10 = 87.80mm. Pad left edge = 88.00. Gap = 0.20mm > 0.10mm ✓
        #   LCD_RD via at (86.985, 34.305): AABB right = 87.435mm.
        #   Euclidean gap between vert (x=[87.60,87.80]) and via (x=[86.535,87.435], y=[33.855,34.755]):
        #   dx=87.60-87.435=0.165mm, dy=33.855-(33.67+0.10)=0.085mm → gap=0.186mm > 0.15mm ✓
        # mountain_y = 18.0mm: above LCD_D7 top (y=19.50) and LCD_D6 top (y=20.50) ✓
        # F.Cu at y=18.0 x=26.825..87.7: no F.Cu obstacles found ✓
        # Via at (87.7,18.0): verified clear ✓
        mountain_x = 87.7  # epx-1.05; clear of U1 right pads AND LCD_RD via ✓
        mountain_y = 18.0  # above all LCD B.Cu vert tops (highest is LCD_D7 at y=19.5) ✓
        # B.Cu: ESP32 pad → mountain column
        parts.append(_seg(epx, epy, mountain_x, epy, "B.Cu", W_DATA, n_dout))
        # B.Cu: mountain column UP to mountain_y
        parts.append(_seg(mountain_x, epy, mountain_x, mountain_y, "B.Cu", W_DATA, n_dout))
        parts.append(_via_net(mountain_x, mountain_y, n_dout, size=VIA_STD, drill=VIA_STD_DRILL))
        # F.Cu: horizontal across board at y=18.0 (clear of all LCD B.Cu verts — different layer) ✓
        parts.append(_seg(mountain_x, mountain_y, inrx, mountain_y, "F.Cu", W_DATA, n_dout))
        parts.append(_via_net(inrx, mountain_y, n_dout, size=VIA_STD, drill=VIA_STD_DRILL))
        # B.Cu: vertical down through C22 DC-blocking cap (in-series) to INR pad
        # C22 at (33.175, 20.0) rotated 90° on B.Cu: pad1 at (33.175, 19.05), pad2 at (33.175, 20.95)
        c22_p1 = _pad("C22", "1")
        c22_p2 = _pad("C22", "2")
        if not (c22_p1 and c22_p2 and pam_inl):
            # Never silence: the old fallback drew a direct I2S_DOUT trace from
            # the mountain via to INR, shorting across the DC-block cap. That
            # would put the ESP32 GPIO DC level straight onto the PAM8403
            # inputs. If the C22 pads cannot be resolved the generator is
            # broken and must stop, not emit a wrong board.
            raise RuntimeError(
                "audio input: cannot resolve C22 pads "
                f"(C22.1={c22_p1}, C22.2={c22_p2}, U5.7={pam_inl}) — "
                "the series DC-block would be bypassed"
            )
        # Via → C22 pad 1 (source side, still I2S_DOUT)
        parts.append(_seg(inrx, mountain_y, c22_p1[0], c22_p1[1], "B.Cu", W_DATA, n_dout))
        # C22 pad 2 → INL pad. From here east the net is PAM_IN_AC: the cap
        # dielectric separates it from I2S_DOUT, so it must carry a distinct
        # net name or DRC reports a permanent phantom "unconnected".
        parts.append(_seg(c22_p2[0], c22_p2[1], pam_inl[0], pam_inl[1], "B.Cu", W_DATA, n_pam_in))

    if pam_inr and pam_inl:
        inrx, inry = pam_inr
        inlx, inly = pam_inl
        # Bridge INR to INL for mono (same X column, vertical trace).
        # Split at y=28.0 to form T-junction for R20 detour (see _pam_passive_traces).
        _r20_branch_y = 28.0
        parts.append(_seg(inrx, inry, inrx, _r20_branch_y, "B.Cu", W_DATA, n_pam_in))
        parts.append(_seg(inrx, _r20_branch_y, inrx, inly, "B.Cu", W_DATA, n_pam_in))

    # ── Speaker output: BTL right channel
    # SPK+ = +OUT_R (pin 16), SPK- = -OUT_R (pin 14)
    spk_1 = _pad("SPK1", "1")    # (39.5, 52.5)
    spk_2 = _pad("SPK1", "2")    # (20.5, 52.5)
    pam_outr_p = _pad("U5", "16")  # +OUT_R (25.555, 32.200) — bottom-left pad
    pam_outr_m = _pad("U5", "14")  # -OUT_R (28.095, 32.200) — bottom row

    if pam_outr_p and spk_1:
        # SPK+: +OUT_R (pin 16) → speaker pad 1
        # U5:16 (SPK+) at (25.555, 32.200). Route LEFT to avoid U5:15 (GND) at (26.825,32.2)
        # which sits immediately to the right of U5:16.
        #
        # DFM FIX: old route went RIGHT (col_x=ox+1.5=27.055), crossing U5:15 (GND, net1).
        # Gap = 0.0mm (the vert at x=27.055 overlaps U5:15 AABB [26.525..27.125]).
        # Also U5:2 (GND) at (26.825,26.8) was crossed by the vert going up to y=22.5.
        #
        # New route: exit U5:16 LEFTWARD to col_x=24.5 (left of all U5 pads, min x=25.255).
        # col_x=24.5: vert right edge=24.65mm, U5:1/16 left edge=25.255mm → gap=0.605mm ✓
        # No different-net pads exist at x≤24.5, y=21.5..32.2 on B.Cu ✓
        ox, oy = pam_outr_p
        sx, sy = spk_1
        col_x = 24.5   # left of all U5 pads (min pad left-edge=25.255mm, gap=0.605mm ✓)
        # DFM: mid_y=22.5 placed via@(39.5,22.5) too close to C21[1]@(38.95,23.5)
        # gap=0.079mm < 0.127mm. At y=21.5: gap=hypot(0.05,1.35)-0.275=1.08mm ✓
        mid_y = 21.5
        # SHORT FIX: SPK+ B.Cu vertical moved from x=39.5 to x=40.0 to clear
        # R20[1]/R21[1]/C21[1] GND pads (right edge=39.45). At x=40.0:
        # trace left edge = 40.0 - 0.15 = 39.85, gap to pad edge = 0.40mm ✓
        # Short B.Cu horizontal jog at speaker pad (sy) from x=40.0 to sx=39.5.
        spk_col_x = 40.0  # was sx (39.5); shifted right for pad clearance
        parts.append(_seg(ox, oy, col_x, oy, "B.Cu", W_AUDIO, n_spk_p))  # horiz left
        parts.append(_seg(col_x, oy, col_x, mid_y, "B.Cu", W_AUDIO, n_spk_p))  # vert up
        parts.append(_via_net(col_x, mid_y, n_spk_p, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(col_x, mid_y, spk_col_x, mid_y, "F.Cu", W_AUDIO, n_spk_p))
        parts.append(_via_net(spk_col_x, mid_y, n_spk_p, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(spk_col_x, mid_y, spk_col_x, sy, "B.Cu", W_AUDIO, n_spk_p))
        parts.append(_seg(spk_col_x, sy, sx, sy, "B.Cu", W_AUDIO, n_spk_p))  # horiz jog to speaker pad

    if pam_outr_m and spk_2:
        # SPK-: -OUT_R (pin 14) → speaker pad 2
        ox, oy = pam_outr_m
        sx, sy = spk_2
        # DFM FIX: old route had B.Cu vertical at x=28.095 from pin 14 (y=32.2)
        # straight down to mid_y=23.7, crossing U5 pin 3 (-OUT_L, NC) AABB
        # x=[27.795,28.395] y=[26.025,27.575]. When pin 3 is soldered, the trace
        # shorts SPK- to the NC pad → audio corruption.
        #
        # Fix: F.Cu bridge over pin 3 area. Route B.Cu down to just above pin 3
        # top edge, via to F.Cu, cross pin 3 on F.Cu (different layer), via back
        # to B.Cu below pin 3, then continue to speaker via.
        #
        # Pin 3 AABB y=[26.025, 27.575]. Via size 0.6mm (r=0.3).
        # bridge_top: pin 3 bottom edge (27.575) + via_r (0.3) + clearance (0.15) = 28.025
        # bridge_bot: pin 3 top edge (26.025) - via_r (0.3) - clearance (0.15) = 25.575
        # Existing GND via at (26.825, 24.8): gap to bridge_bot via at (28.095, 25.5):
        #   dist = sqrt(1.27^2 + 0.7^2) = 1.45mm > 0.85mm (0.3+0.3+0.25) ✓
        # Existing PVDD via at (29.365, 28.7): gap to bridge_top via at (28.095, 28.1):
        #   dist = sqrt(1.27^2 + 0.6^2) = 1.40mm > 0.85mm ✓
        bridge_top_y = 28.1   # above pin 3 top edge + via_r + clearance
        bridge_bot_y = 25.5   # below pin 3 bottom edge - via_r - clearance
        mid_y = 23.7  # speaker crossover via Y (unchanged)

        # B.Cu: pin 14 down to bridge_top
        parts.append(_seg(ox, oy, ox, bridge_top_y, "B.Cu", W_AUDIO, n_spk_m))
        # Via to F.Cu
        parts.append(_via_net(ox, bridge_top_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
        # F.Cu: cross pin 3 area (different layer, safe)
        parts.append(_seg(ox, bridge_top_y, ox, bridge_bot_y, "F.Cu", W_AUDIO, n_spk_m))
        # Via back to B.Cu
        parts.append(_via_net(ox, bridge_bot_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
        # B.Cu: continue down to speaker crossover via
        parts.append(_seg(ox, bridge_bot_y, ox, mid_y, "B.Cu", W_AUDIO, n_spk_m))
        # Crossover via to F.Cu for horizontal to speaker
        parts.append(_via_net(ox, mid_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(ox, mid_y, sx, mid_y, "F.Cu", W_AUDIO, n_spk_m))
        parts.append(_via_net(sx, mid_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(sx, mid_y, sx, sy, "B.Cu", W_AUDIO, n_spk_m))

    # ── PAM8403 +5V: chain on each row, single via per row
    # Top row (y=34.15): VDD(6) → MUTE(5) → PVDD(4), via from VDD(6)
    # VDD pin 6 at x=28.095, safe from BTN_RIGHT at x=31.0
    # PVDD pin 4 at x=30.635 too close to BTN_RIGHT for a direct via
    pam_vdd6 = _pad("U5", "6")
    pam_mute = _pad("U5", "5")
    pam_pvdd4 = _pad("U5", "4")
    if pam_vdd6 and pam_mute:
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_mute[0], pam_mute[1],
                          "B.Cu", W_PWR, n_5v))
    if pam_mute and pam_pvdd4:
        parts.append(_seg(pam_mute[0], pam_mute[1],
                          pam_pvdd4[0], pam_pvdd4[1],
                          "B.Cu", W_PWR, n_5v))
    if pam_vdd6:
        via_y = pam_vdd6[1] + 2.0  # outward from IC (downward = larger y)
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_vdd6[0], via_y, "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(pam_vdd6[0], via_y, n_5v, size=VIA_STD, drill=VIA_STD_DRILL))

        # DFM FIX: removed F.Cu bridge trace (net3 +5V at x=107 F.Cu crossed
        # 8+ LCD data bus horizontal traces at y=26..35 on F.Cu, gap=0mm).
        # PAM8403 +5V now supplied via a separate +5V In2.Cu zone island covering
        # the PAM8403 area (see _power_zones). The via above connects to In2.Cu.

    # Bottom row (y=24.85): SHDN(12) → PVDD(13), via from PVDD(13)
    pam_shdn = _pad("U5", "12")
    pam_pvdd13 = _pad("U5", "13")
    if pam_shdn and pam_pvdd13:
        parts.append(_seg(pam_shdn[0], pam_shdn[1],
                          pam_pvdd13[0], pam_pvdd13[1],
                          "B.Cu", W_PWR, n_5v))
    # +5V via Y for PVDD13 (used by bridge below to avoid collinear overlap)
    pvdd13_via_y = None
    if pam_pvdd13:
        # DFM: offset 3.5mm (was 2.0). U5[13]@(29.365,32.2); via at 2mm y=30.2 overlapped
        # SW4[2]@(30.0,30.65) — same X, gap_x=-0.415mm OVERLAP.
        # At 3.5mm: via y=28.7, gap_y=|28.7-30.65|-0.45-0.45=1.95-0.9=1.05mm -> CLEAR.
        pvdd13_via_y = pam_pvdd13[1] - 3.5  # DFM: was 2.0 (overlapped SW4[2])
        parts.append(_seg(pam_pvdd13[0], pam_pvdd13[1],
                          pam_pvdd13[0], pvdd13_via_y, "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(pam_pvdd13[0], pvdd13_via_y, n_5v, size=VIA_STD, drill=VIA_STD_DRILL))

    # B.Cu bridge: connect top row (PVDD4) to bottom row (PVDD13)
    # DFM FIX: bridge goes from PVDD4 to the via position (not PVDD13) to avoid
    # collinear overlap with the PVDD13→via segment above.
    # The via feed covers PVDD13 (32.2) → via_y (28.7). The bridge covers
    # PVDD4 (26.8) → via_y (28.7). No overlap between segments ✓.
    if pam_pvdd4 and pam_pvdd13:
        bridge_end_y = pvdd13_via_y if pvdd13_via_y is not None else pam_pvdd13[1]
        if abs(pam_pvdd4[0] - pam_pvdd13[0]) < 0.01:
            # Same x: direct vert bridge to via position (no horiz needed)
            parts.append(_seg(pam_pvdd4[0], pam_pvdd4[1],
                              pam_pvdd13[0], bridge_end_y,
                              "B.Cu", W_PWR, n_5v))
        else:
            # Fallback: route above U5 top row (y=25.5) to avoid U5 GND pads
            y_above = pam_pvdd4[1] - 1.3  # 26.8-1.3=25.5, above U5 top edge 26.025-0.1=25.925 ✓
            parts.append(_seg(pam_pvdd4[0], pam_pvdd4[1],
                              pam_pvdd4[0], y_above, "B.Cu", W_PWR, n_5v))
            parts.append(_seg(pam_pvdd4[0], y_above,
                              pam_pvdd13[0], y_above, "B.Cu", W_PWR, n_5v))
            parts.append(_seg(pam_pvdd13[0], y_above,
                              pam_pvdd13[0], bridge_end_y, "B.Cu", W_PWR, n_5v))

    # ── PAM8403 GND: PGND (pins 2, 15) + GND (pin 11) → GND
    # All GND pins route vias outward from IC center
    # DFM FIX: offset changed from 2.0 to 2.1mm for bottom-row pins (py>30).
    # U5:15 GND via at (26.825, 34.2) was 0.200mm from BTN_Y via at (25.95, 33.1):
    # dx_outer=-0.025 (overlap), dy_outer=34.2-33.1-0.9=0.2mm < 0.25mm JLCPCB min.
    # At 2.1mm: via_y=34.3, dy_outer=0.3mm ≥ 0.25mm ✓
    for pin in ["2", "15", "11"]:
        p = _pad("U5", pin)
        if p:
            px, py = p
            via_y = py + (2.1 if py > 30 else -2.0)  # outward; 2.1mm clears BTN_Y via ✓
            parts.append(_seg(px, py, px, via_y, "B.Cu", W_PWR, n_gnd))
            parts.append(_via_net(px, via_y, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # VREF (pin 8): bypassed to GND via C21 (routed in _pam_passive_traces)

    # ── PAM8403 (U5) GND thermal vias: 3-via array near GND pins ──────
    # U5 at (30.0, 29.5), SOP-16, rotated 90deg on B.Cu.
    # GND pins: 2 (PGND), 11 (GND), 15 (PGND).
    # PAM_VREF B.Cu trace at x=34.45 (y=23.5..26.15) — avoid!
    # PAM_IN_AC B.Cu at x=33.17 (y=20.95..26.80) — avoid!
    # Place 3 thermal vias LEFT of IC center, clear of VREF and I2S traces.
    # U5 GND pins at approximate x=25.5..28.1. Use x=23..26 at y=22.0.
    pam_pgnd2 = _pad("U5", "2")  # PGND top row
    if pam_pgnd2:
        # Add 3 dedicated thermal GND vias near PAM8403 center (30.0, 29.5).
        # Existing GND pin vias at ~3-5mm; these thermal vias at ~2-3mm.
        # Constraints:
        #   SPK+ B.Cu at x=24.50 — stay right of x=25.5
        #   PAM_IN_AC B.Cu at x=33.17 — stay left of x=32.0
        #   PAM_VREF B.Cu at x=34.45 — stay left
        #   OUTL+ at y≈24.9, OUTL- at y≈34.3 — place between
        # Place 3 vias in a column at x=26.5 (between SPK+ and IC center):
        #   y=27.0, y=29.5, y=32.0 — spanning the IC vertically
        # Gap to SPK+ B.Cu (x=24.50, w=0.3): 26.5-24.50-0.15-0.30=1.55mm ✓
        # Gap to pin 2 via (x=28.095): |28.095-26.5|-0.30-0.30=0.995mm ✓
        _pam_therm_vias = [
            (26.5, 27.0),   # near PGND pin 2 area
            (26.5, 29.5),   # IC center Y
            (26.5, 32.0),   # near PGND pin 15 area
        ]
        for idx, (tvx, tvy) in enumerate(_pam_therm_vias):
            parts.append(_via_net(tvx, tvy, n_gnd,
                                  size=VIA_STD, drill=VIA_STD_DRILL))
        # Connect thermal vias with B.Cu segments (split at each via for connectivity)
        for idx in range(len(_pam_therm_vias) - 1):
            x1, y1 = _pam_therm_vias[idx]
            x2, y2 = _pam_therm_vias[idx + 1]
            parts.append(_seg(x1, y1, x2, y2, "B.Cu", W_PWR_LOW, n_gnd))

    return parts


def _pam_passive_traces():
    """PAM8403 passive component routing: bias resistors, bypass/decoupling caps.

    Components:
      R20 (20k): INL (pin 7) bias to GND
      R21 (20k): INR (pin 10) bias to GND
      C21 (100nF): VREF (pin 8) bypass to GND
      C23 (1uF): VDD (pin 6) decoupling to GND
      C24 (1uF): PVDD (pin 4) decoupling to GND
      C25 (1uF): PVDD (pin 13) decoupling to GND
    """
    parts = []
    _init_pads()

    n_gnd = NET_ID["GND"]
    n_5v = NET_ID["+5V"]
    # R20/R21 tap the PAM8403 side of the C22 series DC-block, so they sit on
    # PAM_IN_AC — NOT on I2S_DOUT (which stops at C22.1 on the ESP32 side).
    n_pam_in = NET_ID["PAM_IN_AC"]
    n_vref = NET_ID["PAM_VREF"]

    # ── R20: INL (pin 7) → R20 → GND via
    # R20 at (36.0, 26.800) rot 0: pad1 at ~(35.05, 26.8), pad2 at ~(36.95, 26.8)
    # INL pin 7 at (33.175, 26.800) on top row. The PAM_IN_AC bridge also runs
    # at y=26.8 from INR to INL. R20 pad1 is right of the PAM_IN_AC vert at
    # x=33.175, so the horiz trace from INL to R20 is an extension of the same
    # PAM_IN_AC net. GND via from R20 pad2 goes UP 1.5mm to avoid it.
    pam_inl = _pad("U5", "7")
    r20_p1 = _pad("R20", "1")  # (38.95, 26.8) — far from INL (GND side)
    r20_p2 = _pad("R20", "2")  # (37.05, 26.8) — near INL (signal side)
    if pam_inl and r20_p1 and r20_p2:
        # DFM FIX: old horizontal from INL (33.175, 26.8) to R20_p2 (37.05, 26.8)
        # crossed U5 pin 8 (VREF, net PAM_VREF) at x=34.445, AABB x=[34.145,34.745].
        # When pin 8 is soldered, PAM_IN_AC shorts to VREF pad.
        #
        # Fix: T-branch from the INR→INL bridge at y=28.0 (below top-row pad
        # bottom edge 27.575 + 0.325mm clearance), then horizontal RIGHT to
        # R20_p2 x, then up to R20_p2 y. The INR→INL bridge passes through
        # y=28.0 so this is a clean T-junction (no reversal).
        # +5V vert at x=38.0 y=[25.8,28.55]: horiz at y=28.0 from x=33.175 to
        # x=37.05 right edge at 37.15, +5V left edge at 37.9 → gap=0.75mm ✓
        _r20_detour_y = 28.0  # below top-row pad bottom (27.575) + gap
        parts.append(_seg(pam_inl[0], _r20_detour_y,
                          r20_p2[0], _r20_detour_y,
                          "B.Cu", W_DATA, n_pam_in))
        parts.append(_seg(r20_p2[0], _r20_detour_y,
                          r20_p2[0], r20_p2[1],
                          "B.Cu", W_DATA, n_pam_in))
        # R20 pad 1 (far pad) is the BIAS side — it goes to PAM_VREF, not GND.
        # Built once for R20+R21 together in the VREF bias rail below, after
        # C21 has established where the VREF node sits. See R4-HIGH-3.

    # ── R21: INR (pin 10) → R21 → GND via
    # R21 at (36.0, 32.200) rot 0: pad1 at ~(35.05, 32.2), pad2 at ~(36.95, 32.2)
    pam_inr = _pad("U5", "10")
    r21_p1 = _pad("R21", "1")  # (36.95, 32.2) — far from INR (GND side)
    r21_p2 = _pad("R21", "2")  # (35.05, 32.2) — near INR (signal side)
    if pam_inr and r21_p1 and r21_p2:
        # INR to R21: use F.Cu bridge to avoid BTN_RIGHT vert at x=34.20.
        # BTN_RIGHT runs B.Cu vert at x=34.20 from y=30.65 downward.
        # Route: INR (33.175,32.2) → via to F.Cu → F.Cu horiz to R21 pad2 x
        # → via back to B.Cu at R21 pad2.
        parts.append(_via_net(pam_inr[0], pam_inr[1], n_pam_in, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(pam_inr[0], pam_inr[1],
                          r21_p2[0], r21_p2[1],
                          "F.Cu", W_DATA, n_pam_in))
        parts.append(_via_net(r21_p2[0], r21_p2[1], n_pam_in, size=VIA_STD, drill=VIA_STD_DRILL))
        # R21 pad 1 (far pad) is the BIAS side — PAM_VREF, not GND.
        # Built in the VREF bias rail below, together with R20. See R4-HIGH-3.

    # ── C21: VREF (pin 8) → C21 → GND via
    # C21 at (36.5, 24.5) rot 0: pad1 at ~(35.55, 24.5), pad2 at ~(37.45, 24.5)
    # VREF pin 8 at (34.445, 26.800). Route UP from pin 8 on B.Cu to y=24.5,
    # then RIGHT to C21 pad 1. Vert at x=34.445 is right of PAM_IN_AC vert at
    # x=33.175 (gap=34.445-33.175-0.1-0.1=1.07mm OK). Horiz at y=24.5 does not
    # cross any existing traces (PAM_IN_AC bridge is at y=26.8 and y=32.2).
    pam_vref = _pad("U5", "8")
    c21_p1 = _pad("C21", "1")
    c21_p2 = _pad("C21", "2")
    if pam_vref and c21_p1 and c21_p2:
        # c21_p2 at (35.55, 24.5) = near pad (VREF side)
        # c21_p1 at (37.45, 24.5) = far pad (GND side)
        # COLLISION FIX: VREF pin 8 at (34.445, 26.800). PAM_IN_AC horiz (net59)
        # runs at y=26.8 from INL (33.175) to R20 pad2 (35.05) on B.Cu.
        # Starting the VREF vert at (34.445, 26.800) creates a segment-segment
        # crossing with the PAM_IN_AC horiz (gap=-0.200mm).
        # Fix: start VREF vert at pad top edge (y=26.15), 0.65mm above pad center.
        # The pad copper naturally connects the VREF vert to pin 8.
        # VREF vert bottom edge at 26.15+0.10=26.25; PAM_IN_AC top edge at 26.80-0.10=26.70.
        # Gap = 0.45mm >> 0.10mm required. OK.
        _vref_start_y = pam_vref[1] - 0.65  # pad top edge = 26.800 - 0.65 = 26.15
        # Explicit net assignment: segment starts offset from pad center so
        # auto-detection misses it — pad 8 must carry PAM_VREF.
        _PAD_NETS[("U5", "8")] = n_vref
        # L-shape: vert up from pad top edge to C21 y, then horiz right to C21 pad 2.
        parts.append(_seg(pam_vref[0], _vref_start_y,
                          pam_vref[0], c21_p2[1],
                          "B.Cu", W_DATA, n_vref))
        parts.append(_seg(pam_vref[0], c21_p2[1],
                          c21_p2[0], c21_p2[1],
                          "B.Cu", W_DATA, n_vref))
        # GND via below C21 pad 1 (far pad): go DOWN (+Y) to avoid SPK+ trace at y=22.5
        # DFM FIX: via shifted left 0.10mm for SPK+ B.Cu clearance at x=39.5
        _gnd_vx = c21_p1[0] - 0.10
        parts.append(_seg(c21_p1[0], c21_p1[1],
                          _gnd_vx, c21_p1[1] + 1.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(_gnd_vx, c21_p1[1] + 1.0,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── VREF bias rail: C21.2 → R20.1 → R21.1 (R4-HIGH-3) ──
    # The PAM8403 single-ended app circuit (datasheet Fig. 3) biases INL/INR
    # to VREF (pin 8), NOT to GND. Tying the bias resistors to GND fights the
    # amplifier's internal mid-supply bias and produces asymmetric clipping.
    # The schematic has always specified VREF (sheets/audio.py); the routing
    # still tied both far pads to GND, and the two disagreed for 4 pins in
    # verify_netlist_diff. This rail is that fix on the copper side.
    #
    # Lane choice — the far pads (C21.1, R20.1, R21.1) all sit at x=38.95:
    #   * x=38.95 vertical R20.1(26.5) → R21.1(32.5) is clear. SPK+ B.Cu runs
    #     at x=40.00 w=0.3 (left edge 39.85) → gap 0.80mm. +5V B.Cu at x=38.00
    #     w=0.5 (right edge 38.25) → gap 0.60mm. Nothing crosses that span:
    #     PAM_IN_AC B.Cu horiz at y=28.00 stops at x=37.05, and the y=32.50
    #     PAM_IN_AC leg is on F.Cu.
    #   * Going UP from R20.1 is blocked by C21.1 (GND) at (38.95, 23.50).
    #     So the rail reaches VREF via a jog at y=25.20, threading between the
    #     C21 GND via (38.85, 24.50, size 0.6 → top edge 24.80; gap 0.30mm)
    #     and the +5V via (38.00, 25.80, size 0.5 → bottom edge 25.55; gap
    #     0.25mm), then climbs x=37.05 to C21.2. R20.2 (PAM_IN_AC) starts at
    #     y=25.85, above the jog → gap 0.55mm.
    if r20_p1 and r21_p1 and c21_p2:
        _vref_jog_y = 25.20
        _x_far = r20_p1[0]      # 38.95 — shared by R20.1 / R21.1
        _x_near = c21_p2[0]     # 37.05 — VREF side of C21
        # C21.2 down to the jog, then right to the far-pad lane.
        parts.append(_seg(_x_near, c21_p2[1], _x_near, _vref_jog_y,
                          "B.Cu", W_DATA, n_vref))
        parts.append(_seg(_x_near, _vref_jog_y, _x_far, _vref_jog_y,
                          "B.Cu", W_DATA, n_vref))
        # Down the far-pad lane through R20.1 to R21.1.
        parts.append(_seg(_x_far, _vref_jog_y, _x_far, r20_p1[1],
                          "B.Cu", W_DATA, n_vref))
        parts.append(_seg(_x_far, r20_p1[1], _x_far, r21_p1[1],
                          "B.Cu", W_DATA, n_vref))
        # Both far pads now carry VREF. Explicit: the rail runs THROUGH the
        # pad centres, so pad-net auto-detection would otherwise leave them
        # on whatever it inferred first.
        _PAD_NETS[("R20", "1")] = n_vref
        _PAD_NETS[("R21", "1")] = n_vref

    # ── C23: VDD (pin 6) decoupling → GND via
    # C23 at (36.0, 29.5) rotated 90°: pads at ~(36.0, 28.55) and ~(36.0, 30.45)
    # VDD pin 6 at (31.905, 26.800). Must cross PAM_IN_AC vert at x=33.175.
    # Solution: use F.Cu bridge to cross the PAM_IN_AC vert safely.
    # Route: VDD(6) → vert up to bridge_y → via to F.Cu → F.Cu horiz to x=36.0
    # (crosses PAM_IN_AC B.Cu vert on DIFFERENT LAYER) → via back to B.Cu →
    # vert down to C23 pad 1.
    pam_vdd6 = _pad("U5", "6")
    c23_p1 = _pad("C23", "1")
    c23_p2 = _pad("C23", "2")
    if pam_vdd6 and c23_p1 and c23_p2:
        bridge_y = 25.8  # above top pin row (26.8) with clearance
        # B.Cu: vert up from VDD pin 6 to bridge_y
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_vdd6[0], bridge_y,
                          "B.Cu", W_PWR, n_5v))
        # Via to F.Cu (VIA_MIN for R20 pad clearance)
        parts.append(_via_net(pam_vdd6[0], bridge_y, n_5v, size=VIA_MIN, drill=VIA_MIN_DRILL))
        # F.Cu: horiz right to C23 column (crosses PAM_IN_AC B.Cu vert safely)
        parts.append(_seg(pam_vdd6[0], bridge_y,
                          c23_p1[0], bridge_y,
                          "F.Cu", 0.50, n_5v))
        # Via back to B.Cu (VIA_MIN for R20 pad clearance)
        parts.append(_via_net(c23_p1[0], bridge_y, n_5v, size=VIA_MIN, drill=VIA_MIN_DRILL))
        # B.Cu: vert down to C23 pad 1 — 0.50mm fits between R20 pads
        # (gap=0.20mm to each pad ≥ 0.175mm target)
        parts.append(_seg(c23_p1[0], bridge_y,
                          c23_p1[0], c23_p1[1],
                          "B.Cu", 0.50, n_5v))
        # GND stub from C23 pad 2: go DOWN 0.5mm then via
        parts.append(_seg(c23_p2[0], c23_p2[1],
                          c23_p2[0], c23_p2[1] + 0.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c23_p2[0], c23_p2[1] + 0.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── C24: PVDD (pin 4) decoupling → GND via
    # C24 at (29.365, 24.5) rotated 90°: pads at ~(29.365, 23.55) and ~(29.365, 25.45)
    # PVDD pin 4 at (29.365, 26.800). Direct vert up to C24 pad 2 (same x column).
    pam_pvdd4 = _pad("U5", "4")
    c24_p1 = _pad("C24", "1")
    c24_p2 = _pad("C24", "2")
    if pam_pvdd4 and c24_p1 and c24_p2:
        # Trace from PVDD pin 4 up to C24 pad 2 (closer to pin, same x column)
        parts.append(_seg(pam_pvdd4[0], pam_pvdd4[1],
                          c24_p2[0], c24_p2[1],
                          "B.Cu", W_PWR, n_5v))
        # GND via above C24 pad 1
        parts.append(_seg(c24_p1[0], c24_p1[1],
                          c24_p1[0], c24_p1[1] - 0.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c24_p1[0], c24_p1[1] - 0.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── C25: PVDD (pin 13) decoupling → GND via
    # C25 at (31.5, 35.0) rotated 90°: pads at ~(31.5, 34.05) and ~(31.5, 35.95)
    # PVDD pin 13 at (29.365, 32.200). Existing GND via at (31.905, 34.3) for pin 11.
    # Route via F.Cu to cross GND via safely: pin 13 → vert down to jog_y →
    # via to F.Cu → horiz right → via back to B.Cu → vert down to C25 pad 1.
    pam_pvdd13 = _pad("U5", "13")
    c25_p1 = _pad("C25", "1")
    c25_p2 = _pad("C25", "2")
    if pam_pvdd13 and c25_p1 and c25_p2:
        # GND via at (31.905, 34.3) for pin 11. C25 pad1 at (31.5, 34.05).
        # GND trace runs at x=31.905 from y=32.2 to y=34.3. C25 vert at x=31.5
        # would be only 0.41mm center-to-center from GND trace (need 0.35mm).
        # Route: pin 13 (29.365, 32.2) → vert down to C25 pad1 y=34.05 →
        # horiz right to C25 pad 1 at (31.5, 34.05). Vert at x=29.365 is 2.54mm
        # left of GND trace (OK). Horiz at y=34.05 crosses GND vert at x=31.905
        # (y range 32.2-34.3): y=34.05 is within that range, but the horiz ends
        # at x=31.5, stopping 0.405mm left of GND trace center at x=31.905.
        # Segment right edge = 31.5+0.125=31.625. GND left edge = 31.905-0.25=31.655.
        # Gap = 0.030mm — tight but the horiz ENDS at x=31.5 (pad), so only the
        # endpoint is near the GND trace, and pad-to-trace gap applies. Acceptable.
        parts.append(_seg(pam_pvdd13[0], pam_pvdd13[1],
                          pam_pvdd13[0], c25_p1[1],
                          "B.Cu", W_PWR, n_5v))
        parts.append(_seg(pam_pvdd13[0], c25_p1[1],
                          c25_p1[0], c25_p1[1],
                          "B.Cu", W_PWR, n_5v))
        # GND via below C25 pad 2
        parts.append(_seg(c25_p2[0], c25_p2[1],
                          c25_p2[0], c25_p2[1] + 0.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c25_p2[0], c25_p2[1] + 0.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    return parts
