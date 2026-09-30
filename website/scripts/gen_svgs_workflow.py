#!/usr/bin/env python3
"""Draw the SVG figures of the workflow / tooling pages (were ASCII art).

Same kit as the other doc figures (svgfig.py): hand-placed, vector, one
palette, readable in both site themes. Run: python3 website/scripts/gen_svgs_workflow.py
Output: website/static/img/diagrams/wf-*.svg

  wf-new-pcb.svg          development/workflow-guide.md  (scenario 1)
  wf-dfm-fix.svg          development/workflow-guide.md  (scenario 2)
  wf-pre-release.svg      development/workflow-guide.md  (scenario 3)
  wf-release.svg          development/workflow-guide.md  (scenario 4)
  wf-hardware-audit.svg   development/workflow-guide.md  (scenario 5)
  wf-gpio-change.svg      development/workflow-guide.md  (scenario 6)
  wf-enclosure.svg        development/workflow-guide.md  (scenario 7)
  wf-source-of-truth.svg  development/workflow-guide.md  (source of truth hierarchy)
  wf-agent-tree.svg       tooling/claude-agents.md       (architecture overview)
  wf-cross-agent.svg      tooling/claude-agents.md       (cross-agent dependencies)
"""
import os

from svgfig import C, INK, MUTED, MONO, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "diagrams")

Svg.out_dir = OUT

STEP_H = 40      # command box height
SUB_H = 30       # sub-item row pitch
GAP = 34         # vertical gap (arrow) between steps
X0 = 40          # left edge of the command column


def cmd_box(s, x, y, w, text, color, h=STEP_H, size=13.5):
    """A command / file as a rounded box with a mono label."""
    stroke, bg, tx = C[color]
    s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="{bg}" stroke="{stroke}" '
          f'stroke-width="1.6" filter="url(#sh)"/>')
    s.text(x + w / 2, y + h / 2 + size * 0.36, text, size, 650, tx, font=MONO)


def num_badge(s, x, cy, n, color):
    s.add(f'<circle cx="{x}" cy="{cy}" r="12" fill="{C[color][0]}"/>')
    s.text(x, cy + 4.5, str(n), 12, 700, "#ffffff")


def text_w(t, size=13.5):
    return len(t) * size * 0.6 + 34


def pipeline(name, title, steps, numbered=False, w=1000, top=30, pre=None):
    """Vertical pipeline: each step is a command box + muted description, with
    optional indented sub-items (chip + description).

    step = dict(cmd, desc, color, subs=[(chip, desc)], decision=(question, yes_chip, loop_to_index))
    """
    xs = X0 + (34 if numbered else 0)
    cw = max(220, max(text_w(st["cmd"]) for st in steps if "cmd" in st))
    sub_x = xs + 44
    sub_w = max([s_ for st in steps for s_ in [Svg(0, 0, "").chip_w(c) for c, _ in st.get("subs", [])]] or [0])
    desc_x = max(xs + cw + 28, sub_x + sub_w + 28)

    # layout pass
    y = top
    pos = []
    for st in steps:
        h = STEP_H
        subs_h = len(st.get("subs", [])) * SUB_H + (10 if st.get("subs") else 0)
        dec_h = 40 + GAP if st.get("decision") else 0
        pos.append((y, subs_h))
        y += h + subs_h + dec_h + GAP
    H = y - GAP + 30
    texts = [st.get(k, "") for st in steps for k in ("desc", "desc2")] + [d for st in steps for _, d in st.get("subs", [])]
    need = desc_x + max(len(t) for t in texts) * 13 * 0.56 + 40
    if any(st.get("decision") for st in steps):
        need = max(need, desc_x + 420)
    w = round(min(w, max(640, need)))
    s = Svg(w, H, title)
    cx = xs + cw / 2
    if pre:
        pre(s, cx)

    for i, st in enumerate(steps):
        y, subs_h = pos[i]
        col = st.get("color", "blue")
        cmd_box(s, xs, y, cw, st["cmd"], col)
        if numbered:
            num_badge(s, X0 + 8, y + STEP_H / 2, i + 1, col)
        if st.get("desc"):
            s.text(desc_x, y + STEP_H / 2 + 5, st["desc"], 13, color=MUTED, anchor="start")
        if st.get("desc2"):
            s.text(desc_x, y + STEP_H / 2 + 23, st["desc2"], 12.5, color=MUTED, anchor="start")
        subs = st.get("subs", [])
        if subs:
            last = y + STEP_H + 10 + (len(subs) - 1) * SUB_H + 13
            s.add(f'<path d="M{xs + 22},{y + STEP_H} L{xs + 22},{last}" stroke="{C[col][0]}" stroke-width="1.4" '
                  'fill="none"/>')
            for j, (chip, d) in enumerate(subs):
                yy = y + STEP_H + 10 + j * SUB_H
                s.add(f'<path d="M{xs + 22},{yy + 13} L{sub_x - 2},{yy + 13}" stroke="{C[col][0]}" '
                      'stroke-width="1.4" fill="none"/>')
                s.chip(sub_x, yy, chip, col)
                if d:
                    s.text(desc_x, yy + 17.5, d, 12.5, color=MUTED, anchor="start")
        bottom = y + STEP_H + subs_h
        dec = st.get("decision")
        if dec:
            q, yes_chip, loop_to = dec
            dy = bottom + GAP
            s.arrow([(cx, bottom + 2), (cx, dy - 2)])
            qw = text_w(q, 13)
            s.box(cx - qw / 2, dy, qw, 40, None, [], "amber")
            s.text(cx, dy + 25, q, 13, 650, C["amber"][2])
            yx = cx + qw / 2 + 90
            s.arrow([(cx + qw / 2, dy + 20), (yx - 3, dy + 20)], "yes", lx=cx + qw / 2 + 44, ly=dy + 20)
            yw = s.chip_w(yes_chip, 12.5) + 10
            cmd_box(s, yx, dy + 4, yw, yes_chip, "red", h=32, size=12.5)
            ty = pos[loop_to][0] - 14   # run above the target box, clear of its description
            tx = xs + cw - 36
            rx = max(yx + yw + 40, desc_x + 380)
            s.arrow([(yx + yw, dy + 20), (rx, dy + 20), (rx, ty), (tx, ty), (tx, ty + 12)], "loop", lx=rx,
                    ly=(dy + ty) / 2, dashed=True, color=C["red"][0])
            bottom = dy + 40
        if i < len(steps) - 1:
            lab = "no" if dec else None
            s.arrow([(cx, bottom + 2), (cx, pos[i + 1][0] - 2)], lab, lx=cx + 18, ly=(bottom + pos[i + 1][0]) / 2)
    s.save(name)


# ---------------------------------------------------------------------------
def new_pcb():
    pipeline("wf-new-pcb.svg", "New PCB from scratch", [
        dict(cmd="/bootstrap-new-pcb", desc="scaffold project structure", color="gray"),
        dict(cmd="/design-pcb", desc="composes 4 skills:", color="orange", subs=[
            ("/pcb-schematic", "define GPIO_NETS, regenerate .kicad_sch"),
            ("/pcb-board", "set outline, layers, mounting holes"),
            ("/pcb-components", "place footprints in board.py"),
            ("/pcb-routing", "route traces + vias in routing.py")]),
        dict(cmd="/generate-pcb", desc="composes 2 skills:", color="teal", subs=[
            ("/generate", "Python -> .kicad_pcb + BOM + CPL"),
            ("/check", "DRC + 3D + gerbers + DFM")]),
        dict(cmd="/verify-pcb", desc="composes 8 verification skills", color="blue",
             decision=("failures?", "/fix-pcb", 2)),
        dict(cmd="/pcb-to-firmware", desc="sync board_config.h", color="purple"),
        dict(cmd="/release-pcb", desc="gerbers + renders + git tag", color="green"),
    ])


def dfm_fix():
    # two entry points feed /dfm-fix: draw them above the generic pipeline
    steps = [
        dict(cmd="/dfm-fix <report>", desc="read report, categorize, fix source files", color="orange",
             desc2="(board.py / routing.py / footprints.py)", subs=[
            ("/fix-rotation", "if CPL rotation wrong"),
            ("/jlcpcb-check", "if 3D alignment wrong"),
            ("/jlcpcb-parts", "if BOM parts out of stock")]),
        dict(cmd="/generate", desc="regenerate .kicad_pcb", color="teal"),
        dict(cmd="/verify", desc="confirm all 124 DFM tests pass", color="blue"),
        dict(cmd="/dfm-test", desc="add regression guard test", color="purple",
             decision=("still failing?", "repeat /dfm-fix", 0)),
        dict(cmd="/release-prep", desc="sync release_jlcpcb/ (no git commit)", color="green"),
    ]
    def entry(e, cx):
        e.box(40, 26, 250, 44, None, [], "red")
        e.text(165, 53, "JLCPCB DFM report (PDF)", 13, 650, C["red"][2])
        e.text(320, 53, "or", 13, 600, MUTED)
        cmd_box(e, 350, 28, 110, "/verify", "blue")
        e.arrow([(460, 48), (500, 48)])
        e.text(508, 53, "failures found", 13, color=MUTED, anchor="start")
        e.arrow([(165, 72), (165, 96), (cx, 96), (cx, 130)])
        e.arrow([(405, 70), (405, 96), (cx, 96)], head=False)

    pipeline("wf-dfm-fix.svg", "Fix a DFM issue", steps, top=132, pre=entry)


def pre_release():
    pipeline("wf-pre-release.svg", "Pre-release verification", [
        dict(cmd="/verify-pcb", desc="composes ALL verification skills:", color="blue", subs=[
            ("/verify", "124 DFM + 9 DFA + 24 JLCPCB"),
            ("/drc-native", "KiCad native DRC + baseline delta"),
            ("/drc-audit", "full electrical classification"),
            ("/pad-analysis", "pad spacing table"),
            ("/jlcpcb-validate", "24 JLCPCB manufacturing rules"),
            ("/datasheet-verify", "267 pin-to-net checks vs datasheets"),
            ("/design-intent", "357 cross-source consistency checks"),
            ("/pcb-review", "8-domain 100-point scored review")]),
    ])


def release():
    pipeline("wf-release.svg", "Release to JLCPCB", [
        dict(cmd="/release-pcb", desc="composes /full-release:", color="green", subs=[
            ("/generate", "1 · regenerate from Python"),
            ("/verify", "2 · 124 DFM + 9 DFA + 24 JLCPCB"),
            ("/drc-native", "3 · KiCad DRC"),
            ("/render", "4 · SVG layers + animation"),
            ("/pcba-render", "5 · 13 raytraced 3D PCBA views"),
            ("Export gerbers", "6 · kicad-cli + Docker zone fill"),
            ("BOM + CPL", "7 · JLCPCB formatting"),
            ("Sync", "8 · release_jlcpcb/ updated"),
            ("Commit + tag", "9 · git commit + version tag + push")]),
    ])


def hardware_audit():
    gates = [("verify_trace_through_pad", "fab shorts"), ("verify_trace_crossings", "same-layer crossings"),
             ("verify_copper_clearance", "Shapely polygon gaps"), ("verify_net_connectivity", "per-net copper graph"),
             ("verify_dfm_v2", "124 DFM tests"), ("verify_dfa", "9 assembly tests"),
             ("validate_jlcpcb", "24 JLCPCB rules"), ("verify_polarity", "48 pin-to-net"),
             ("verify_datasheet_nets", "267 checks"), ("verify_datasheet", "29 physical"),
             ("verify_design_intent", "357 cross-source"), ("verify_schematic_pcb_sync", "R4 guard"),
             ("verify_strapping_pins", "12 ESP32 boot"), ("verify_decoupling_adequacy", "23 cap checks"),
             ("verify_power_sequence", "29 power chain"), ("verify_power_paths", "10+11 copper paths"),
             ("erc_check + KiCad DRC", "0 real shorts")]
    steps = [("Power chain", "USB-C -> IP5306 -> Q2 switch -> SY8089 -> ESP32"),
             ("ESP32 boot", "strapping pins, PSRAM mode"),
             ("Display", "ILI9488 8080 parallel, FPC"),
             ("Audio", "I2S PDM -> PAM8403 -> speaker"),
             ("SD card", "SPI 1-bit, TF-01A"),
             ("Buttons", "12 + menu combo D1; SW16 belongs to Step 1 since the respin"),
             ("USB", "native FS, CC pull-downs, ESD TVS"),
             ("Emulator performance", "PSRAM, DMA, LCD")]
    rows1 = (len(gates) + 1) // 2
    g1h = 96 + rows1 * 32 + 30
    g2h = 60 + len(steps) * 34 + 10
    H = 30 + 50 + 30 + g1h + 40 + g2h + 40 + 50 + 30
    s = Svg(1000, H, "Hardware audit")
    cmd_box(s, 400, 24, 200, "/hardware-audit", "blue")
    y = 24 + STEP_H + 30
    s.arrow([(500, 24 + STEP_H + 2), (500, y - 2)])
    s.group(24, y, 952, g1h, "Layer 1 · automated gates (22 scripts, 1200+ checks)", "red",
            badge="HARD BLOCK")
    s.text(40, y + 48, "HARD BLOCK if ANY fail — fix before Layer 2", 12.5, 600, C["red"][2], anchor="start")
    for i, (g, d) in enumerate(gates):
        col, row = i // rows1, i % rows1
        gx = 44 + col * 470
        gy = y + 66 + row * 32
        w = s.chip(gx, gy, g, "red")
        s.text(gx + 262, gy + 17.5, d, 12.5, color=MUTED, anchor="start")
        del w
    s.text(44, y + 66 + rows1 * 32 + 18, "... and more", 12.5, color=MUTED, anchor="start", italic=True)
    y2 = y + g1h + 40
    s.arrow([(500, y + g1h + 2), (500, y2 - 2)], "all pass", lx=560, ly=y + g1h + 20)
    s.group(24, y2, 952, g2h, "Layer 2 · domain-by-domain prose review (8 domains)", "purple")
    for i, (t, d) in enumerate(steps):
        yy = y2 + 50 + i * 34
        num_badge(s, 56, yy + 13, i + 1, "purple")
        s.text(80, yy + 18, t, 13, 650, C["purple"][2], anchor="start")
        s.text(260, yy + 18, d, 12.5, color=MUTED, anchor="start")
    y3 = y2 + g2h + 40
    s.arrow([(500, y2 + g2h + 2), (500, y3 - 2)])
    s.box(250, y3, 500, 50, None, [], "green")
    s.text(500, y3 + 22, "hardware-audit-bugs.md", 13.5, 650, C["green"][2], font=MONO)
    s.text(500, y3 + 40, "CRIT / HIGH / MED / LOW findings", 12, color=MUTED)
    s.save("wf-hardware-audit.svg")


def gpio_change():
    pipeline("wf-gpio-change.svg", "GPIO / component change", [
        dict(cmd="Edit scripts/generate_schematics/config.py", desc="master GPIO map", color="gray"),
        dict(cmd="/pcb-to-firmware", desc="auto-sync:", color="purple", subs=[
            ("board_config.h", "updated"), ("datasheet_specs.py", "updated"),
            ("routing.py", "button assignments updated"), ("website/docs/", "updated")]),
        dict(cmd="/generate-pcb", desc="regen PCB + quick verify", color="teal"),
        dict(cmd="/verify-pcb", desc="full sweep", color="blue"),
        dict(cmd="/firmware-sync", desc="confirm GPIO match", color="green"),
    ], numbered=True)


def enclosure():
    pipeline("wf-enclosure.svg", "Enclosure update", [
        dict(cmd="/enclosure-design", desc="update OpenSCAD parameters (pcb_w, pcb_h, cutouts, screw holes)",
             color="green"),
        dict(cmd="/enclosure-render", desc="PNG views via Docker", color="teal"),
        dict(cmd="/enclosure-export", desc="STL files for 3D printing", color="blue"),
    ], numbered=True)


def source_of_truth():
    rows = [("config.py", "MASTER: GPIO assignments", "blue"),
            ("board_config.h", "firmware (must match config.py)", "teal"),
            ("datasheet_specs.py", "pin-to-net specs (37 components)", "purple"),
            ("routing.py", "PCB traces + vias", "orange")]
    s = Svg(1000, 30 + 4 * (STEP_H + GAP) + 110, "Source of truth hierarchy")
    y = 30
    for i, (f, d, c) in enumerate(rows):
        cmd_box(s, 300, y, 220, f, c)
        s.text(550, y + 25, d, 13, 650 if i == 0 else 400, INK if i == 0 else MUTED, anchor="start")
        s.arrow([(410, y + STEP_H + 2), (410, y + STEP_H + GAP - 2)])
        y += STEP_H + GAP
    s.group(260, y, 600, 100, "GENERATED · never edit directly!", "red")
    cmd_box(s, 290, y + 42, 180, ".kicad_pcb", "red")
    cmd_box(s, 500, y + 42, 180, ".kicad_sch", "red")
    s.text(130, 40 + 2 * (STEP_H + GAP), "changes flow", 12.5, 650, MUTED)
    s.text(130, 58 + 2 * (STEP_H + GAP), "DOWN only", 12.5, 650, MUTED)
    s.arrow([(130, 50), (130, 30 + 4 * (STEP_H + GAP) + 60)], width=3)
    s.save("wf-source-of-truth.svg")


def agent_tree():
    s = Svg(1000, 364, "Agent definitions")
    s.box(360, 24, 280, 64, "team-lead", ["Sonnet · orchestrator, task coordination"], "blue")
    kids = [("pcb-engineer", "Opus · 27 skills", "PCB design + manufacturing", "orange"),
            ("software-dev", "Opus · 6 skills", "firmware + website + docs", "teal"),
            ("cad-engineer", "Sonnet · 3 skills", "OpenSCAD enclosure", "green")]
    for i, (t, a, b, c) in enumerate(kids):
        x = 40 + i * 320
        s.box(x, 140, 280, 76, t, [a, b], c)
        s.arrow([(500, 90), (500, 112), (x + 140, 112), (x + 140, 138)])
    s.group(24, 238, 952, 106, "stand-alone", "gray")
    s.box(44, 270, 440, 60, "plan-reviewer", ["Opus · review only, no skills — vets plans before implementation"],
          "amber", row_size=11.5)
    s.box(516, 270, 440, 60, "scout", ["Opus · 1 skill, GitHub pattern discovery (weekly via GitHub Action)"],
          "purple", row_size=11.5)
    s.save("wf-agent-tree.svg")


def cross_agent():
    s = Svg(1000, 300, "Cross-agent dependencies")
    s.box(40, 40, 220, 64, "PCB", ["pcb-engineer"], "orange")
    s.box(740, 40, 220, 64, "SW", ["software-dev"], "teal")
    s.box(390, 210, 220, 64, "CAD", ["cad-engineer"], "green")
    s.arrow([(262, 72), (738, 72)], "config.py = board_config.h\n(GPIO pins sync)", lx=500, ly=72, both=True,
            dashed=True, color=C["orange"][0])
    s.arrow([(150, 106), (150, 242), (388, 242)], "board.py 160×75mm = enclosure.scad\n(dimensions sync)", lx=210,
            ly=176, both=True, dashed=True, color=C["green"][0])
    s.arrow([(850, 106), (850, 242), (612, 242)], "website/docs/\n(renders + documentation)", lx=850, ly=176,
            both=True, dashed=True, color=C["teal"][0])
    s.save("wf-cross-agent.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (new_pcb, dfm_fix, pre_release, release, hardware_audit, gpio_change, enclosure, source_of_truth,
               agent_tree, cross_agent):
        fn()
    print("written:", sorted(f for f in os.listdir(OUT) if f.startswith("wf-")))
