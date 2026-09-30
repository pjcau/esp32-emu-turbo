#!/usr/bin/env python3
"""Draw the SVG figures that replaced the Mermaid diagrams of the docs.

Same kit as the GBA dynarec page (svgfig.py): hand-placed, vector, one
palette, readable in both site themes. Run: python3 website/scripts/gen_doc_svgs.py
Output: website/static/img/diagrams/*.svg

  agents.svg            development/workflow-guide.md  (architecture overview)
  decision-tree.svg     development/workflow-guide.md  (when to use what)
  fix-cycle.svg         development/workflow-guide.md  (the fix cycle)
  agent-skills.svg      tooling/claude-agents.md       (architecture graph)
  test-pipeline.svg     manufacturing/production-test-map.md (pipeline)
  release-timeline.svg  manufacturing/production-test-map.md (version improvements)
"""
import os

from svgfig import C, INK, LINE, MUTED, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "diagrams")

Svg.out_dir = OUT


# ---------------------------------------------------------------------------
def agents():
    s = Svg(1100, 510, "Agent architecture")
    s.box(30, 200, 150, 64, "User", [], "gray", title_size=15)
    s.box(290, 200, 230, 64, "TEAM-LEAD", ["sonnet · orchestrator"], "blue")
    s.box(290, 400, 230, 64, "PLAN-REVIEWER", ["opus · review only"], "amber")
    s.box(30, 400, 150, 64, "SCOUT", ["opus · weekly auto"], "purple")
    s.badge(52, 474, "weekly cron", "purple")

    s.group(620, 40, 330, 450, "worker agents", "gray")
    s.box(650, 80, 270, 72, "PCB-ENGINEER", ["opus · 27 skills"], "orange")
    s.box(650, 238, 270, 72, "SOFTWARE-DEV", ["opus · 6 skills"], "teal")
    s.box(650, 396, 270, 72, "CAD-ENGINEER", ["sonnet · 3 skills"], "green")

    s.arrow([(180, 232), (288, 232)], "complex task", lx=234, ly=214)
    s.arrow([(105, 266), (105, 330), (250, 330), (250, 432), (288, 432)], "review plan", lx=178, ly=330)
    s.arrow([(105, 198), (105, 20), (785, 20), (785, 38)], "direct task: PCB · firmware · enclosure",
            lx=445, ly=20, dashed=True)
    s.arrow([(520, 214), (648, 116)])
    s.arrow([(520, 232), (648, 274)], "coordinates", lx=580, ly=246)
    s.arrow([(520, 250), (648, 432)])

    s.arrow([(785, 154), (785, 236)], "GPIO sync\nconfig.py = board_config.h", lx=785, ly=195, both=True,
            dashed=True, color=C["orange"][0])
    s.arrow([(785, 312), (785, 394)], "docs update\nwebsite/docs/", lx=785, ly=353, both=True, dashed=True,
            color=C["teal"][0])
    s.arrow([(922, 116), (1000, 116), (1000, 432), (922, 432)], "dimensions sync\nboard.py =\nenclosure.scad",
            lx=1000, ly=274, both=True, dashed=True, color=C["green"][0])
    s.save("agents.svg")


def decision_tree():
    rows = [
        ("New PCB from scratch?", "/design-pcb", "Pipeline A"),
        ("Change existing design?", "/generate-pcb", "Pipeline E"),
        ("Fix a bug / DFM issue?", "/fix-pcb", "Pipeline B"),
        ("Verify before release?", "/verify-pcb", "Pipeline C"),
        ("Ship to JLCPCB?", "/release-pcb", "Pipeline D"),
        ("Full hardware audit?", "/hardware-audit", "Pipeline F"),
        ("Firmware change?", "/pcb-to-firmware", None),
        ("3D enclosure?", "/enclosure-design", None),
    ]
    rh, top = 56, 70
    s = Svg(1000, top + len(rows) * rh + 20, "Which command to run")
    s.text(290, 40, "need", 12, 700, MUTED)
    s.text(575, 40, "command", 12, 700, MUTED)
    s.text(850, 40, "pipeline", 12, 700, MUTED)
    mid = top + len(rows) * rh / 2 - 6
    s.box(24, mid - 36, 150, 72, None, [], "blue")
    s.lines(99, mid - 4, ["What do you", "need?"], size=14, color=C["blue"][2], weight=650, gap=20)
    for i, (need, cmd, pipe) in enumerate(rows):
        y = top + i * rh
        cy = y + 22
        s.arrow([(174, mid), (196, mid), (196, cy), (208, cy)], head=True, width=1.4)
        s.box(210, y, 270, 44, None, [], "gray")
        s.text(345, cy + 5, need, 13, 650, C["gray"][2])
        s.arrow([(480, cy), (498, cy)])
        w = s.chip_w(cmd, 12.5) + 20
        s.add(f'<rect x="500" y="{y + 4}" width="{w}" height="36" rx="18" fill="{C["orange"][1]}" '
              f'stroke="{C["orange"][0]}" stroke-width="1.6" filter="url(#sh)"/>')
        s.text(500 + w / 2, cy + 5, cmd, 12.5, 600, C["orange"][2], font="'JetBrains Mono', 'Fira Code', Menlo, "
               "Consolas, monospace")
        if pipe:
            s.arrow([(500 + w, cy), (778, cy)])
            s.box(780, y + 4, 140, 36, None, [], "teal")
            s.text(850, cy + 5, pipe, 13, 650, C["teal"][2])
    s.save("decision-tree.svg")


def fix_cycle():
    s = Svg(1000, 250, "The fix cycle")
    steps = [("/verify", "find failures", "blue"), ("/dfm-fix", "edit source", "orange"),
             ("/generate", "regen PCB", "teal"), ("/verify", "confirm fix", "blue"),
             ("/dfm-test", "add guard", "purple"), ("/release-prep", "", "green")]
    w, gap, x0, y = 140, 26, 20, 50
    for i, (cmd, sub, col) in enumerate(steps):
        x = x0 + i * (w + gap)
        if sub:
            s.box(x, y, w, 70, cmd, [sub], col, title_size=14)
        else:
            s.box(x, y, w, 70, None, [], col)
            s.text(x + w / 2, y + 40, cmd, 14, 650, C[col][2])
        if i < len(steps) - 1:
            lab = "all pass" if i == 3 else None
            s.arrow([(x + w, y + 35), (x + w + gap - 2, y + 35)], lab, lx=x + w + gap / 2, ly=y - 12)
    xb = x0 + 1 * (w + gap) + w / 2
    xd = x0 + 3 * (w + gap) + w / 2
    s.arrow([(xd, 122), (xd, 180), (xb, 180), (xb, 124)], "still failing", lx=(xb + xd) / 2, ly=180,
            color=C["red"][0], dashed=True)
    s.text(500, 225, "loop until every gate passes, then pin the fix with a regression test", 12, color=MUTED)
    s.save("fix-cycle.svg")


def agent_skills():
    s = Svg(1000, 900, "Agents and their skills")
    # row A: scout -> team-lead -- cross-agent skills
    s.group(20, 20, 270, 100, "SCOUT · opus · weekly Action", "purple")
    s.text(34, 62, "Pattern Discovery · 1", 11.5, 600, C["purple"][2], anchor="start")
    s.chips(34, 76, 240, ["/scout"], "purple")
    s.box(380, 34, 240, 72, "TEAM-LEAD", ["sonnet · orchestrator"], "blue")
    s.group(710, 20, 270, 100, "Cross-Agent · 2", "blue")
    s.chips(724, 50, 250, ["/user-feedback", "/memory-maintenance"], "blue")
    s.arrow([(290, 70), (378, 70)], "integrates\npatterns", lx=334, ly=70, dashed=True)
    s.arrow([(620, 70), (708, 70)], head=False)

    # row B: the three worker agents
    s.box(170, 170, 200, 64, "PCB-ENGINEER", ["opus · 27 skills"], "orange")
    s.box(570, 170, 160, 64, "SOFTWARE-DEV", ["opus · 6 skills"], "teal")
    s.box(810, 170, 160, 64, "CAD-ENGINEER", ["sonnet · 3 skills"], "green")
    s.arrow([(450, 106), (270, 168)])
    s.arrow([(500, 106), (650, 168)], "coordinates", lx=560, ly=134)
    s.arrow([(550, 106), (890, 168)])
    s.arrow([(372, 202), (568, 202)], "GPIO sync\nconfig.py = board_config.h", lx=470, ly=202, both=True,
            dashed=True, color=C["orange"][0])
    s.arrow([(732, 202), (808, 202)], "docs +\nrenders", lx=770, ly=202, both=True, dashed=True,
            color=C["teal"][0])
    s.arrow([(270, 236), (270, 262), (890, 262), (890, 236)],
            "dimensions sync · board.py 160×75 mm = enclosure.scad", lx=580, ly=262, both=True, dashed=True,
            color=C["green"][0])

    # row C: skill groups under their owner
    def skill_group(x, y, w, label, items, color):
        h = Svg(0, 0, "").chips(x + 14, y + 36, w - 28, items, color) + 50  # measure only
        s.group(x, y, w, h, f"{label} · {len(items)}", color)
        s.chips(x + 14, y + 36, w - 28, items, color)
        return h

    y0 = 292
    h1 = skill_group(20, y0, 250, "Pipeline", ["/generate", "/release", "/release-prep", "/full-release", "/render",
                                              "/pcba-render", "/check"], "orange")
    h2 = skill_group(280, y0, 270, "Verification", ["/verify", "/dfm-test", "/drc-native", "/drc-audit",
                                                   "/pcb-optimize", "/pcb-review", "/datasheet-verify",
                                                   "/design-intent", "/pad-analysis", "/jlcpcb-alignment",
                                                   "/jlcpcb-validate"], "orange")
    y1 = y0 + max(h1, h2) + 14
    h3 = skill_group(20, y1, 250, "Fix and Debug", ["/dfm-fix", "/fix-rotation", "/jlcpcb-check", "/jlcpcb-parts"],
                     "orange")
    h4 = skill_group(280, y1, 270, "MCP Design", ["/pcb-schematic", "/pcb-components", "/pcb-routing",
                                                 "/pcb-library", "/pcb-board"], "orange")
    h5 = skill_group(570, y0, 200, "Firmware and Web", ["/firmware-build", "/firmware-sync", "/website-dev", "/doc",
                                                       "/pcb-to-firmware", "/hardware-test-gen"], "teal")
    h6 = skill_group(790, y0, 190, "Enclosure", ["/enclosure-design", "/enclosure-render", "/enclosure-export"],
                     "green")
    bottom = max(y1 + max(h3, h4), y0 + h5, y0 + h6)

    # row D: the main design flow across the skills
    fy = bottom + 40
    s.group(20, fy, 960, 150, "main design flow", "gray")
    flow = ["/pcb-schematic", "/pcb-board", "/pcb-components", "/pcb-routing", "/generate", "/verify", "/release"]
    labels = ["nets", "outline", "placed", "routed", "PCB ready", "must pass"]
    widths = [s.chip_w(f) for f in flow]
    gap = (960 - 28 - sum(widths)) / (len(flow) - 1)
    x, cy = 34, fy + 56
    xs = []
    for i, f in enumerate(flow):
        col = "orange" if i < 4 else ("teal" if i == 4 else ("blue" if i == 5 else "green"))
        s.chip(x, cy, f, col)
        xs.append(x)
        if i < len(flow) - 1:
            s.arrow([(x + widths[i] + 2, cy + 13), (x + widths[i] + gap - 3, cy + 13)], width=2.2)
            s.text(x + widths[i] + gap / 2, cy - 8, labels[i], 11, color=MUTED)
        x += widths[i] + gap
    gx = xs[4] + widths[4] / 2
    fx = gx - s.chip_w("/dfm-fix") / 2
    s.chip(fx, cy + 66, "/dfm-fix", "red")
    s.arrow([(gx, cy + 64), (gx, cy + 29)], "fixes, then regen", lx=gx + 70, ly=cy + 47, color=C["red"][0])
    s.h = fy + 170
    s.save("agent-skills.svg")


def test_pipeline():
    stages = [
        ("1 · Source sync", 11, "copper vs the drawing", "red"),
        ("2 · Copper integrity", 14, "opens, shorts, orphan copper", "red"),
        ("3 · Fabrication", 14, "DRC, DFM, drill, stackup", "red"),
        ("4 · Assembly", 13, "rotation, polarity, BOM, stencil", "red"),
        ("5 · Electrical", 22, "ERC, sim, power, ESD, boot", "red"),
        ("6 · Signal integrity / EMC", 8, "impedance, return path, coupling", "amber"),
        ("7 · Release integrity", 11, "ordered == verified", "purple"),
    ]
    bh, gap, x, w = 58, 20, 170, 400
    y = 92
    s = Svg(1000, 92 + len(stages) * (bh + gap) + 100, "Production test pipeline")
    s.add(f'<rect x="{x + 40}" y="20" width="{w - 80}" height="50" rx="25" fill="{C["gray"][1]}" '
          f'stroke="{C["gray"][0]}" stroke-width="1.6" filter="url(#sh)"/>')
    s.text(x + w / 2, 41, "make generate", 14, 650, C["gray"][2])
    s.text(x + w / 2, 59, "board + schematic from Python", 11.5, color=MUTED, italic=True)
    s.arrow([(x + w / 2, 70), (x + w / 2, 90)])
    ys = []
    for i, (t, n, sub, col) in enumerate(stages):
        s.box(x, y, w, bh, t, [sub], col, title_size=14, row_size=12)
        s.badge(x + w - 78, y + 8, f"{n} gates", col)
        ys.append(y)
        s.arrow([(x + w / 2, y + bh), (x + w / 2, y + bh + gap - 2)])
        y += bh + gap
    s.add(f'<rect x="{x + 40}" y="{y}" width="{w - 80}" height="50" rx="25" fill="{C["gray"][1]}" '
          f'stroke="{C["gray"][0]}" stroke-width="1.6" filter="url(#sh)"/>')
    s.text(x + w / 2, y + 21, "JLCPCB order", 14, 650, C["gray"][2])
    s.text(x + w / 2, y + 39, "gerbers + BOM + CPL", 11.5, color=MUTED, italic=True)

    # meta stage, auditing the whole column
    mx, mw = 680, 280
    my = ys[2] + 10
    s.box(mx, my, mw, 110, "8 · Meta / blind-spot", ["can the network", "still notice?"], "purple", title_size=14)
    s.badge(mx + mw / 2 - 34, my + 118, "6 gates", "purple")
    s.arrow([(mx + 60, my - 2), (mx + 60, ys[0] + bh / 2), (x + w + 2, ys[0] + bh / 2)], "audits every stage",
            lx=mx + 60, ly=(my + ys[0] + bh / 2) / 2, dashed=True, color=C["purple"][0])
    s.arrow([(mx + 60, my + 112), (mx + 60, ys[6] + bh / 2), (x + w + 2, ys[6] + bh / 2)], dashed=True,
            color=C["purple"][0])
    for yy in ys[1:6]:
        s.add(f'<path d="M{mx - 1},{yy + bh / 2} L{x + w + 6},{yy + bh / 2}" stroke="{C["purple"][0]}" '
              'stroke-width="1" stroke-dasharray="2 5" opacity="0.5"/>')

    # legend
    lx, ly = 30, 110
    s.text(lx, ly, "severity", 12, 700, MUTED, anchor="start")
    for i, (name, col) in enumerate([("dead-board", "red"), ("degraded", "amber"), ("blind-spot", "purple"),
                                     ("edges", "gray")]):
        yy = ly + 24 + i * 26
        s.add(f'<rect x="{lx}" y="{yy - 11}" width="14" height="14" rx="4" fill="{C[col][1]}" '
              f'stroke="{C[col][0]}" stroke-width="1.6"/>')
        s.text(lx + 22, yy, name, 12, color=INK, anchor="start")
    s.save("test-pipeline.svg")


def release_timeline():
    sections = [
        ("v2–v3 · first packages", "blue", [
            ("v2.9", ["NPTH positioning holes fixed"]),
            ("v3.2", ["first full JLCPCB package"]),
            ("v3.4", ["Layer-1 and 2 hardware audit over 10 rounds"]),
            ("v3.5", ["pin-1 markers plus 10 DFM checks"]),
            ("v3.6", ["R13 copper-clearance sweep and gate"]),
            ("v3.7", ["JLCDFM cleanup"]),
        ]),
        ("v4 · the gate network", "orange", [
            ("v4.0", ["reverse-polarity protection", "thermal vias", "5 verification scripts"]),
            ("v4.1", ["community DFM and DFA gap analysis"]),
            ("v4.2", ["USB-C footprint fixes"]),
            ("v4.3", ["polarity fixes", "PAM8403 plus 5V bridge"]),
            ("v4.3.1", ["systemic CPL rotation incident", "first-article-check protocol born"]),
            ("v4.4.0", ["four new blocking gates", "10 live bugs fixed", "order-manifest SHAs"]),
            ("v4.5.0", ["diagnostic LED tree for photo-diagnosable rails"]),
            ("v4.5.1", ["R31 respin", "Q1 RPP orientation", "BTN_R off card-detect pad"]),
        ]),
        ("next", "gray", [
            ("v3 silk", ["silkscreen pass"]),
            ("EMC", ["crosstalk", "plane split", "length match", "via discontinuity"]),
        ]),
    ]
    rh, sh = 34, 52
    n = sum(len(it) for _, _, it in sections)
    s = Svg(1000, 70 + n * rh + len(sections) * sh + 30, "Quality improvements per release")
    s.text(500, 38, "Quality improvements per release", 16, 700, INK)
    spine = 150
    y = 70
    top = y
    for title, col, items in sections:
        stroke, bg, tx = C[col]
        s.add(f'<rect x="24" y="{y + 8}" width="952" height="32" rx="10" fill="{bg}" stroke="{stroke}" '
              'stroke-width="1.2"/>')
        s.text(40, y + 29, title, 13, 700, stroke, anchor="start")
        y += sh
        for ver, parts in items:
            cy = y + rh / 2
            bw = 12 + 7.4 * len(ver)
            s.add(f'<rect x="{spine - 20 - bw}" y="{cy - 11}" width="{bw}" height="22" rx="11" fill="{stroke}"/>')
            s.text(spine - 20 - bw / 2, cy + 4.5, ver, 12, 700, "#ffffff")
            s.add(f'<circle cx="{spine}" cy="{cy}" r="6" fill="#ffffff" stroke="{stroke}" stroke-width="2.4"/>')
            s.text(spine + 22, cy + 4.5, "  ·  ".join(parts), 13, color=INK, anchor="start")
            y += rh
    s.add(f'<path d="M{spine},{top + sh} L{spine},{y - rh / 2}" stroke="{LINE}" stroke-width="2"/>')
    # the spine must sit under the dots: move it to the front of the drawing
    s.parts.insert(1, s.parts.pop())
    s.save("release-timeline.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (agents, decision_tree, fix_cycle, agent_skills, test_pipeline, release_timeline):
        fn()
    print("written:", sorted(os.listdir(OUT)))
