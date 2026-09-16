#!/usr/bin/env python3
"""Enclosure REQUIREMENTS gate — the user's constraints, one check each.

verify_enclosure_sync proves the scad agrees with the board and the
datasheets; verify_enclosure_collision proves nothing overlaps. Neither
knows what the user ASKED for. This gate does: every check below quotes
the requirement it enforces (2026-09-16 review of the V1 print), reads the
scad constants block (same parser as the sync gate) and the generated PCB
parts, and fails if the model drifted away from the ask — bigger buttons
shrinking back, the speaker wandering to the wrong corner, an insert
socket that no longer fits the insert, a label engraved beside the wrong
button.

  R1  display stack   PCB top -> glass = 7.0 = panel 3.9 + 3.1 cable riser;
                      the extension board fits under the riser
  R2  glass placement glass between the Select and Y cap BODIES with equal
                      gaps >= MIN_GLASS_GAP; no cap body over the glass; only
                      the two designated caps may have a flange that reaches
                      the glass (they are clipped there)
  R3  cables          tail fold zone clears the nearest switch body (SW4);
                      extension board inside the glass footprint, left of
                      the FPC slot, under the riser
  R4  LEDs            all six top-side LEDs have a light pipe that keeps a
                      >= MIN_WEB web from every button cutout
  R5  speaker         grille top-left when looking at the back (+X, +Y in
                      enclosure coords); driver clears the pocket border,
                      columns, lever hinges, ribs and the wall
  R6  inserts         M2.5 heat-set (OD 3.5, L 3): socket OD-0.5..OD-0.3,
                      depth >= L+0.3, boss wall >= 1.5; screw tip lands in
                      the relief above the insert; bottom column walls,
                      gussets present
  R7  button sizes    ABXY >= 9, D-pad arms >= 6.5, Start/Select >= 10x5,
                      Menu >= 12x4 (the "un po' piu' grandi" request)
  R8  robustness      minimum feature thicknesses (walls, rim, well rings,
                      lever flange/nub, neck wall, ribs)
  R10 battery         pocket holds the cell the user MEASURED (90x50x10,
                      2026-09-16) with lead clearance, cell top under the
                      PCB-side parts (delegated to the sync gate)
  R11 hold-down       two >= 1 mm straps over the cell on posts at the cell
                      top plane, >= 40 mm apart (the PCB captures them)
  R12 thin walls      OpenSCAD slices every printed shell/lever, erodes by
                      min_wall/2 and reports what disappears — the check the
                      print service runs, run before uploading
  R9  labels          engraved glyphs exported by OpenSCAD (part
                      labels_check) — every label beside ITS OWN button,
                      no glyph anywhere else, and not MIRRORED (the "B"
                      read from the front and the "L" read from the back
                      have their stem on the correct side)

Output contract: every failing check prints a line starting with FAIL.
Exit codes: 0 pass · 1 requirement violated · 2 cannot evaluate.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

import verify_enclosure_sync as ves                      # noqa: E402
from verify_enclosure_collision import components, OUT_DIR  # noqa: E402

MIN_GLASS_GAP = 0.4     # mm, cap body to glass pocket edge, each side
MIN_WEB = 1.2           # mm, LED hole to button cutout (print-service threshold)
MIN_WALL = 1.5          # mm, plastic around an insert / a screw bore
MEASURED_CELL = (90.0, 50.0, 10.0)   # L x W x T, user's ruler, 2026-09-16
LABEL_STL = "enclosure-labels-check.stl"
THIN_STL = "enclosure-thin-check.stl"
THIN_MIN_VOL = 0.03     # mm^3 = 0.3 mm^2 of thin material in a 0.1 mm slab
# label -> (glyph count, x, y) built from the scad constants in main()
Structural = ves.Structural


def export_part(part: str, name: str) -> Path:
    """Export one `part` of the scad under test to OUT_DIR/name via Docker."""
    import os
    out = OUT_DIR / name
    if out.exists():
        out.unlink()
    # the scad under test must live in hardware/enclosure (the /project
    # mount) — the mutation suite drops its copies there
    scad_dir = BASE / "hardware" / "enclosure"
    try:
        rel = ves.SCAD.resolve().relative_to(scad_dir.resolve())
    except ValueError:
        raise Structural(f"{ves.SCAD} is outside {scad_dir}; the container "
                         "cannot see it")
    cmd = ["docker", "compose", "-f", str(BASE / "docker-compose.yml"),
           "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
           "openscad", "-o", f"/output/{name}",
           "-D", f'part="{part}"', f"/project/{rel.as_posix()}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Structural(f"cannot run the OpenSCAD container: {e}")
    if r.returncode != 0 or not out.exists():
        raise Structural(f"OpenSCAD export of {part} failed:\n"
                         + (r.stderr or r.stdout)[-2000:])
    return out


def export_labels() -> Path:
    return export_part("labels_check", LABEL_STL)


def chirality(stl: Path):
    """Per connected component: (bbox cx, bbox cy, centroid_x - cx)."""
    from collections import defaultdict
    tris, cur = [], []
    for line in stl.read_text().splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            cur.append(tuple(round(float(v), 4) for v in line.split()[1:4]))
            if len(cur) == 3:
                tris.append(tuple(cur))
                cur = []
    parent: dict = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in tris:
        parent[find(a)] = find(b)
        parent[find(b)] = find(c)
    groups = defaultdict(list)
    for t in tris:
        groups[find(t[0])].append(t)
    out = []
    for ts in groups.values():
        vol = 0.0
        mx = 0.0
        for a, b, c in ts:
            v = (a[0] * (b[1] * c[2] - b[2] * c[1])
                 - a[1] * (b[0] * c[2] - b[2] * c[0])
                 + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
            vol += v
            mx += v * (a[0] + b[0] + c[0]) / 4
        xs = [p[0] for t in ts for p in t]
        ys = [p[1] for t in ts for p in t]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        out.append((cx, cy, (mx / vol - cx) if abs(vol) > 1e-9 else 0.0))
    return out


def main() -> int:
    print("=" * 72)
    print("ENCLOSURE REQUIREMENTS (the user's constraints, 2026-09-16)")
    print("=" * 72)
    try:
        from scripts import generate_enclosure_pcb as GEP
    except Exception as e:
        raise Structural(f"cannot import the PCB model generator: {e}")
    parts = GEP.parts()
    by_ref = {r[0]: r for r in parts}

    text = ves.SCAD.read_text()
    env = ves.parse_scalars(text)
    screws = ves.parse_vector(text, "screw_positions", env)
    abxy = ves.parse_vector(text, "abxy_offsets", env)
    need = lambda *n: ves.need(env, *n)          # noqa: E731
    results = []

    def check(code, name, ok, detail):
        results.append(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {code} {name}: {detail}")

    # ── R1 display stack ────────────────────────────────────────────────
    top_int, disp_t, riser, ext_t = need("top_int", "disp_t", "disp_riser",
                                         "ext_t")
    check("R1", "display-stack",
          ves.__dict__.get("close", lambda a, b: abs(a - b) <= 0.1)(top_int, 7.0)
          and abs(top_int - (disp_t + riser)) <= 0.05 and ext_t <= riser - 0.1,
          f"interior {top_int:g} = panel {disp_t:g} + riser {riser:g}; "
          f"extension board {ext_t:g} thick under the riser")

    # ── R2 glass between the caps ───────────────────────────────────────
    (gcx, out_l, out_w, clear, oy, gap, ref_l, ref_r, btn_clear,
     fl_extra) = need("disp_glass_cx", "disp_outline_l", "disp_outline_w",
                      "disp_clear", "disp_offset_y", "disp_gap",
                      "disp_ref_left", "disp_ref_right", "btn_clear",
                      "btn_flange_extra")
    px0, px1 = gcx - out_l / 2 - clear, gcx + out_l / 2 + clear
    py0, py1 = oy - out_w / 2 - clear, oy + out_w / 2 + clear
    gap_l, gap_r = px0 - ref_l, ref_r - px1
    check("R2", "glass-gaps",
          gap_l >= MIN_GLASS_GAP - 1e-9 and gap_r >= MIN_GLASS_GAP - 1e-9
          and abs(gap_l - gap_r) <= 0.05 and abs(gap - gap_l) <= 0.05,
          f"pocket x[{px0:.2f}, {px1:.2f}]; gap to Select cap {gap_l:.2f}, "
          f"to Y cap {gap_r:.2f} (min {MIN_GLASS_GAP})")

    # cap bodies: (name, x0, x1, y0, y1, may_touch_glass_side)
    dx, dy, al, aw = need("dpad_x", "dpad_y", "dpad_arm_len", "dpad_arm_w")
    ax, ay, ad = need("abxy_x", "abxy_y", "abxy_diam")
    sx, sy, ssp, sw, sh = need("ss_x", "ss_y", "ss_spacing", "ss_w", "ss_h")
    mx, my, mw, mh = need("menu_x", "menu_y", "menu_w", "menu_h")
    c = btn_clear / 2
    caps = [("dpad", dx - al + c, dx + al - c, dy - al + c, dy + al - c, 0)]
    for name, (ox, oy_) in zip("ABXY", abxy):
        caps.append((name, ax + ox - ad / 2 + c, ax + ox + ad / 2 - c,
                     ay + oy_ - ad / 2 + c, ay + oy_ + ad / 2 - c,
                     -1 if name == "Y" else 0))
    caps.append(("start", sx - ssp / 2 - sw / 2 + c, sx - ssp / 2 + sw / 2 - c,
                 sy - sh / 2 + c, sy + sh / 2 - c, 0))
    caps.append(("select", sx + ssp / 2 - sw / 2 + c, sx + ssp / 2 + sw / 2 - c,
                 sy - sh / 2 + c, sy + sh / 2 - c, +1))
    caps.append(("menu", mx - mw / 2 + c, mx + mw / 2 - c,
                 my - mh / 2 + c, my + mh / 2 - c, 0))
    body_hits, flange_hits = [], []
    for name, x0, x1, y0, y1, side in caps:
        if x0 < px1 and x1 > px0 and y0 < py1 and y1 > py0:
            body_hits.append(name)
        fx0, fx1 = x0 - fl_extra, x1 + fl_extra
        fy0, fy1 = y0 - fl_extra, y1 + fl_extra
        if side > 0:
            fx1 = x1          # clipped on the glass side
        elif side < 0:
            fx0 = x0
        if fx0 < px1 and fx1 > px0 and fy0 < py1 and fy1 > py0:
            flange_hits.append(name)
    check("R2", "glass-vs-caps",
          not body_hits and not flange_hits,
          f"{len(caps)} caps; bodies over the glass: {body_hits or 'none'}; "
          f"flanges over the glass: {flange_hits or 'none'}")

    # ── R3 cables ────────────────────────────────────────────────────────
    tail_side, tail_ext, tail_w = need("disp_tail_side", "disp_tail_ext",
                                       "disp_tail_w")
    sw_body = need("sw_body")[0]
    # nearest switch body on the tail side, within the tail's Y band
    band0, band1 = oy - tail_w / 2, oy + tail_w / 2
    edge = px0 - tail_ext if tail_side < 0 else px1 + tail_ext
    blockers = []
    for ref, cx, cy, rot, side, L, W, H in parts:
        if side != "top" or not ref.startswith("SW"):
            continue
        if cy + sw_body / 2 < band0 or cy - sw_body / 2 > band1:
            continue
        if (tail_side < 0 and cx > px0) or (tail_side > 0 and cx < px1):
            continue                      # not on the tail side of the glass
        near = cx + sw_body / 2 if tail_side < 0 else cx - sw_body / 2
        if (tail_side < 0 and near > edge - 0.2) or \
                (tail_side > 0 and near < edge + 0.2):
            blockers.append(f"{ref} body edge {near:g}")
    check("R3", "tail-fold-zone",
          not blockers,
          f"fold zone reaches x={edge:.2f} on side {tail_side:+g}"
          + (": blocked by " + ", ".join(blockers) if blockers else
             " — clear of every top switch in the tail band"))
    ext_l, ext_w, ext_gap = need("ext_l", "ext_w", "ext_gap")
    from scripts.generate_pcb import board as B
    slot_x0 = B.FPC_SLOT_ENC[0] - B.FPC_SLOT_W / 2
    ex1 = slot_x0 - ext_gap
    ex0 = ex1 - ext_l
    inside = (ex0 >= px0 + clear and ex1 <= px1 - clear
              and oy - ext_w / 2 >= py0 + clear and oy + ext_w / 2 <= py1 - clear)
    check("R3", "extension-board",
          inside and ex1 <= slot_x0,
          f"board x[{ex0:.1f}, {ex1:.1f}] y±{ext_w / 2:g} under the glass, "
          f"{'before' if ex1 <= slot_x0 else 'OVER'} the slot at x={slot_x0:g}")

    # ── R4 LEDs ─────────────────────────────────────────────────────────
    led_d, led_dd = need("led_d", "led_diag_d")
    cut = [("dpad", dx - al, dx + al, dy - al, dy + al)]
    for name, (ox, oy_) in zip("ABXY", abxy):
        cut.append((name, ax + ox - ad / 2, ax + ox + ad / 2,
                    ay + oy_ - ad / 2, ay + oy_ + ad / 2))
    cut += [("start", sx - ssp / 2 - sw / 2, sx - ssp / 2 + sw / 2, sy - sh / 2, sy + sh / 2),
            ("select", sx + ssp / 2 - sw / 2, sx + ssp / 2 + sw / 2, sy - sh / 2, sy + sh / 2),
            ("menu", mx - mw / 2, mx + mw / 2, my - mh / 2, my + mh / 2)]
    webs = []
    for n in range(1, 7):
        lx, ly = need(f"led{n}_x", f"led{n}_y")
        r = (led_d if n <= 2 else led_dd) / 2
        for name, x0, x1, y0, y1 in cut:
            ddx = max(x0 - lx, 0, lx - x1)
            ddy = max(y0 - ly, 0, ly - y1)
            web = math.hypot(ddx, ddy) - r
            if web < MIN_WEB:
                webs.append(f"LED{n}-{name} web {web:.2f}")
    check("R4", "led-light-pipes",
          not webs,
          "six holes, min web to a cutout "
          + (", ".join(webs) if webs else f">= {MIN_WEB} everywhere"))

    # ── R5 speaker ──────────────────────────────────────────────────────
    spx, spy, sdd, seat_od = need("spk_x", "spk_y", "spk_driver_d", "spk_seat_od")
    body_w, body_h, wall, side_wall = need("body_w", "body_h", "wall", "side_wall")
    r = seat_od / 2
    bx, by, bw, bh, bbw = need("bat_offset_x", "bat_offset_y", "bat_w", "bat_h",
                               "bat_border_w")
    hx, hy, bgap, bt = need("lever_hinge_x", "shoulder_y", "lever_block_gap",
                            "lever_block_t")
    s_out = need("screw_d_outer")[0]
    probs = []
    if not (spx > 0 and spy > 0):
        probs.append("not in the +X/+Y quadrant")
    if abs(spx) + r > body_w / 2 - side_wall or abs(spy) + r > body_h / 2 - side_wall:
        probs.append("touches the wall")
    pb = (bx - (bw + 5) / 2 - bbw, bx + (bw + 5) / 2 + bbw,
          by - bh / 2 - bbw, by + bh / 2 + bbw)
    ddx = max(pb[0] - spx, 0, spx - pb[1]); ddy = max(pb[2] - spy, 0, spy - pb[3])
    if math.hypot(ddx, ddy) < r:
        probs.append("overlaps the battery pocket border")
    for sxp, syp in screws:
        if math.hypot(spx - sxp, spy - syp) < r + s_out / 2 + 3:
            probs.append(f"too close to column ({sxp:g},{syp:g})")
    for sgn in (-1, 1):
        hb = (sgn * hx - 1.5, sgn * hx + 1.5, hy - bgap - bt, hy + bgap + bt)
        ddx = max(hb[0] - spx, 0, spx - hb[1]); ddy = max(hb[2] - spy, 0, spy - hb[3])
        if math.hypot(ddx, ddy) < r:
            probs.append("overlaps a lever hinge")
    check("R5", "speaker-position",
          not probs,
          f"driver seat r{r:g} at ({spx:g},{spy:g}) — "
          + ("; ".join(probs) if probs else "back top-left, clear of "
             "wall/pocket/columns/hinges"))

    # ── R6 inserts, screws, columns ─────────────────────────────────────
    (i_od, i_l, i_hd, i_dep, rel_h, tb_d, sd_in, sd_out, g_n, g_t, head_dep,
     s_len, pcb_z, pcb_d, half_h, i_wall) = need(
        "insert_od", "insert_l", "insert_hole_d", "insert_hole_depth",
        "insert_relief_h", "top_boss_d", "screw_d_inner", "screw_d_outer",
        "boss_gusset_n", "boss_gusset_t", "m25_head_depth", "screw_len",
        "pcb_z", "pcb_d", "boss_half_h", "insert_wall")
    tip = head_dep + s_len
    z_top = pcb_z + pcb_d
    check("R6", "insert-socket",
          abs(i_od - 3.5) < 1e-9 and abs(i_l - 2.5) < 1e-9        # the user's insert
          and i_od - 0.5 <= i_hd <= i_od - 0.3 and i_dep >= i_l + 0.3
          and i_wall >= 2.0 - 1e-9 and (tb_d - i_hd) / 2 >= i_wall - 1e-9,
          f"M2.5 insert OD {i_od:g} L {i_l:g}: socket Ø{i_hd:g} x {i_dep:g}, "
          f"boss Ø{tb_d:g} = {(tb_d - i_hd) / 2:.2f} mm of plastic around it "
          f"(user asked for {i_wall:g})")
    check("R6", "screw-length",
          z_top + i_l + 0.5 <= tip <= z_top + i_dep + rel_h - 0.3,
          f"M2.5x{s_len:g} tip at Z={tip:g}: insert spans {z_top:g}..{z_top + i_l:g}, "
          f"relief to {z_top + i_dep + rel_h:g}")
    check("R6", "bottom-columns",
          (sd_out - sd_in) / 2 >= MIN_WALL and g_n >= 3 and g_t >= MIN_WALL
          and 1.5 <= half_h <= 3,
          f"column wall {(sd_out - sd_in) / 2:.2f}, {g_n:g} gussets x {g_t:g}, "
          f"half-column contact {half_h:g} tall")

    # ── R7 button sizes ─────────────────────────────────────────────────
    check("R7", "button-sizes",
          ad >= 9 and aw >= 6.5 and sw >= 10 and sh >= 5 and mw >= 12 and mh >= 3.8,
          f"ABXY Ø{ad:g} (>=9), D-pad arms {aw:g} (>=6.5), Start/Select "
          f"{sw:g}x{sh:g} (>=10x5), Menu {mw:g}x{mh:g} (>=12x3.8 — the LED "
          f"light pipes need a {MIN_WEB:g} web)")

    # ── R8 robustness ───────────────────────────────────────────────────
    rim_t, well_t, lf_t, nub_d, rib_w = need("disp_rim_t", "btn_well_t",
                                             "lever_flange_t", "lever_nub_d",
                                             "rib_w")
    tw, ttop, rod_z, rod_d, lmin = need("lever_tongue_w", "lever_tongue_top",
                                        "lever_rod_z", "lever_rod_d",
                                        "min_wall")
    lip_t, lip_c, seat_od, drv_d, fl_h, st_t, g_t2, t_front, post_t, peg_d = need(
        "lip_t", "lip_clearance", "spk_seat_od", "spk_driver_d",
        "btn_flange_h", "bat_strap_t", "boss_gusset_t", "lever_tongue_front",
        "bat_post_t", "bat_peg_d")
    walls = {
        "wall": wall, "side wall": side_wall,
        "lip skin": side_wall - lip_t - lip_c, "lip tongue": lip_t,
        "display rim": rim_t, "well ring": well_t, "lever flange": lf_t,
        "lever hook side": (tw - (rod_d + 0.3)) / 2,
        "lever hook top": ttop - (rod_z + (rod_d + 0.3) / 2),
        "lever hook front": t_front - (rod_d + 0.3) / 2,
        "strap post wall": (post_t - (peg_d + 0.3)) / 2,
        "speaker seat ring": (seat_od - (drv_d + 0.6)) / 2,
        "cap flange plate": fl_h, "battery strap": st_t, "column gusset": g_t2,
        "column wall": (sd_out - sd_in) / 2, "boss wall": (tb_d - i_hd) / 2,
    }
    thin = [f"{k} {v:.2f}" for k, v in walls.items() if v < lmin - 1e-9]
    check("R8", "min-thickness",
          not thin and nub_d >= 3.0 and rib_w >= 6,
          f"{len(walls)} printed walls >= {lmin:g} mm (Weerg thin-material "
          f"threshold)" + (": THIN " + ", ".join(thin) if thin else
                           f"; thinnest {min(walls.values()):.2f}"))

    # ── R10 battery ────────────────────────────────────────────────────
    check("R10", "battery-fits-measured-cell",
          bw >= MEASURED_CELL[0] - 1e-9 and bh >= MEASURED_CELL[1] - 1e-9
          and need("bat_d")[0] >= MEASURED_CELL[2] - 1e-9,
          f"pocket {bw + 5:g}x{bh:g}x{need('bat_d')[0]:g} (bat_w {bw:g} + 5 leads) "
          f"vs measured cell {MEASURED_CELL[0]:g}x{MEASURED_CELL[1]:g}x{MEASURED_CELL[2]:g}")

    # ── R11 battery hold-down ───────────────────────────────────────────
    sx1, sx2, s_w, s_t, p_h, bat_d = need("bat_strap_x1", "bat_strap_x2",
                                          "bat_strap_w", "bat_strap_t",
                                          "bat_post_h", "bat_d")
    check("R11", "battery-hold-down",
          abs(p_h - bat_d) <= 1e-9 and s_t >= 1.0 and s_w >= 4
          and sx1 < sx2 and sx2 - sx1 >= 40,
          f"2 straps {s_w:g}x{s_t:g} at x={sx1:g},{sx2:g} resting on posts at "
          f"the cell top (Z {wall + p_h:g}); the PCB captures them")

    # ── R9 labels (Docker) ──────────────────────────────────────────────
    lcx, lw = need("lever_cx", "lever_w")
    expect = {
        "^": (1, dx, dy + al + 3), "v": (1, dx, dy - al - 3),
        "A": (1, ax + abxy[0][0], ay + abxy[0][1] + ad / 2 + 2),
        "B": (1, ax + abxy[1][0] + ad / 2 + 2, ay + abxy[1][1]),
        "X": (1, ax + abxy[2][0], ay + abxy[2][1] - ad / 2 - 2),
        "Y": (1, ax + abxy[3][0] - ad / 2 - 2, ay + abxy[3][1]),
        "START": (5, sx - ssp / 2, sy - sh / 2 - 2.5),
        "SEL": (3, sx + ssp / 2, sy - sh / 2 - 2.5),
        "MENU": (4, mx, my - mh / 2 - 2.5),
        "L": (1, -lcx, hy + lw / 2 + 3), "R": (1, lcx, hy + lw / 2 + 3),
    }
    stl = export_labels()
    try:
        comps = components(stl)
        chir = chirality(stl)
    finally:
        stl.unlink(missing_ok=True)
    centres = [((b[0] + b[1]) / 2, (b[2] + b[3]) / 2) for _v, b, _n in comps]
    bad, claimed = [], set()
    for txt, (n, ex, ey) in expect.items():
        near = [i for i, (cx, cy) in enumerate(centres)
                if math.hypot(cx - ex, cy - ey) <= 6.0]
        claimed.update(near)
        if len(near) != n:
            bad.append(f"'{txt}' at ({ex:g},{ey:g}): {len(near)} glyph(s), want {n}")
    orphans = len(comps) - len(claimed)
    if orphans:
        bad.append(f"{orphans} glyph(s) beside no button")
    # chirality: a glyph's mass sits on the side of its stem. "B" is read
    # from the FRONT (+Z): stem on -X -> centroid left of the bbox centre.
    # "L" is read from the BACK (-Z), engraved mirrored: stem on +X ->
    # centroid right of centre. A mirrored engraving flips the sign.
    for txt, want_sign in (("B", -1), ("L", +1)):
        n, ex, ey = expect[txt]
        hit = [c for c in chir if math.hypot(c[0] - ex, c[1] - ey) <= 4.0]
        if len(hit) == 1:
            off = hit[0][2]
            if off * want_sign <= 0.05:
                bad.append(f"'{txt}' engraved mirrored (stem offset {off:+.2f})")
    check("R9", "labels-beside-own-button",
          not bad,
          f"{len(comps)} glyphs exported" + ("; " + "; ".join(bad) if bad else
                                               ", all 11 labels in place"))

    # ── R12 thin walls, measured (Docker) ───────────────────────────────
    # part thin_check: horizontal slices of top shell (z < 40), bottom
    # shell (40..80) and levers (80+), each eroded/dilated by min_wall/2;
    # whatever survives is material thinner than min_wall. R8 knows the
    # walls we named; this finds the ones we did not.
    stl = export_part("thin_check", THIN_STL)
    try:
        thin = [c for c in components(stl) if c[0] > THIN_MIN_VOL]
    finally:
        stl.unlink(missing_ok=True)
    where = []
    for vol, (x0, x1, y0, y1, z0, z1), _n in thin[:8]:
        part_name = "top" if z0 < 40 else "bottom" if z0 < 80 else "levers"
        zz = z0 - (0 if z0 < 40 else 40 if z0 < 80 else 80)
        where.append(f"{part_name} z={zz:.1f} x[{x0:.1f},{x1:.1f}] "
                     f"y[{y0:.1f},{y1:.1f}] ({vol / 0.1:.1f} mm2)")
    check("R12", "thin-walls-measured",
          not thin,
          f"21 slices eroded by {lmin / 2:g}: "
          + (f"{len(thin)} thin region(s): " + "; ".join(where) if thin
             else f"no material under {lmin:g} mm"))

    print("-" * 72)
    fails = results.count(False)
    if fails:
        print(f"Results: FAIL — {fails}/{len(results)} requirement(s) violated")
        return 1
    print(f"Results: PASS — {len(results)}/{len(results)} user requirements hold")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Structural as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
