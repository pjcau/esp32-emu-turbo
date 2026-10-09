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
  R5  speaker         on the player's LEFT = the D-pad side (-X, +Y in
                      enclosure coords; user 2026-10-07); driver clears
                      the pocket border, columns, the L lever's pivot
                      blocks and the filleted inner floor outline
  R6  inserts         M2.5 heat-set HANGLIFE D3.5 x L4: socket OD-0.5..OD-0.3,
                      depth >= L+0.3, boss wall >= 1.5; screw tip lands in
                      the relief above the insert; bottom column walls,
                      gussets present
  R7  button sizes    ABXY >= 9, D-pad arms >= 6.5, Start/Select >= 10x5,
                      Menu >= 12x4 (the "un po' piu' grandi" request)
  R8  robustness      minimum feature thicknesses (walls, rim, well rings,
                      L/R cap flange, L/R lever + pivot blocks, slider plates, recess
                      floors, fillet walls, ribs)
  R10 battery         pocket holds the cell the user MEASURED (90x50x10,
                      2026-09-16) with lead clearance, cell top under the
                      PCB-side parts (delegated to the sync gate)
  R11 hold-down       two >= 1 mm straps over the cell on posts at the cell
                      top plane, >= 40 mm apart (the PCB captures them)
  R12 thin walls      OpenSCAD slices every printed shell/edge cap, erodes
                      by min_wall/2 and reports what disappears — the check
                      the print service runs, run before uploading
  R13 edge recesses   (user 2026-10-07) USB-C opening recessed >= 2 mm;
                      the SD card keeps the V2.1 16 x 3.5 slit (the V3
                      window was reverted 2026-10-08); SW16's knob driven by the printed
                      slider (a finger cannot reach it: 5.1 mm inside)
  R14 proud caps      (user 2026-10-07) face caps >= 2 mm proud with a
                      rounded head; L/R caps 2-3 mm proud, rounded
  R15 rounded shell   (user 2026-10-07, Switch Lite) corners >= 10, back
                      fillet >= 6, front fillet >= 1.5, fillet walls >= min_wall
  R9  labels          engraved glyphs exported by OpenSCAD (part
                      labels_check) — every label beside ITS OWN button,
                      no glyph anywhere else, and not MIRRORED (the "B"
                      read from the front and the "L" read from the back
                      have their stem on the correct side), and VISIBLE: no
                      glyph under the raised display bezel

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
    """Export one `part` of the scad under test via Docker to a file named
    after `name` but UNIQUE per call; the caller deletes it.

    A fixed name, unlinked and rewritten on every call, races the OrbStack
    bind mount: the host intermittently missed the fresh file and the gate
    reported an empty "export failed" (exit 2) on a random mutation case —
    the same race verify_enclosure_stl fixed with unique names."""
    import os
    import time
    stem, ext = name.rsplit(".", 1)
    name = f"{stem}-{os.getpid()}-{time.monotonic_ns()}.{ext}"
    out = OUT_DIR / name
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
        raise Structural(f"OpenSCAD export of {part} failed (exit {r.returncode}, "
                         f"{'file present' if out.exists() else 'no file'}):\n"
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
    print("ENCLOSURE REQUIREMENTS (the user's constraints, 2026-09-16 + 2026-10-07)")
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
    back_r, bx0_, bx1_, b_gap, b_t, piv_y, slot_w_, b_wall = need(
        "back_r", "lr_beam_x0", "lr_beam_x1", "lr_blk_gap", "lr_blk_t", "lr_piv_y",
        "lr_slot_w", "lr_blk_wall")
    s_out = need("screw_d_outer")[0]
    probs = []
    if not (spx < 0 and spy > 0):
        probs.append("not in the -X/+Y quadrant (player's left = D-pad side)")
    if abs(spx) + r > body_w / 2 - side_wall or abs(spy) + r > body_h / 2 - side_wall:
        probs.append("touches the wall")
    # the floor's inner outline is inset back_r by the fillet: the driver
    # (which sits ON the floor) must stay inside it
    if abs(spx) + sdd / 2 > body_w / 2 - back_r + 1e-9 or abs(spy) + sdd / 2 > body_h / 2 - back_r + 1e-9:
        probs.append("driver edge inside the back fillet")
    pb = (bx - (bw + 5) / 2 - bbw, bx + (bw + 5) / 2 + bbw,
          by - bh / 2 - bbw, by + bh / 2 + bbw)
    ddx = max(pb[0] - spx, 0, spx - pb[1]); ddy = max(pb[2] - spy, 0, spy - pb[3])
    if math.hypot(ddx, ddy) < r:
        probs.append("overlaps the battery pocket border")
    for sxp, syp in screws:
        if math.hypot(spx - sxp, spy - syp) < r + s_out / 2 + 3:
            probs.append(f"too close to column ({sxp:g},{syp:g})")
    # the L/R lever's pivot blocks (the outermost, lowest-standing L/R parts)
    for sgn in (-1, 1):
        hb = (min(sgn * (bx0_ - b_gap - b_t), sgn * (bx1_ + b_gap + b_t)),
              max(sgn * (bx0_ - b_gap - b_t), sgn * (bx1_ + b_gap + b_t)),
              piv_y - slot_w_ / 2 - b_wall, body_h / 2 - side_wall)
        ddx = max(hb[0] - spx, 0, spx - hb[1]); ddy = max(hb[2] - spy, 0, spy - hb[3])
        if math.hypot(ddx, ddy) < r:
            probs.append("overlaps an L/R lever")
    check("R5", "speaker-position",
          not probs,
          f"driver seat r{r:g} at ({spx:g},{spy:g}) — "
          + ("; ".join(probs) if probs else "player's left (D-pad side), clear of "
             "wall/fillet/pocket/columns/L-R levers"))

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
          abs(i_od - 3.5) < 1e-9 and abs(i_l - 4.0) < 1e-9        # HANGLIFE M2.5 x D3.5 x L4
          and i_od - 0.5 <= i_hd <= i_od - 0.3 and i_dep >= i_l + 0.3
          and i_wall >= 2.0 - 1e-9 and (tb_d - i_hd) / 2 >= i_wall - 1e-9,
          f"M2.5 insert OD {i_od:g} L {i_l:g}: socket Ø{i_hd:g} x {i_dep:g}, "
          f"boss Ø{tb_d:g} = {(tb_d - i_hd) / 2:.2f} mm of plastic around it "
          f"(user asked for {i_wall:g})")
    check("R6", "screw-length",
          z_top + i_l <= tip <= z_top + i_dep + rel_h - 0.3
          and i_dep + rel_h <= top_int - 0.3,
          f"M2.5x{s_len:g} tip at Z={tip:g}: insert spans {z_top:g}..{z_top + i_l:g} "
          f"(full engagement), relief to {z_top + i_dep + rel_h:g}; hole {i_dep + rel_h:g} "
          f"of the {top_int:g} mm boss")
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
    rim_t, well_t, rib_w, lmin = need("disp_rim_t", "btn_well_t", "rib_w", "min_wall")
    lip_t, lip_c, seat_od, drv_d, fl_h, st_t, g_t2, post_t, peg_d = need(
        "lip_t", "lip_clearance", "spk_seat_od", "spk_driver_d",
        "btn_flange_h", "bat_strap_t", "boss_gusset_t",
        "bat_post_t", "bat_peg_d")
    (lr_fl_t, lr_blk_wall, lr_arm_top, lr_arm_z0, lr_in_y0, lr_in_y1, lr_beam_y0,
     lr_beam_y1, lr_beam_z0, lr_arm_w, lr_in_w, pwr_fl_t, pwr_fork_t, pwr_tab_h, u_rd,
     u_pad, front_r) = need(
        "lr_fl_t", "lr_blk_wall", "lr_arm_top", "lr_arm_z0", "lr_in_y0", "lr_in_y1",
        "lr_beam_y0", "lr_beam_y1", "lr_beam_z0", "lr_arm_w", "lr_in_w", "pwr_fl_t",
        "pwr_fork_t", "pwr_tab_h", "usbc_recess_d", "usbc_pad_t", "front_r")
    # front fillet: outer arc centre (front_r, front_r) from the edge/face,
    # inner cavity corner at (side_wall, wall) -> wall = R - distance
    front_fillet_wall = front_r - math.hypot(side_wall - front_r, wall - front_r)
    walls = {
        "wall": wall, "side wall": side_wall,
        "lip skin": side_wall - lip_t - lip_c, "lip tongue": lip_t,
        "display rim": rim_t, "well ring": well_t,
        "L/R cap flange": lr_fl_t, "L/R pivot slot wall": lr_blk_wall,
        "L/R upper arm (Z)": lr_arm_top - lr_arm_z0, "L/R upper arm (X)": lr_arm_w,
        "L/R lower arm (Y)": lr_in_y1 - lr_in_y0, "L/R lower arm (X)": lr_in_w,
        "L/R beam (Y)": lr_beam_y1 - lr_beam_y0, "L/R beam (Z)": lr_arm_top - lr_beam_z0,
        "slider flange": pwr_fl_t, "slider fork arm": pwr_fork_t, "slider tab": pwr_tab_h,
        "slider guide lip": need("pwr_guide_lip")[0], "slider guide stop": need("pwr_guide_stop")[0],
        "USB recess floor": side_wall + u_pad - u_rd,
        "front fillet wall": front_fillet_wall, "back fillet wall": min(wall, side_wall),
        "strap post wall": (post_t - (peg_d + 0.3)) / 2,
        "speaker seat ring": (seat_od - (drv_d + 0.6)) / 2,
        "cap flange plate": fl_h, "battery strap": st_t, "column gusset": g_t2,
        "column wall": (sd_out - sd_in) / 2, "boss wall": (tb_d - i_hd) / 2,
    }
    thin = [f"{k} {v:.2f}" for k, v in walls.items() if v < lmin - 1e-9]
    check("R8", "min-thickness",
          not thin and rib_w >= 6,
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
    lr_x, lr_ly = need("lr_x", "lr_label_y")
    expect = {
        "^": (1, dx, dy + al + 3), "v": (1, dx, dy - al - 3),
        "<": (1, dx - al - 3, dy), ">": (1, dx + al + 3, dy),
        "A": (1, ax + abxy[0][0], ay + abxy[0][1] + ad / 2 + 2),
        "B": (1, ax + abxy[1][0] + ad / 2 + 2, ay + abxy[1][1]),
        "X": (1, ax + abxy[2][0], ay + abxy[2][1] - ad / 2 - 2),
        # Y above its cap: on its left it sat under the raised bezel
        "Y": (1, ax + abxy[3][0], ay + abxy[3][1] + ad / 2 + 2),
        "START": (5, sx - ssp / 2, sy - sh / 2 - 2.5),
        "SEL": (3, sx + ssp / 2, sy - sh / 2 - 2.5),
        "MENU": (4, mx, my - mh / 2 - 2.5),
        "L": (1, -lr_x, lr_ly), "R": (1, lr_x, lr_ly),
    }
    # brand banners (user 2026-10-08): glyph count inside a box round the
    # string's centre; the front one is read from +Z, the back one from -Z
    b_fy, b_fs, b_by, b_bs, disp_x_ = need("brand_front_y", "brand_front_size",
                                           "brand_back_y", "brand_back_size", "disp_x")
    banners = {"GAME BRO!": (9, disp_x_, b_fy, 6 * b_fs, b_fs),    # the "!" is 2 glyphs
               "CPJ & CP 2026": (10, 0.0, b_by, 7 * b_bs, b_bs)}
    stl = export_labels()
    try:
        comps = components(stl)
        chir = chirality(stl)
    finally:
        stl.unlink(missing_ok=True)
    centres = [((b[0] + b[1]) / 2, (b[2] + b[3]) / 2) for _v, b, _n in comps]
    bad, claimed, back = [], set(), set()   # back: glyphs on the BACK face
    for txt, (n, bx, by_, hw, hh) in banners.items():
        inside = [i for i, (cx, cy) in enumerate(centres)
                  if abs(cx - bx) <= hw and abs(cy - by_) <= hh]
        claimed.update(inside)
        if txt.startswith("CPJ"):
            back.update(inside)
        if len(inside) != n:
            bad.append(f"'{txt}' at ({bx:g},{by_:g}): {len(inside)} glyph(s), want {n}")
            continue
        # chirality of one asymmetric glyph: the "B" of GAME BRO! (5th from
        # the left, read from the front: stem on -X -> centroid left) and
        # the "J" of CPJ (3rd from the +X end: the string is engraved
        # mirrored for the back, so the J's stem is on -X -> centroid left)
        order = sorted(inside, key=lambda i: centres[i][0])
        pick, want_sign = (order[4], -1) if txt.startswith("GAME") else (order[-3], -1)
        hit = [c for c in chir if math.hypot(c[0] - centres[pick][0], c[1] - centres[pick][1]) <= 1.0]
        if len(hit) == 1 and hit[0][2] * want_sign <= 0.05:
            bad.append(f"'{txt}' engraved mirrored (stem offset {hit[0][2]:+.2f})")
    for txt, (n, ex, ey) in expect.items():
        near = [i for i, (cx, cy) in enumerate(centres)
                if math.hypot(cx - ex, cy - ey) <= 6.0]
        claimed.update(near)
        if txt in ("L", "R"):
            back.update(near)
        if len(near) != n:
            bad.append(f"'{txt}' at ({ex:g},{ey:g}): {len(near)} glyph(s), want {n}")
    # visible: a glyph engraved where the raised display bezel stands is
    # swallowed by it (the Y of V3 at x 46.5) — no glyph may touch the
    # bezel's outer rectangle (viewport + clearance + bezel width); the
    # back-face glyphs (L, R, the CPJ line) are on the other shell
    vx, vy, vw, vh, vcl, vbz = need("disp_x", "disp_offset_y", "disp_w", "disp_h",
                                    "disp_clear", "disp_bezel")
    bz_hw, bz_hh = vw / 2 + vcl + vbz + 0.3, vh / 2 + vcl + vbz + 0.3
    for i, (_v, b, _n) in enumerate(comps):
        if i in back:
            continue
        if b[1] > vx - bz_hw and b[0] < vx + bz_hw and b[3] > vy - bz_hh and b[2] < vy + bz_hh:
            bad.append(f"glyph at ({(b[0] + b[1]) / 2:.1f},{(b[2] + b[3]) / 2:.1f}) under the "
                       f"raised display bezel (x {vx - bz_hw:.1f}..{vx + bz_hw:.1f}) — invisible")
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
                                               ", all 13 labels and 2 brand lines in place, none under the bezel"))

    # ── R12 thin walls, measured (Docker) ───────────────────────────────
    # part thin_check: horizontal slices of top shell (z < 40), bottom
    # shell (40..80) and the edge caps + slider (80+), each eroded/dilated by min_wall/2;
    # whatever survives is material thinner than min_wall. R8 knows the
    # walls we named; this finds the ones we did not.
    stl = export_part("thin_check", THIN_STL)
    try:
        thin = [c for c in components(stl) if c[0] > THIN_MIN_VOL]
    finally:
        stl.unlink(missing_ok=True)
    where = []
    for vol, (x0, x1, y0, y1, z0, z1), _n in thin[:8]:
        part_name = "top" if z0 < 40 else "bottom" if z0 < 80 else "edge caps"
        zz = z0 - (0 if z0 < 40 else 40 if z0 < 80 else 80)
        where.append(f"{part_name} z={zz:.1f} x[{x0:.1f},{x1:.1f}] "
                     f"y[{y0:.1f},{y1:.1f}] ({vol / 0.1:.1f} mm2)")
    check("R12", "thin-walls-measured",
          not thin,
          f"22 slices eroded by {lmin / 2:g}: "
          + (f"{len(thin)} thin region(s): " + "; ".join(where) if thin
             else f"no material under {lmin:g} mm"))

    # ── R13 edge recesses (user 2026-10-07) ─────────────────────────────
    # SD: the user reverted the V3 finger window to the V2.1 16 x 3.5 slit
    # (2026-10-08) — any sd_win_* constant means the window came back.
    sd_window_back = sorted(k for k in env if k.startswith("sd_win"))
    (sd_w, sd_zc, sd_h, k_tip, k_root, nub_proud,
     fork_z0, fork_z1, k_z, slot_w, nub_w, travel) = need(
        "sd_cut_w", "sd_z", "sd_cut_h",
        "pwr_knob_tip_y", "pwr_knob_root_y", "pwr_nub_proud", "pwr_fork_z0",
        "pwr_fork_z1", "pwr_knob_z", "pwr_slot_w", "pwr_nub_w", "pwr_travel")
    knob_depth = k_tip + body_h / 2          # knob tip inside the -Y face
    fork_end = k_root - 0.6
    check("R13", "edge-recesses",
          u_rd >= 2.0 - 1e-9
          and not sd_window_back and sd_w >= 16 and sd_h >= 3.5 - 1e-9
          and nub_proud > 0 and fork_z0 < k_z < fork_z1 and fork_end - k_tip >= 0.5
          and slot_w >= nub_w + travel + 0.3 - 1e-9,
          f"USB-C recess {u_rd:g} (>= 2); SD V2.1 slit {sd_w:g} x {sd_h:g} at Z {sd_zc:g}"
          + (f" — WINDOW IS BACK: {', '.join(sd_window_back)}" if sd_window_back else "")
          + f"; SW16 knob "
          f"{knob_depth:g} inside the face -> slider: fork {fork_end - k_tip:g} over the "
          f"knob, {slot_w:g} slot for a {nub_w:g} nub + {travel:g} travel, nub "
          f"{nub_proud:g} proud")

    # ── R14 proud, rounded caps (user 2026-10-07) ───────────────────────
    face_h, face_r, lr_proud, lr_r, lr_cap_h, lr_cap_w = need(
        "btn_face_h", "btn_face_r", "lr_cap_proud", "lr_cap_r", "lr_cap_h", "lr_cap_w")
    smallest_half = min(aw, sh, mh, ad) / 2
    check("R14", "caps-proud-and-rounded",
          face_h >= 2.0 - 1e-9 and 1.0 <= face_r <= face_h and face_r < smallest_half
          and 2.0 - 1e-9 <= lr_proud <= 3.0 + 1e-9 and 1.0 <= lr_r <= lr_proud
          and lr_r < min(lr_cap_h, lr_cap_w) / 2,
          f"face caps {face_h:g} proud (>= 2), head radius {face_r:g} (narrowest cap "
          f"half-width {smallest_half:g}); L/R caps {lr_proud:g} proud (2..3), radius {lr_r:g}")

    # ── R15 rounded shell (user 2026-10-07, Switch Lite) ────────────────
    corner_r, back_r_, steps = need("corner_r", "back_r", "fillet_steps")
    check("R15", "rounded-shell",
          corner_r >= 10 and back_r_ >= 6 and front_r >= 1.5 and steps >= 8
          and front_fillet_wall >= lmin - 1e-9 and back_r_ > side_wall + 0.2,
          f"corners r{corner_r:g} (>= 10), back fillet r{back_r_:g} (>= 6), front fillet "
          f"r{front_r:g} (>= 1.5, wall at the inner corner {front_fillet_wall:.2f}), "
          f"{steps:g} slices per quarter")

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
