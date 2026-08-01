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
  display viewport     board.py DISPLAY_W/H / DISPLAY_ENC
  buttons + LEDs       board.py DPAD/ABXY/SS/MENU/LED/SHOULDER constants
                       (ABXY compared per-offset — DFM shifts included)
  ESP32 module         board.py ESP32_ENC cross-checked against the U1
                       placement; module envelope from the WROOM-1
                       datasheet (25.5 x 18.0 x 3.1 mm)
  battery pocket       scripts/vbench/models/bt1_lp105080.py `dims`
                       (10 x 50 x 80 mm) — axis map: length->X, width->Y,
                       thickness->Z
  Z stack              pcb_z == bot_d == boss top; battery top clears the
                       ESP32 module underside by >= MIN_Z_CLEAR when the
                       pocket overlaps the module in XY
  boss/pocket fit      no screw boss may stand inside the battery pocket

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
    except Exception as e:  # a source of truth is unimportable
        raise Structural(f"cannot import a source of truth: {e}")

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

    # 5 — display viewport
    disp_w, disp_h, disp_oy = need(env, "disp_w", "disp_h", "disp_offset_y")
    check("display",
          close(disp_w, B.DISPLAY_W) and close(disp_h, B.DISPLAY_H)
          and close(disp_oy, B.DISPLAY_ENC[1]),
          f"viewport {disp_w:g}x{disp_h:g}@y{disp_oy:g} vs board "
          f"{B.DISPLAY_W:g}x{B.DISPLAY_H:g}@y{B.DISPLAY_ENC[1]:g}")

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

    l1x, l1y, l2x, l2y = need(env, "led1_x", "led1_y", "led2_x", "led2_y")
    check("leds",
          close(l1x, B.LED_CHARGE_ENC[0]) and close(l1y, B.LED_CHARGE_ENC[1])
          and close(l2x, B.LED_FULL_ENC[0]) and close(l2y, B.LED_FULL_ENC[1]),
          f"led1 ({l1x:g},{l1y:g})/{B.LED_CHARGE_ENC} "
          f"led2 ({l2x:g},{l2y:g})/{B.LED_FULL_ENC}")

    sh_x, sh_y = need(env, "shoulder_inset_x", "shoulder_y")
    check("shoulders",
          close(-sh_x, B.SHOULDER_L_ENC[0]) and close(sh_x, B.SHOULDER_R_ENC[0])
          and close(sh_y, B.SHOULDER_L_ENC[1])
          and close(sh_y, B.SHOULDER_R_ENC[1]),
          f"(+/-{sh_x:g},{sh_y:g}) vs board {B.SHOULDER_L_ENC} / "
          f"{B.SHOULDER_R_ENC}")

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

    # battery-vs-module clearance applies when pocket and module overlap
    # in XY (an 85mm pocket cannot avoid the centered module)
    px0, px1 = bat_ox - pocket[0] / 2, bat_ox + pocket[0] / 2
    py0, py1 = bat_oy - pocket[1] / 2, bat_oy + pocket[1] / 2
    ex0, ex1 = esp_x - esp_w / 2, esp_x + esp_w / 2
    ey0, ey1 = esp_y - esp_h / 2, esp_y + esp_h / 2
    overlaps = px0 < ex1 and px1 > ex0 and py0 < ey1 and py1 > ey0
    bat_top = wall + bat_d
    esp_bottom = pcb_z - esp_d
    check("z-battery-module",
          (not overlaps) or bat_top + MIN_Z_CLEAR <= esp_bottom + 1e-9,
          f"battery top {bat_top:g} vs module underside {esp_bottom:g} "
          f"(overlap={'yes' if overlaps else 'no'}, "
          f"min clear {MIN_Z_CLEAR:g})")

    # 10 — no screw boss stands inside the battery pocket
    inside = [s for s in screws
              if px0 - BOSS_R < s[0] < px1 + BOSS_R
              and py0 - BOSS_R < s[1] < py1 + BOSS_R]
    check("boss-pocket-fit",
          not inside,
          f"{len(inside)} boss(es) inside pocket footprint"
          + (f" {inside}" if inside else ""))

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
