#!/usr/bin/env python3
"""Enclosure <-> PCB mechanical sync gate — the shell must fit the board.

`hardware/enclosure/enclosure.scad` and `scripts/generate_pcb/board.py`
describe the same object from two sides, and until this gate nothing
compared them: the battery pocket held a cell that was no longer the
spec'd one, three button groups had drifted from their switches, and the
engraved A/B/X/Y labels named the wrong nets. Every check here reads the
scad's constants block (a CONTRACT: a constant this gate expects but
cannot parse is a structural error, never a skip) and compares it against
the board-side source of truth:

  outline / margins    board.py BOARD_W/H, CORNER_R
  screw bosses         board.py MOUNT_HOLES_ENC (the deliberate 4-of-6
                       subset: bosses must sit ON holes)
  edge cutouts (X)     board.py USBC_ENC / SD_ENC / PWR_SWITCH_ENC
  display viewport     board.py PANEL_ACTIVE_W/H (the viewport IS the
                       active area), PANEL_OUTLINE/PANEL_T, DISPLAY_ENC y;
                       the border split must add up to the outline; the
                       glass-centring references are the Select and Y cap
                       bodies computed from board SS/ABXY constants
  PCB model            hardware/enclosure/pcb_parts.scad is FRESH (it is
                       generated from board.py by generate_enclosure_pcb)
  buttons + LEDs       board.py DPAD/ABXY/SS/MENU/SHOULDER constants and
                       the six top-side LED placements (LED1-LED6)
  buttons + LEDs       board.py DPAD/ABXY/SS/MENU/LED/SHOULDER constants
                       (ABXY compared per-offset — DFM shifts included)
  ESP32 module         board.py ESP32_ENC cross-checked against the U1
                       placement; module envelope from the WROOM-1
                       datasheet (25.5 x 18.0 x 3.1 mm)
  battery pocket       scripts/vbench/models/bt1_lp105080.py `dims`
                       (10 x 50 x 80 mm) — axis map: length->X, width->Y,
                       thickness->Z
  Z stack              pcb_z == bot_d == boss top; body_d == bot_d + top_d;
                       top interior == panel thickness + cable riser; the
                       face-cap stem computed from that stack must still
                       reach the switch (SW_DATASHEET: TS-1187A code A,
                       1.5 mm); battery top clears every tall bottom-side
                       part (ESP32 module, J3 JST S2B-PH-SM4-TB 5.5 mm) by
                       >= MIN_Z_CLEAR wherever the pocket overlaps it in XY
  boss/pocket fit      no screw boss may stand inside the battery pocket
  L/R levers (V3)      edge caps press the ON-BOARD SW11/SW12 through a
                       printed bell-crank lever per side: the arm's end
                       edge on the board's switch centre, its top =
                       actuator tip - pretravel, arms giving a 0.8..1.25
                       ratio, the swing never above the actuator tip (the
                       TS-1187A cover from SW_DATASHEET), the beam clear
                       of the cap flange at full travel, the pin held in
                       its slot, lever and blocks clear of the pocket
                       border, the columns and every other bottom part;
                       the bottom column's half-column contact face
                       clears the SW11/SW12 pads
  -Y edge (V3)         SW16 knob (board PWR_SWITCH_ENC + MSK12C02) inside
                       the slider's fork; SD slit passes the 11 mm card
                       and the TF-01A housing front (U6) sets the card
                       reach; USB-C recess pad clears J1

Scalar constants are parsed with a COLUMN-0-anchored regex (a tolerant
anchor would bind module-local variables of the same name); vector
constants (`screw_positions`, `abxy_offsets`) go through a small
bracket-balanced reader. Expressions are evaluated over the constants
parsed so far (so `bot_d = body_d - top_d` works).

Output contract: every failing check prints a line starting with FAIL —
open_issues_report.py extracts exactly that shape.

Exit codes: 0 in sync · 1 mismatch(es) · 2 structural error (scad
contract broken, board module unimportable).
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

SCAD = BASE / "hardware" / "enclosure" / "enclosure.scad"

TOL = 0.1          # mm — position/dimension agreement
MIN_Z_CLEAR = 0.5  # mm — battery top to ESP32 module underside
BOSS_R = 3.0       # mm — screw boss outer radius (screw_d_outer / 2)

# ESP32-S3-WROOM-1 module envelope, datasheet section 10 (dimensions):
# 25.5 x 18.0 x 3.1 mm
ESP_DATASHEET = {"w": 25.5, "h": 18.0, "d": 3.1}

# PCB thickness: JLCPCB 4-layer 1.6 mm stackup (verify_stackup's subject)
PCB_THICKNESS = 1.6

# Tactile switch C318884 = XKB TS-1187A-B-A-B, datasheet
# website/static/datasheets/SW1-SW13_Tact-Switch_C318884.pdf: height code
# A = 1.5 mm, body 5.1 x 5.1, travel 0.25 mm; the drawing: cover face
# 1.2 above the board, actuator o2.0, operating force code B = 160 gf
SW_DATASHEET = {"h": 1.5, "body": 5.1, "cover": 1.2, "act_d": 2.0,
                "travel": 0.25, "force_gf": 160}

# J3 = JST S2B-PH-SM4-TB, hardware/datasheets/J3_JST-PH-2P-SMD_C295747.pdf
# p.4 "Side entry type": height 5.5 mm, B = 7.9 mm (2 circuits); 6.0 mm
# body + 2.6 mm mouth along the mating axis
J3_DATASHEET = {"w": 7.9, "h": 8.6, "d": 5.5}

MIN_STEM = 1.0     # mm — a face-cap stem shorter than this cannot be printed

# SW16 = MSK12C02 (hardware/datasheets/SW16_Slide-Switch_C431540.pdf):
# body 1.4 tall, knob 1.6 wide and 1.5 long on the -Y face, travel 1.6
PWR_DATASHEET = {"body_d": 2.8, "body_h": 1.4, "knob_w": 1.6, "knob_l": 1.5,
                 "travel": 1.6}
# U6 = TF-01A: housing 14.5 x 15 (pcb_parts BODY_BY_PACKAGE), front edge
# at SD_ENC y - 7.5

# board.py:46-47 record the body relation: 170mm body = 160 + 2x5mm
BODY_MARGIN = 5.0


class Structural(RuntimeError):
    """The scad constants contract or a source of truth is broken."""


# ─── scad parsing ────────────────────────────────────────────────────────

_SCALAR_RE = re.compile(r"^([a-z][a-z0-9_]*) = ([^;]+);", re.MULTILINE)


def _eval_expr(expr: str, env: dict) -> float:
    """Evaluate a scad constant expression (numbers, names, + - * /)."""
    try:
        node = ast.parse(expr, mode="eval").body
    except SyntaxError:
        raise Structural(f"unparseable scad expression: {expr!r}")

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in env and isinstance(env[n.id], float):
                return env[n.id]
            raise Structural(f"unknown name {n.id!r} in scad expression "
                             f"{expr!r} — constant moved or renamed?")
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Add):
                return a + b
            if isinstance(n.op, ast.Sub):
                return a - b
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        raise Structural(f"unsupported scad expression: {expr!r}")

    return ev(node)


def parse_scalars(text: str) -> dict:
    """Column-0 `name = value;` constants, evaluated in file order."""
    env: dict = {}
    for m in _SCALAR_RE.finditer(text):
        name, raw = m.group(1), m.group(2).strip()
        if raw.startswith('"'):
            env[name] = raw.strip('"')       # e.g. part = "assembly"
            continue
        if raw.startswith("["):
            continue                          # vectors: dedicated reader
        env[name] = _eval_expr(raw, env)
    return env


def parse_vector(text: str, name: str, env: dict) -> list:
    """Bracket-balanced reader for `name = [ [x, y], ... ];` at column 0."""
    m = re.search(r"^%s = \[" % re.escape(name), text, re.MULTILINE)
    if not m:
        raise Structural(f"vector constant {name!r} not found at column 0 "
                         "in enclosure.scad — the constants contract moved")
    i = m.end() - 1
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "[":
            depth += 1
        elif text[j] == "]":
            depth -= 1
            if depth == 0:
                break
    else:
        raise Structural(f"unbalanced brackets in {name!r}")
    body = re.sub(r"//[^\n]*", "", text[i + 1:j])
    pairs = []
    for chunk in re.findall(r"\[([^\[\]]+)\]", body):
        parts = [p.strip() for p in chunk.split(",") if p.strip()]
        if len(parts) != 2:
            raise Structural(f"{name!r} entry is not an [x, y] pair: "
                             f"{chunk!r}")
        pairs.append(tuple(_eval_expr(p, env) for p in parts))
    if not pairs:
        raise Structural(f"{name!r} parsed empty")
    return pairs


def need(env: dict, *names: str) -> list:
    missing = [n for n in names if n not in env
               or not isinstance(env[n], float)]
    if missing:
        raise Structural("scad constants missing or non-numeric: "
                         + ", ".join(missing)
                         + " — the constants contract moved")
    return [env[n] for n in names]


# ─── checks ──────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 72)
    print("ENCLOSURE <-> PCB MECHANICAL SYNC")
    print("=" * 72)

    try:
        from scripts.generate_pcb import board as B
        from scripts.generate_pcb.jlcpcb_export import _build_placements
        from scripts.vbench.models.bt1_lp105080 import BT1
        from scripts import generate_enclosure_pcb as GEP
    except Exception as e:  # a source of truth is unimportable
        raise Structural(f"cannot import a source of truth: {e}")
    parts = GEP.parts()
    by_ref = {r[0]: r for r in parts}

    text = SCAD.read_text()
    env = parse_scalars(text)
    screws = parse_vector(text, "screw_positions", env)
    abxy_offsets = parse_vector(text, "abxy_offsets", env)

    results = []

    def check(name: str, ok: bool, detail: str):
        results.append(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {detail}")

    def close(a, b, tol=TOL):
        return abs(a - b) <= tol

    # 1 — PCB outline
    pcb_w, pcb_h, pcb_d, pcb_r = need(env, "pcb_w", "pcb_h", "pcb_d",
                                      "pcb_corner_r")
    check("pcb-outline",
          close(pcb_w, B.BOARD_W) and close(pcb_h, B.BOARD_H)
          and close(pcb_d, PCB_THICKNESS) and close(pcb_r, B.CORNER_R),
          f"scad {pcb_w:g}x{pcb_h:g}x{pcb_d:g} r{pcb_r:g} vs board "
          f"{B.BOARD_W:g}x{B.BOARD_H:g}x{PCB_THICKNESS:g} r{B.CORNER_R:g}")

    # 2 — body margin relation (board.py:46-47)
    body_w, body_h = need(env, "body_w", "body_h")
    check("body-margin",
          close(body_w, B.BOARD_W + 2 * BODY_MARGIN)
          and close(body_h, B.BOARD_H + 2 * BODY_MARGIN),
          f"body {body_w:g}x{body_h:g} vs board + 2x{BODY_MARGIN:g}mm "
          f"= {B.BOARD_W + 2 * BODY_MARGIN:g}x{B.BOARD_H + 2 * BODY_MARGIN:g}")

    # 3 — screw bosses sit ON mount holes (deliberate 4-of-6 subset)
    holes = [(float(x), float(y)) for x, y in B.MOUNT_HOLES_ENC]
    orphan = [s for s in screws
              if not any(close(s[0], hx) and close(s[1], hy)
                         for hx, hy in holes)]
    check("screw-bosses",
          len(screws) == 4 and not orphan,
          f"{len(screws)} bosses, {len(orphan)} not on a mount hole"
          + (f" {orphan}" if orphan else ""))

    # 4 — edge cutout X positions
    usbc_x, sd_x, pwr_x = need(env, "usbc_x", "sd_x", "pwr_sw_x")
    check("edge-cutouts",
          close(usbc_x, B.USBC_ENC[0]) and close(sd_x, B.SD_ENC[0])
          and close(pwr_x, B.PWR_SWITCH_ENC[0]),
          f"USB {usbc_x:g}/{B.USBC_ENC[0]:g}, SD {sd_x:g}/{B.SD_ENC[0]:g}, "
          f"PWR {pwr_x:g}/{B.PWR_SWITCH_ENC[0]:g}")

    # 5 — display: viewport == panel active area, panel envelope, borders
    disp_w, disp_h, disp_oy, disp_x = need(env, "disp_w", "disp_h",
                                           "disp_offset_y", "disp_x")
    disp_t, out_l, out_w = need(env, "disp_t", "disp_outline_l",
                                "disp_outline_w")
    b_side, b_tail, b_end = need(env, "disp_border_side",
                                 "disp_border_tail", "disp_border_end")
    check("display-viewport",
          close(disp_w, B.PANEL_ACTIVE_W) and close(disp_h, B.PANEL_ACTIVE_H)
          and close(disp_oy, B.DISPLAY_ENC[1]),
          f"viewport {disp_w:g}x{disp_h:g}@({disp_x:g},{disp_oy:g}) vs "
          f"panel active {B.PANEL_ACTIVE_W:g}x{B.PANEL_ACTIVE_H:g}"
          f"@y{B.DISPLAY_ENC[1]}")
    ref_l, ref_r, gcx, tail_side = need(env, "disp_ref_left",
                                        "disp_ref_right", "disp_glass_cx",
                                        "disp_tail_side")
    ss_w, abxy_diam, btn_clear = need(env, "ss_w", "abxy_diam", "btn_clear")
    want_l = B.SS_ENC[0] + B.SS_OFFSETS[1][0] + ss_w / 2 - btn_clear / 2
    want_r = B.ABXY_ENC[0] + B.ABXY_OFFSETS[3][0] - abxy_diam / 2 + btn_clear / 2
    check("display-glass-refs",
          close(ref_l, want_l) and close(ref_r, want_r)
          and close(gcx, (want_l + want_r) / 2) and abs(tail_side) == 1
          and close(disp_x, gcx - tail_side * (b_tail - b_end) / 2),
          f"glass between Select body edge {ref_l:g} (board {want_l:g}) and "
          f"Y body edge {ref_r:g} (board {want_r:g}); centre {gcx:g}, tail "
          f"side {tail_side:+g}, active centre {disp_x:g}")

    # 5b — the generated PCB model matches board.py
    check("pcb-parts-fresh",
          GEP.OUT.exists() and GEP.OUT.read_text() == GEP.build(),
          f"{GEP.OUT.relative_to(BASE)} vs generate_enclosure_pcb.build()")
    check("display-panel",
          close(disp_t, B.PANEL_T) and close(out_l, B.PANEL_OUTLINE_L)
          and close(out_w, B.PANEL_OUTLINE_W)
          and close(b_tail + b_end, out_l - disp_w)
          and close(2 * b_side, out_w - disp_h),
          f"panel {out_l:g}x{out_w:g}x{disp_t:g}, borders tail {b_tail:g} "
          f"+ end {b_end:g} = {b_tail + b_end:g} (need {out_l - disp_w:g}), "
          f"side {b_side:g} (need {(out_w - disp_h) / 2:g})")

    # 6 — button clusters
    dpad_x, dpad_y, arm = need(env, "dpad_x", "dpad_y", "dpad_arm_len")
    stem_r = arm - 3          # cap stems sit at arm_len-3 from center
    dpad_r = abs(B.DPAD_OFFSETS[0][1])
    check("dpad",
          close(dpad_x, B.DPAD_ENC[0]) and close(dpad_y, B.DPAD_ENC[1])
          and close(stem_r, dpad_r),
          f"center ({dpad_x:g},{dpad_y:g}) stems r{stem_r:g} vs board "
          f"{B.DPAD_ENC} r{dpad_r:g}")

    abxy_x, abxy_y = need(env, "abxy_x", "abxy_y")
    off_bad = [i for i, ((sx, sy), (bx, by))
               in enumerate(zip(abxy_offsets, B.ABXY_OFFSETS))
               if not (close(sx, bx) and close(sy, by))]
    check("abxy",
          close(abxy_x, B.ABXY_ENC[0]) and close(abxy_y, B.ABXY_ENC[1])
          and len(abxy_offsets) == len(B.ABXY_OFFSETS) and not off_bad,
          f"center ({abxy_x:g},{abxy_y:g}) vs {B.ABXY_ENC}; "
          f"offsets {abxy_offsets} vs {B.ABXY_OFFSETS}"
          + (f" — mismatch at index {off_bad}" if off_bad else ""))

    ss_x, ss_y, ss_spacing = need(env, "ss_x", "ss_y", "ss_spacing")
    ss_r = abs(B.SS_OFFSETS[0][0])
    check("start-select",
          close(ss_x, B.SS_ENC[0]) and close(ss_y, B.SS_ENC[1])
          and close(ss_spacing / 2, ss_r),
          f"center ({ss_x:g},{ss_y:g}) half-span {ss_spacing / 2:g} vs "
          f"board {B.SS_ENC} r{ss_r:g}")

    menu_x, menu_y = need(env, "menu_x", "menu_y")
    check("menu",
          close(menu_x, B.MENU_ENC[0]) and close(menu_y, B.MENU_ENC[1]),
          f"({menu_x:g},{menu_y:g}) vs board {B.MENU_ENC}")

    led_bad = []
    for n in range(1, 7):
        lx, ly = need(env, f"led{n}_x", f"led{n}_y")
        row = by_ref.get(f"LED{n}")
        if row is None or row[4] != "top" or not (close(lx, row[1])
                                                  and close(ly, row[2])):
            led_bad.append(f"LED{n} scad ({lx:g},{ly:g}) vs "
                           f"{(row[1], row[2], row[4]) if row else 'absent'}")
    check("leds",
          not led_bad,
          "LED1-LED6 light pipes on the top-side LED placements"
          + (": " + "; ".join(led_bad) if led_bad else ""))

    # 6b — L/R levers (V3): edge caps press the ON-BOARD SW11/SW12 through
    # a bell crank. Geometry is checked against the board placements and
    # the TS-1187A drawing, the kinematics from the constants.
    (lr_x, lr_sx, lr_sy, cover, arm_top, arm_end, arm_w, piv_y, piv_z, pin_d,
     slot_w, beam_y0, beam_y1, beam_z0, beam_x0, beam_x1, in_w, in_y0, in_y1,
     in_z0, bump_r, bump_z, blk_t, blk_gap, blk_wall, blk_top, fl_t, fl_gap,
     fl_back, cap_w, cap_cl, fl_extra, sw_h_, pretravel_, travel_,
     side_wall_) = need(
        env, "lr_x", "lr_sw_x", "lr_sw_y", "sw_cover_h", "lr_arm_top",
        "lr_arm_y_end", "lr_arm_w", "lr_piv_y", "lr_piv_z", "lr_pin_d",
        "lr_slot_w", "lr_beam_y0", "lr_beam_y1", "lr_beam_z0", "lr_beam_x0",
        "lr_beam_x1", "lr_in_w", "lr_in_y0", "lr_in_y1", "lr_in_z0",
        "lr_bump_r", "lr_bump_z", "lr_blk_t", "lr_blk_gap", "lr_blk_wall",
        "lr_blk_top", "lr_fl_t", "lr_fl_gap", "lr_fl_back_y", "lr_cap_w",
        "lr_cap_clear", "lr_fl_extra", "sw_h", "sw_pretravel", "sw_travel",
        "side_wall")
    pcb_z_, pcb_h_ = need(env, "pcb_z", "pcb_h")
    D = SW_DATASHEET
    tip_z = pcb_z_ - sw_h_                    # actuator tip at rest
    probs = []
    for ref, sgn in (("SW11", -1), ("SW12", 1)):
        row = by_ref.get(ref)
        if row is None or row[4] != "bottom" or not (close(sgn * lr_sx, row[1])
                                                     and close(lr_sy, row[2])):
            probs.append(f"{ref} scad ({sgn * lr_sx:g},{lr_sy:g}) vs board "
                         f"{(row[1], row[2], row[4]) if row else 'absent'}")
    r_out = piv_y - arm_end                  # pivot -> contact edge on the actuator
    r_in = piv_z - bump_z                    # pivot -> cap contact
    theta = (pretravel_ + travel_) / r_out   # full switch travel
    if not close(cover, D["cover"]) or not close(travel_, D["travel"]):
        probs.append(f"cover {cover:g} / travel {travel_:g} vs datasheet {D['cover']:g} / {D['travel']:g}")
    if not close(arm_top, tip_z - pretravel_):
        probs.append(f"arm top {arm_top:g} != actuator tip {tip_z:g} - pretravel {pretravel_:g}")
    if not close(arm_end, lr_sy):
        probs.append(f"arm end edge y {arm_end:g} off the actuator centre line {lr_sy:g} "
                     f"(beyond it the arm rises above the actuator tip, short of it the push is off-centre)")
    if arm_w < D["act_d"]:
        probs.append(f"arm {arm_w:g} narrower than the o{D['act_d']:g} actuator")
    # the beam's -Y edge (nearest to the switch body) at full travel
    beam_rise = arm_top + (piv_y - beam_y0) * theta
    body_edge = lr_sy + D["body"] / 2
    if beam_y0 < body_edge + 0.3 and beam_rise > pcb_z_ - cover - 0.05:
        probs.append(f"beam edge y {beam_y0:g} rises to {beam_rise:.2f} under the switch cover")
    if beam_rise > pcb_z_ - 0.3:
        probs.append(f"beam rises to {beam_rise:.2f}, within 0.3 of the PCB")
    check("lr-lever-on-switch",
          not probs,
          f"SW11/SW12 at (+/-{lr_sx:g},{lr_sy:g}) on the board's bottom side; arm "
          f"{arm_w:g} wide, top {arm_top:g} = tip {tip_z:g} - pretravel {pretravel_:g}, end "
          f"edge on the actuator centre line; at full travel the arm reaches the tip "
          f"{tip_z + travel_:g}, {pcb_z_ - cover - (tip_z + travel_):.2f} under the cover"
          + (": " + "; ".join(probs) if probs else ""))

    probs = []
    ratio = r_out / r_in
    cap_travel = theta * r_in
    if not 0.8 <= ratio <= 1.25:
        probs.append(f"ratio {ratio:.2f} outside 0.8..1.25 (cap travel {cap_travel:.2f}, "
                     f"force {D['force_gf'] * ratio:.0f} gf)")
    if not close(fl_back, body_h / 2 - side_wall_ - fl_gap - fl_t):
        probs.append(f"flange back y {fl_back:g} not derived from the wall")
    gap = fl_back - (in_y1 + bump_r)
    if not 0 < gap <= 0.1 + 1e-9:
        probs.append(f"bump {gap:.2f} from the flange (want 0..0.1)")
    if not (in_z0 <= bump_z - bump_r and bump_z + bump_r <= beam_z0):
        probs.append(f"bump Z {bump_z:g} not on the lower arm (Z {in_z0:g}..{beam_z0:g})")
    for name_, y_ in (("beam", beam_y1), ("lower arm", in_y1)):
        if y_ > fl_back - cap_travel - 0.2 + 1e-9:
            probs.append(f"{name_} +Y face {y_:g} within 0.2 of the flange at full travel "
                         f"({fl_back - cap_travel:.2f})")
    if not (beam_y0 < piv_y < beam_y1 and beam_z0 < piv_z - pin_d / 2):
        probs.append(f"pivot ({piv_y:g},{piv_z:g}) outside the beam")
    # the lever can only rise until its arm meets the actuator (pretravel):
    # the whole pin must stay >= 0.5 under the slot top
    pin_hi = piv_z + pretravel_ + pin_d / 2
    if blk_top - pin_hi < 0.5 - 1e-9:
        probs.append(f"pin top rises to {pin_hi:g}, {blk_top - pin_hi:.2f} under the slot "
                     f"top {blk_top:g} (want >= 0.5)")
    if blk_top > pcb_z_ - 0.3 + 1e-9 or slot_w - pin_d < 0.2 - 1e-9 or blk_wall < 1.2 - 1e-9:
        probs.append(f"block top {blk_top:g} / slot clearance {slot_w - pin_d:g} / wall {blk_wall:g}")
    check("lr-lever-kinematics",
          not probs,
          f"arms {r_out:g} / {r_in:g} (ratio {ratio:.2f}): cap travel {cap_travel:.2f}, "
          f"force {D['force_gf'] * ratio:.0f} gf; bump {gap:.2f} from the flange; beam "
          f"{fl_back - cap_travel - beam_y1:.2f} short of it at full travel; pin o{pin_d:g} "
          f"in a {slot_w:g} slot, its top {blk_top - pin_hi:.1f} under the slot top "
          f"at most lift" + (": " + "; ".join(probs) if probs else ""))

    # lever and blocks (both sides) vs the flange X span, the pocket border,
    # the columns and every other bottom-side part
    bat_ox_, bat_oy_, bat_w_, bat_h_, bbw_ = need(env, "bat_offset_x", "bat_offset_y",
                                                 "bat_w", "bat_h", "bat_border_w")
    pb_x0, pb_x1 = bat_ox_ - (bat_w_ + 5) / 2 - bbw_, bat_ox_ + (bat_w_ + 5) / 2 + bbw_
    pb_y0, pb_y1 = bat_oy_ - bat_h_ / 2 - bbw_, bat_oy_ + bat_h_ / 2 + bbw_
    fl_half = (cap_w - cap_cl) / 2 + fl_extra
    y_in = body_h / 2 - side_wall_
    probs = []
    for sgn in (-1, 1):
        def X(a, b):
            return (min(sgn * a, sgn * b), max(sgn * a, sgn * b))
        moving = (("beam",) + X(beam_x0, beam_x1) + (beam_y0, beam_y1, beam_z0),
                  ("arm",) + X(lr_sx - arm_w / 2, lr_sx + arm_w / 2) + (arm_end, beam_y0, beam_z0),
                  ("lower arm",) + X(lr_x - in_w / 2, lr_x + in_w / 2) + (in_y0, in_y1 + bump_r, in_z0))
        blocks = (("block",) + X(beam_x0 - blk_gap - blk_t, beam_x0 - blk_gap)
                  + (piv_y - slot_w / 2 - blk_wall, y_in, 2.0),
                  ("block",) + X(beam_x1 + blk_gap, beam_x1 + blk_gap + blk_t)
                  + (piv_y - slot_w / 2 - blk_wall, y_in, 2.0))
        for nm, x0, x1, y0, y1, _z in moving + blocks:
            if x0 < pb_x1 and x1 > pb_x0 and y0 < pb_y1 and y1 > pb_y0:
                probs.append(f"{nm} x[{x0:g},{x1:g}] over the pocket border")
            for cx, cy in screws:
                nx, ny = min(max(cx, x0), x1), min(max(cy, y0), y1)
                d = ((cx - nx) ** 2 + (cy - ny) ** 2) ** 0.5
                if nm != "block" and d < BOSS_R + 0.4:
                    probs.append(f"{nm} {d - BOSS_R:.2f} from the column at ({cx:g},{cy:g})")
            for ref, px, py, rot, side, L, W, H in parts:
                if side != "bottom" or ref in ("SW11", "SW12"):
                    continue
                cw, ch = (W, L) if rot % 180 == 90 else (L, W)
                if x0 < px + cw / 2 and x1 > px - cw / 2 and y0 < py + ch / 2 \
                        and y1 > py - ch / 2:
                    probs.append(f"{ref} over the L/R {nm}")
        for nm, x0, x1, *_ in blocks:      # the flange slides past the blocks
            if x0 < sgn * lr_x + fl_half + 0.3 and x1 > sgn * lr_x - fl_half - 0.3:
                probs.append(f"block x[{x0:g},{x1:g}] inside the cap flange span")
    check("lr-lever-clear",
          not probs,
          f"levers and pivot blocks at x=+/-[{beam_x0 - blk_gap - blk_t:g},"
          f"{beam_x1 + blk_gap + blk_t:g}] vs the flange span +/-[{lr_x - fl_half:g},"
          f"{lr_x + fl_half:g}], pocket border x[{pb_x0:g},{pb_x1:g}] y[{pb_y0:g},{pb_y1:g}], "
          f"columns, bottom parts" + (": " + "; ".join(probs) if probs else " — all clear"))

    # 6c — power slider vs SW16 (board placement + MSK12C02 datasheet)
    (k_tip, k_root, k_z, k_w, travel, nub_w, slot_w, fl_w, fork_z0, fork_z1,
     fl_t, fl_z0, slot_z0, g_z0, g_z1, g_d, ch_d, ch_half, g_lip, g_stop) = need(
        env, "pwr_knob_tip_y", "pwr_knob_root_y", "pwr_knob_z", "pwr_knob_w",
        "pwr_travel", "pwr_nub_w", "pwr_slot_w", "pwr_fl_w", "pwr_fork_z0",
        "pwr_fork_z1", "pwr_fl_t", "pwr_fl_z0", "pwr_slot_z0", "pwr_guide_z0",
        "pwr_guide_z1", "pwr_guide_d", "pwr_chan_d", "pwr_chan_half",
        "pwr_guide_lip", "pwr_guide_stop")
    PD = PWR_DATASHEET
    want_root = B.PWR_SWITCH_ENC[1] - PD["body_d"] / 2
    want_tip = want_root - PD["knob_l"]
    fork_end = k_root - 0.6
    check("pwr-slider-vs-sw16",
          close(k_root, want_root) and close(k_tip, want_tip) and close(k_w, PD["knob_w"])
          and close(travel, PD["travel"])
          and pcb_z_ - PD["body_h"] <= k_z <= pcb_z_
          and fork_z0 <= k_z - 0.3 and fork_z1 >= k_z + 0.3 and fork_z1 <= pcb_z_ - 0.1
          and fork_end - k_tip >= 0.5
          and slot_w >= nub_w + travel + 0.3 - 1e-9
          and fl_w >= slot_w + travel + 2 * 1.2 - 1e-9 and fl_z0 <= slot_z0 - 1.2 + 1e-9
          # the horizontal guide: flange runs in the channel with play, the
          # channel is longer than flange + travel, its lip and end stops are
          # printable, the block ends under the SW16 body and the fork arms
          and ch_d >= fl_t + 0.05 and ch_half >= fl_w / 2 + travel / 2 + 0.2 - 1e-9
          and g_lip >= 1.2 - 1e-9 and g_stop >= 1.2 - 1e-9
          and g_z0 < fl_z0 and g_z1 <= min(fork_z0, pcb_z_ - PD["body_h"]) - 0.1
          and body_h / 2 - side_wall_ - g_d <= pcb_h_ / 2 + 0.3,
          f"knob root y {k_root:g} (board {want_root:g}), tip {k_tip:g} ({want_tip:g}), "
          f"Z {k_z:g} in [{pcb_z_ - PD['body_h']:g},{pcb_z_:g}]; fork Z {fork_z0:g}..{fork_z1:g} "
          f"reaches y {fork_end:g} ({fork_end - k_tip:g} over the knob); slot {slot_w:g} >= nub "
          f"{nub_w:g} + travel {travel:g}; flange {fl_w:g} wide from Z {fl_z0:g}; guide "
          f"channel {2 * ch_half:g} x {ch_d:g} in a {g_d:g} deep block Z {g_z0:g}..{g_z1:g}, "
          f"lip {g_lip:g}, stops {g_stop:g} (ON<->OFF range {travel:g})")

    # 6d — SD card slit + card reach, USB-C recess pad vs J1
    (sd_front, sd_out, sd_reach, sd_zc, sd_h, sd_wc,
     u_rd, u_pad, u_rw, u_rh, u_cw, u_ch) = need(
        env, "sd_housing_front", "sd_card_out", "sd_card_reach",
        "sd_z", "sd_cut_h", "sd_cut_w",
        "usbc_recess_d", "usbc_pad_t", "usbc_recess_w", "usbc_recess_h",
        "usbc_cut_w", "usbc_cut_h")
    u6 = by_ref.get("U6")
    j1 = by_ref.get("J1")
    if u6 is None or j1 is None:
        raise Structural("U6 (TF-01A) or J1 (USB-C) missing from the PCB model")
    want_front = -(u6[2] - u6[6] / 2)
    # microSD is 11 mm wide: the slit must pass it, and stay in the bottom
    # shell (top edge below the PCB bottom face = the shell split)
    check("sd-slit",
          close(sd_front, want_front) and close(sd_reach, body_h / 2 - sd_front - sd_out)
          and sd_wc >= 11 + 2 and sd_zc + sd_h / 2 <= pcb_z_ + 1e-9,
          f"TF-01A front |y| {sd_front:g} (U6 {want_front:g}); card end {sd_reach:g} "
          f"inside the face; {sd_wc:g}x{sd_h:g} slit at Z {sd_zc:g} "
          f"(top {sd_zc + sd_h / 2:g} <= PCB bottom {pcb_z_:g})")
    j1_front = -(j1[2] - j1[6] / 2)
    pad_face = body_h / 2 - side_wall_ - u_pad
    check("usbc-recess",
          u_rd >= 2.0 - 1e-9 and side_wall_ + u_pad - u_rd >= 1.2 - 1e-9
          and pad_face > j1_front + 0.5 and u_rw > u_cw + 2 and u_rh > u_ch + 2,
          f"recess {u_rd:g} deep ({u_rw:g}x{u_rh:g} round the {u_cw:g}x{u_ch:g} opening), "
          f"floor {side_wall_ + u_pad - u_rd:g} thick; pad inner face |y| {pad_face:g} vs "
          f"J1 front {j1_front:g}")

    # 7 — ESP32 module: scad constants vs board constant vs U1 placement
    esp_x, esp_y, esp_w, esp_h, esp_d = need(
        env, "esp_x", "esp_y", "esp_w", "esp_h", "esp_d")
    u1 = [(x, y) for ref, _v, _pkg, x, y, _r, _l in _build_placements()
          if ref == "U1"]
    if not u1:
        raise Structural("U1 not found in _build_placements()")
    u1_enc = (u1[0][0] - B.CX, B.CY - u1[0][1])
    check("esp32-position",
          close(esp_x, B.ESP32_ENC[0]) and close(esp_y, B.ESP32_ENC[1])
          and close(u1_enc[0], B.ESP32_ENC[0])
          and close(u1_enc[1], B.ESP32_ENC[1]),
          f"scad ({esp_x:g},{esp_y:g}), board {B.ESP32_ENC}, "
          f"U1 placement ({u1_enc[0]:g},{u1_enc[1]:g})")
    check("esp32-envelope",
          close(esp_w, ESP_DATASHEET["w"]) and close(esp_h, ESP_DATASHEET["h"])
          and esp_d >= ESP_DATASHEET["d"] - 1e-9,
          f"scad {esp_w:g}x{esp_h:g}x{esp_d:g} vs datasheet "
          f"{ESP_DATASHEET['w']}x{ESP_DATASHEET['h']}x{ESP_DATASHEET['d']}")

    # 8 — battery pocket holds the cell (source: vbench BT1 dims)
    cell_t, cell_w, cell_l = BT1.params["dims"].value
    bat_w, bat_h, bat_d = need(env, "bat_w", "bat_h", "bat_d")
    bat_ox, bat_oy, wall = need(env, "bat_offset_x", "bat_offset_y", "wall")
    pocket = (bat_w + 5, bat_h, bat_d)   # +5: lead clearance in X
    check("battery-pocket",
          pocket[0] >= cell_l - 1e-9 and pocket[1] >= cell_w - 1e-9
          and pocket[2] >= cell_t - 1e-9,
          f"pocket {pocket[0]:g}x{pocket[1]:g}x{pocket[2]:g} vs cell "
          f"LxWxT {cell_l:g}x{cell_w:g}x{cell_t:g} "
          f"({BT1.part}, {BT1.datasheet.doc})")

    # 9 — Z stack
    pcb_z, bot_d, boss_h = need(env, "pcb_z", "bot_d", "screw_boss_h")
    check("z-pcb-seat",
          close(pcb_z, bot_d) and close(wall + boss_h, pcb_z),
          f"pcb_z {pcb_z:g}, bot_d {bot_d:g}, boss top {wall + boss_h:g}")

    body_d, top_d, top_int, riser, stack = need(
        env, "body_d", "top_d", "top_int", "disp_riser", "disp_stack")
    check("z-top-stack",
          close(body_d, bot_d + top_d) and close(top_d, pcb_d + top_int + wall)
          and close(top_int, stack) and close(stack, disp_t + riser),
          f"body {body_d:g} = bot {bot_d:g} + top {top_d:g}; interior "
          f"{top_int:g} = panel {disp_t:g} + riser {riser:g}")

    sw_h, sw_body, stem_h, guide_h, flange_h, pretravel = need(
        env, "sw_h", "sw_body", "btn_stem_h", "btn_guide_h", "btn_flange_h",
        "sw_pretravel")
    check("switch-datasheet",
          close(sw_h, SW_DATASHEET["h"]) and close(sw_body, SW_DATASHEET["body"]),
          f"scad switch {sw_body:g}x{sw_body:g}x{sw_h:g} vs TS-1187A code A "
          f"{SW_DATASHEET['body']}x{SW_DATASHEET['body']}x{SW_DATASHEET['h']}")
    check("cap-stem",
          close(stem_h, top_int - guide_h - flange_h - sw_h - pretravel)
          and stem_h >= MIN_STEM - 1e-9,
          f"stem {stem_h:g} = interior {top_int:g} - well {guide_h:g} - "
          f"flange {flange_h:g} - switch {sw_h:g} - pretravel {pretravel:g} "
          f"(min {MIN_STEM:g})")

    # battery vs every tall bottom-side part it overlaps in XY
    px0, px1 = bat_ox - pocket[0] / 2, bat_ox + pocket[0] / 2
    py0, py1 = bat_oy - pocket[1] / 2, bat_oy + pocket[1] / 2
    bat_top = wall + bat_d
    jst_x, jst_y, jst_w, jst_h, jst_d = need(
        env, "jst_x", "jst_y", "jst_w", "jst_h", "jst_d")
    check("jst-datasheet",
          close(jst_x, B.JST_BAT_ENC[0]) and close(jst_y, B.JST_BAT_ENC[1])
          and close(jst_w, J3_DATASHEET["w"]) and close(jst_h, J3_DATASHEET["h"])
          and jst_d >= J3_DATASHEET["d"] - 1e-9,
          f"J3 ({jst_x:g},{jst_y:g}) {jst_w:g}x{jst_h:g}x{jst_d:g} vs board "
          f"{B.JST_BAT_ENC} + S2B-PH-SM4-TB {J3_DATASHEET}")
    for name, cx, cy, cw, ch, cd in (
            ("module", esp_x, esp_y, esp_w, esp_h, esp_d),
            ("j3", jst_x, jst_y, jst_w, jst_h, jst_d)):
        ex0, ex1 = cx - cw / 2, cx + cw / 2
        ey0, ey1 = cy - ch / 2, cy + ch / 2
        overlaps = px0 < ex1 and px1 > ex0 and py0 < ey1 and py1 > ey0
        part_bottom = pcb_z - cd
        check(f"z-battery-{name}",
              (not overlaps) or bat_top + MIN_Z_CLEAR <= part_bottom + 1e-9,
              f"battery top {bat_top:g} vs {name} underside {part_bottom:g} "
              f"(overlap={'yes' if overlaps else 'no'}, "
              f"min clear {MIN_Z_CLEAR:g})")
    # ...and EVERY bottom-side part from the generated PCB model
    hits = []
    for ref, cx, cy, rot, side, L, W, H in parts:
        if side != "bottom":
            continue
        cw, ch = (W, L) if rot % 180 == 90 else (L, W)
        ex0, ex1 = cx - cw / 2, cx + cw / 2
        ey0, ey1 = cy - ch / 2, cy + ch / 2
        if px0 < ex1 and px1 > ex0 and py0 < ey1 and py1 > ey0:
            if bat_top + MIN_Z_CLEAR > pcb_z - H + 1e-9:
                hits.append(f"{ref} ({H:g} tall, underside {pcb_z - H:g})")
    check("z-battery-all-parts",
          not hits,
          f"{sum(1 for r in parts if r[4] == 'bottom')} bottom parts vs the "
          f"pocket footprint" + (": " + ", ".join(hits) if hits else ""))

    # battery hold-down straps + posts vs every bottom-side part
    sx1, sx2, s_w, s_t, p_w, p_t, p_h, bbw = need(
        env, "bat_strap_x1", "bat_strap_x2", "bat_strap_w", "bat_strap_t",
        "bat_post_w", "bat_post_t", "bat_post_h", "bat_border_w")
    boxes = []
    for sx in (sx1, sx2):
        y_out = bat_h / 2 + bbw + p_t
        boxes.append((f"strap x={sx:g}", sx - s_w / 2, sx + s_w / 2,
                      bat_oy - y_out, bat_oy + y_out, wall + p_h + s_t))
        for sgn in (-1, 1):
            py = bat_oy + sgn * (bat_h / 2 + bbw + p_t / 2)
            boxes.append((f"post ({sx:g},{py:g})", sx - p_w / 2, sx + p_w / 2,
                          py - p_t / 2, py + p_t / 2, wall + p_h))
    hits = []
    for name, x0, x1, y0, y1, ztop in boxes:
        for ref, cx, cy, rot, side, L, W, H in parts:
            if side != "bottom":
                continue
            cw, ch = (W, L) if rot % 180 == 90 else (L, W)
            if x0 < cx + cw / 2 and x1 > cx - cw / 2 and y0 < cy + ch / 2 \
                    and y1 > cy - ch / 2 and pcb_z - H < ztop + MIN_Z_CLEAR - 1e-9:
                hits.append(f"{name} vs {ref} (underside {pcb_z - H:g})")
    check("z-battery-straps",
          not hits and sx1 + s_w / 2 < esp_x - esp_w / 2 - 1e-9
          and sx2 - s_w / 2 > esp_x + esp_w / 2 + 1e-9,
          f"2 straps (top Z {wall + p_h + s_t:g}) + 4 posts (top Z {wall + p_h:g}) "
          f"outside the ESP32 footprint, {MIN_Z_CLEAR:g} under every part"
          + (": " + ", ".join(hits) if hits else ""))

    # 10 — no screw boss stands inside the battery pocket
    inside = [s for s in screws
              if px0 - BOSS_R < s[0] < px1 + BOSS_R
              and py0 - BOSS_R < s[1] < py1 + BOSS_R]
    check("boss-pocket-fit",
          not inside,
          f"{len(inside)} boss(es) inside pocket footprint"
          + (f" {inside}" if inside else ""))

    # 11 — the column's contact face under the PCB is its OUTER half: its
    # inner edge is the axis (corner_x), which must clear the SW11/SW12
    # pad field (the wires to the off-board L/R switches are soldered
    # there: body edge + 0.7 mm of terminal) and stand >= boss_half_h tall
    half_h, s_out = need(env, "boss_half_h", "screw_d_outer")
    corner_x = max(abs(s[0]) for s in screws)
    corner_y = max(abs(s[1]) for s in screws)
    sh_x, sh_y = B.SHOULDER_R_ENC
    inner_edge = corner_x
    pad_edge = abs(sh_x) + sw_body / 2 + 0.7
    check("half-column-shoulder-switch",
          inner_edge >= pad_edge + 0.5 - 1e-9 and half_h >= 1.5 - 1e-9
          and abs(corner_y - sh_y) < s_out / 2 + sw_body,
          f"contact half-column inner edge {inner_edge:g} vs SW11/12 pad edge "
          f"{pad_edge:g} (min 0.5 clear), half height {half_h:g}")

    print("-" * 72)
    fails = results.count(False)
    if fails:
        print(f"Results: FAIL — {fails}/{len(results)} mechanical sync "
              "check(s): the printed shell no longer matches the board")
        return 1
    print(f"Results: PASS — {len(results)}/{len(results)} enclosure "
          "constants agree with the board sources")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Structural as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
