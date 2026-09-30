#!/usr/bin/env python3
"""Draw the SVG figures of docs/software/m68k-dynarec.md.

Same kit as the GBA dynarec page (svgfig.py). Run:
python3 website/scripts/gen_svgs_m68k.py
Output: website/static/img/m68k-dynarec/*.svg
"""
import os

from svgfig import C, INK, MUTED, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "m68k-dynarec")

Svg.out_dir = OUT


def interp_vs_jit():
    s = Svg(1000, 350, "Musashi interpreter vs m68kjit")
    s.group(20, 20, 470, 310, "Musashi interpreter  ·  m68k_execute()", "gray")
    s.text(255, 60, "fetch + decode + dispatch on EVERY instruction", 12, color=MUTED)
    s.box(60, 90, 170, 64, "fetch", ["opcode word at PC"], "gray")
    s.box(280, 90, 170, 64, "dispatch", ["handler table[op]"], "gray")
    s.box(170, 220, 170, 64, "handler", ["C code per opcode"], "gray")
    s.arrow([(230, 122), (278, 122)])
    s.arrow([(365, 156), (300, 218)])
    s.arrow([(200, 218), (140, 158)])
    s.group(510, 20, 470, 310, "m68kjit  ·  on top of the same Musashi", "green")
    s.text(745, 60, "fetch and decode ONCE per block, then Xtensa code", 12, color=MUTED)
    s.box(540, 86, 410, 60, "first time a block is reached", ["length-decode it, emit Xtensa code into the cache"],
          "orange")
    s.box(540, 176, 195, 70, "native", ["known forms: Xtensa code", "on Musashi's registers"], "green",
          title_size=13.5)
    s.box(755, 176, 195, 70, "handler call", ["anything else: Musashi's", "own handler, exact"], "teal",
          title_size=13.5)
    s.arrow([(700, 148), (640, 174)])
    s.arrow([(790, 148), (850, 174)])
    s.text(745, 280, "84 % of random valid 68000 code runs native", 12.5, 650, C["green"][0])
    s.text(745, 302, "every instruction works from day one: the rest is the interpreter", 12, color=MUTED)
    s.save("interp-vs-jit.svg")


def stack():
    s = Svg(1000, 690, "The 68000 dynarec stack")
    rows = [
        ("arcade game", "gray", [("Neo Geo · CPS1 · 68000 MAME boards", "68000 code in the ROM set", 700)]),
        ("mame-go app", "blue", [("launcher", "pick a game · states", 300),
                                 ("MAME 0.37b5 drivers", "video · Z80 · YM2610 / YM2151 · OKI", 390)]),
        ("Musashi 3.1", "teal", [("interpreter", "handlers · flags · cycles · IRQs", 330),
                                 ("glue_musashi31.c", "fills m68kjit_host_t, own m68k_execute()", 360)]),
        ("m68kjit", "orange", [("translator", "length decoder · blocks · native forms", 380),
                               ("block cache", "4096 blocks · 1 MB code · chaining", 310)]),
        ("xjit core", "purple", [("shared with the GBA", "encoders · labels · PSRAM mapped for exec · cache sync", 700)]),
        ("ESP32-S3 N16R8", "gray", [("2 × Xtensa LX7 240 MHz", "32 KB I-cache shared · 64 KB D-cache", 340),
                                    ("memory", "internal RAM tight · 8 MB PSRAM · 16 MB flash", 350)]),
    ]
    y = 24
    for i, (label, col, items) in enumerate(rows):
        stroke, bg, _ = C[col]
        h = 88
        s.add(f'<rect x="24" y="{y}" width="952" height="{h}" rx="14" fill="{bg}" stroke="{stroke}" stroke-width="1.4"/>')
        s.add(f'<rect x="24" y="{y}" width="170" height="{h}" rx="14" fill="{stroke}"/>')
        s.add(f'<rect x="180" y="{y}" width="14" height="{h}" fill="{stroke}"/>')
        s.text(109, y + h / 2 + 5, label, 15, 700, "#ffffff")
        x = 214
        for title, sub, w in items:
            s.box(x, y + 12, w, h - 24, title, [sub] if sub else [], col, title_size=13.5, row_size=12)
            x += w + 18
        if col == "orange":
            s.badge(900, y - 10, "NEW")
        if i < len(rows) - 1:
            s.arrow([(500, y + h + 1), (500, y + h + 17)])
        y += h + 18
    s.save("stack.svg")


def block():
    s = Svg(1000, 470, "Inside a block")
    s.text(24, 34, "a block: up to 64 instructions from one PC, fixed code (ROM) only", 14, 700, INK, anchor="start")
    s.text(24, 54, "code in RAM stays interpreted, so no write can make a block stale", 12, color=MUTED, anchor="start")
    # three instruction lanes
    items = [("MOVE.w (A0)+,D1", "native", "green"), ("MULU D2,D1", "handler call", "teal"),
             ("DBF D3,loop", "native", "green")]
    y = 80
    for op, kind, col in items:
        s.box(24, y, 230, 52, None, [], "gray")
        s.text(139, y + 31, op, 13, 600, INK, font="'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace")
        s.arrow([(254, y + 26), (282, y + 26)])
        s.box(284, y, 160, 52, None, [], col)
        s.text(364, y + 31, kind, 13, 650, C[col][2])
        y += 70
    s.code(480, 80, 496, [
        "PPC = pc, PC = pc + 2, IR = op",
        "handler()               ; or native Xtensa",
        "cycles -= cyc[op]",
        "if (PC != next || cycles <= 0) leave",
    ], title="per instruction, what the interpreter loop does")
    s.text(728, 222, "native register-only forms skip the PPC/IR stores and the call", 11.5, color=MUTED)
    # exits
    s.group(24, 300, 952, 150, "a block leaves exactly where m68k_execute() would stop", "red")
    ex = [("taken branch", "PC != next"), ("exception / TRAP", "handler moved PC"),
          ("interrupt", "taken inside a memory handler"), ("end of slice", "cycles <= 0")]
    x = 44
    for t, sub in ex:
        s.box(x, 340, 212, 64, t, [sub], "red", title_size=13.5)
        x += 228
    s.text(500, 432, "the instruction always finishes first: registers, flags and cycles equal the interpreter's",
           12, color=MUTED)
    s.save("block.svg")


def chaining():
    s = Svg(1000, 330, "Block chaining")
    s.box(30, 110, 200, 80, "block A", ["exit to a known target", "(Bcc/DBcc, BRA/BSR, fall-through)"], "orange",
          row_size=11.5)
    s.box(330, 40, 220, 70, "slot, first time", ["stub: back to the dispatcher,", "remember the slot"], "gray",
          row_size=11.5)
    s.box(330, 190, 220, 70, "slot, afterwards", ["block B's chain entry"], "green")
    s.box(700, 40, 260, 70, "dispatcher", ["finds or translates block B", "writes B into the slot"], "blue",
          row_size=11.5)
    s.box(700, 190, 260, 70, "block B", ["runs with no return to C"], "green")
    s.arrow([(232, 135), (328, 80)], "1st time", lx=270, ly=98)
    s.arrow([(552, 75), (698, 75)])
    s.arrow([(830, 112), (830, 150), (440, 150), (440, 188)], "patch", lx=640, ly=150, dashed=True)
    s.arrow([(232, 165), (328, 225)], "next times", lx=270, ly=204)
    s.arrow([(552, 225), (698, 225)], "cycle check first", lx=625, ly=207)
    s.text(500, 300, "loops (DBcc, Bcc back) chain to themselves; on random code a third of the returns to the "
           "dispatcher disappear", 12, color=MUTED)
    s.save("chaining.svg")


def frame_budget():
    s = Svg(1000, 330, "Metal Slug 2 frame budget")
    s.text(24, 34, "Metal Slug 2 in play, core 0, ms per emulated frame (NEOPROF build)", 14, 700, INK, anchor="start")
    scale = 27  # px per ms
    x0 = 170
    def bar(y, label, parts, note):
        s.text(x0 - 14, y + 24, label, 13, 650, INK, anchor="end")
        x = x0
        for name, ms, col in parts:
            w = ms * scale
            stroke, bg, tx = C[col]
            s.add(f'<rect x="{x}" y="{y}" width="{w}" height="38" fill="{stroke}" fill-opacity="0.85" '
                  'stroke="#ffffff" stroke-width="1.5"/>')
            if w > 50:
                s.text(x + w / 2, y + 24, f"{name} {ms:g}", 12, 650, "#ffffff")
            x += w
        s.text(x0 + 24 * scale + 40, y + 24, note, 12.5, 650, INK, anchor="start")
    bar(70, "today", [("68000", 12, "orange"), ("video", 5, "purple"), ("Z80", 4, "teal"),
                      ("other", 2.2, "gray")], "23.6 ms · 42 fps")
    bar(140, "JIT 1.5x", [("68000", 8, "orange"), ("video", 5, "purple"), ("Z80", 4, "teal"),
                          ("other", 2.2, "gray")], "~19 ms")
    bar(210, "JIT 2.5x", [("68000", 4.8, "orange"), ("video", 5, "purple"), ("Z80", 4, "teal"),
                          ("other", 2.2, "gray")], "~16 ms · 60 fps")
    bx = x0 + 16.67 * scale
    s.add(f'<path d="M{bx},58 L{bx},262" stroke="{INK}" stroke-width="2"/>')
    s.text(bx, 280, "16.67 ms = 60 fps", 12, 700, INK)
    for ms in range(0, 25, 4):
        s.text(x0 + ms * scale, 300, str(ms), 11, color=MUTED)
    s.text(x0 + 24 * scale + 14, 300, "ms", 11, color=MUTED, anchor="start")
    s.text(976, 34, "JIT rows: plan estimate (1.5-2.5x on the 68000 only)", 11.5, color=MUTED, anchor="end",
           italic=True)
    s.save("frame-budget.svg")


def verify():
    s = Svg(1000, 290, "How the 68000 dynarec is verified")
    steps = [("lengths", ["m68kjit_insn_len vs the", "disassembler, 45799 opcodes"], "purple", "PC"),
             ("block model", ["C blocks vs m68k_execute()", "random machines, 4 mutations"], "purple", "PC"),
             ("QEMU fuzz", ["Xtensa blocks vs Musashi", "600 seeds + 23 families"], "purple", "QEMU"),
             ("board", ["speed guard vs interpreter", "games + webcam (step 9)"], "blue", "board")]
    x = 24
    for i, (t, r, c, where) in enumerate(steps):
        s.box(x, 70, 220, 100, t, r, c)
        s.badge(x + 8, 60, where, c)
        if i < len(steps) - 1:
            s.arrow([(x + 220, 120), (x + 244, 120)])
        x += 244
    s.text(500, 36, "a change moves right only if the step before it passes", 13, 600, MUTED)
    s.box(24, 196, 952, 76, "every native group was broken on purpose once, and the fuzz caught it",
          ["wrong V on ADD · not-taken cycles · A7 byte step · index sign extension · chain cycle check · ASL's V",
           "and it found one real bug: the PC store clobbered a memory-to-memory MOVE"], "red", title_size=13.5,
          row_size=12)
    s.save("verify.svg")


def roadmap():
    steps = [("8a", "lengths, block model, host fuzz", "done"), ("8b", "Xtensa blocks, m68k-test in QEMU", "done"),
             ("8c", "native register-only forms", "done"), ("8d", "native Bcc / DBcc", "done"),
             ("8e", "memory operands", "done"), ("8f", "indexed modes, PEA/JSR/BSR/RTS, shifts, MOVEM", "done"),
             ("8g", "block chaining", "done"),
             ("9", "mame-go: Musashi 3.1 glue, switch, fallback, speed guard, games", "in progress"),
             ("10", "gwenesis (Mega Drive), if it helps there", "later")]
    rh = 36
    s = Svg(1000, 40 + len(steps) * rh + 20, "68000 dynarec steps")
    spine = 120
    y = 30
    s.add(f'<path d="M{spine},{y + rh / 2} L{spine},{y + (len(steps) - 0.5) * rh}" stroke="#94a3b8" stroke-width="2"/>')
    for n, what, st in steps:
        col = {"done": "green", "in progress": "orange", "later": "gray"}[st]
        cy = y + rh / 2
        bw = 44
        s.add(f'<rect x="{spine - 24 - bw}" y="{cy - 11}" width="{bw}" height="22" rx="11" fill="{C[col][0]}"/>')
        s.text(spine - 24 - bw / 2, cy + 4.5, n, 12, 700, "#ffffff")
        fill = C[col][0] if st == "done" else "#ffffff"
        s.add(f'<circle cx="{spine}" cy="{cy}" r="6" fill="{fill}" stroke="{C[col][0]}" stroke-width="2.4"/>')
        s.text(spine + 22, cy + 4.5, what, 13, color=INK, anchor="start")
        s.text(976, cy + 4.5, st, 12, 650, C[col][0], anchor="end")
        y += rh
    s.save("roadmap.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (interp_vs_jit, stack, block, chaining, frame_budget, verify, roadmap):
        fn()
    print("written:", sorted(os.listdir(OUT)))
