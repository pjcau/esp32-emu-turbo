#!/usr/bin/env python3
"""Draw the SVG figures of xtensa-68000-dynarec/docs/codegen-plan.md.

Same kit as every other figure (svgfig.py). Run:
python3 website/scripts/gen_svgs_codegen.py
Output: retro-go/xtensa-68000-dynarec/docs/img/codegen-*.svg
"""
import os

from svgfig import C, INK, MUTED, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "retro-go", "xtensa-68000-dynarec", "docs", "img")

Svg.out_dir = OUT

MONO = "'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace"


def bytes_per_insn():
    rows = [("today (a31679d)", 75, "red", "measured: 70-80"),
            ("F1  16-bit forms", 58, "orange", "-20-25 %"),
            ("F2  IRQs at instruction boundaries", 40, "amber", "-30-40 % on memory ops"),
            ("F3  direct ROM/RAM access", 38, "teal", "speed more than size"),
            ("F4  guest registers in host registers", 28, "blue", "fewer loads/stores"),
            ("target", 22, "green", "20-25 B")]
    s = Svg(1000, 70 + len(rows) * 50 + 50, "Bytes of Xtensa code per 68000 instruction")
    s.text(24, 34, "Xtensa bytes per translated 68000 instruction", 15, 700, INK, anchor="start")
    s.text(976, 34, "only the first row is measured; the others are the plan's estimates", 11.5, color=MUTED,
           anchor="end", italic=True)
    x0, scale = 330, 6.4
    y = 62
    for label, v, col, note in rows:
        stroke, bg, tx = C[col]
        s.text(x0 - 14, y + 23, label, 13, 600, INK, anchor="end")
        dashed = '' if label.startswith("today") else ' stroke-dasharray="5 4"'
        s.add(f'<rect x="{x0}" y="{y + 4}" width="{v * scale}" height="30" rx="6" fill="{bg}" stroke="{stroke}" '
              f'stroke-width="1.6"{dashed}/>')
        s.text(x0 + v * scale - 10, y + 24, f"~{v}", 13, 700, tx, anchor="end")
        s.text(x0 + v * scale + 12, y + 24, note, 12, color=MUTED, anchor="start")
        y += 50
    for b in (0, 20, 40, 60, 80):
        s.add(f'<path d="M{x0 + b * scale},{y + 2} L{x0 + b * scale},{y + 8}" stroke="{MUTED}" stroke-width="1"/>')
        s.text(x0 + b * scale, y + 24, str(b), 11, color=MUTED)
    s.text(x0 + 80 * scale + 16, y + 24, "bytes", 11, color=MUTED, anchor="start")
    s.save("codegen-bytes.svg")


def memory_access():
    s = Svg(1000, 470, "One memory read, before and after")
    s.text(24, 34, "MOVE.w (A0)+,D1 : the code generated for the read", 15, 700, INK, anchor="start")
    s.group(20, 54, 470, 396, "today: Musashi 3.1 may take an IRQ inside the read", "red")
    before = [("s32i  a5, PPC", "state an IRQ inside the", "handler would push"),
              ("movi + s32i  IR", None, None),
              ("movi + s32i  PC", None, None),
              ("compute + store X N Z V C", "all flags live before", "every access"),
              ("l32i  A0 ; addi ; s32i  A0", "address + (An)+ update", None),
              ("l32r  handler ; mov a10 ; callx8", "MAME memory tables", "for ROM and RAM too"),
              ("PC != next ? leave", "check after the call", None)]
    y = 92
    for code, n1, n2 in before:
        s.add(f'<rect x="36" y="{y}" width="250" height="40" rx="7" fill="#ffffff" stroke="{C["red"][0]}" '
              'stroke-width="1.2"/>')
        s.text(48, y + 25, code, 11.5, 600, INK, anchor="start", font=MONO)
        if n1:
            s.text(300, y + 18 if n2 else y + 25, n1, 11.5, color=MUTED, anchor="start")
        if n2:
            s.text(300, y + 33, n2, 11.5, color=MUTED, anchor="start")
        y += 48
    s.group(510, 54, 470, 396, "after F2 + F3: IRQs between instructions", "green")
    after = [("l32i.n  a4, A0", "A0 (or a pinned register, F4)"),
             ("addi.n ; s32i.n  A0", "(An)+ update"),
             ("extui  page ; l32i  base", "64 KB page table, shared"),
             ("beqz  base, cold", "I/O or bank: out of line"),
             ("add ; l16ui  a7", "direct read, no call")]
    y = 92
    for code, note in after:
        s.add(f'<rect x="526" y="{y}" width="250" height="40" rx="7" fill="#ffffff" stroke="{C["green"][0]}" '
              'stroke-width="1.2"/>')
        s.text(538, y + 25, code, 11.5, 600, INK, anchor="start", font=MONO)
        s.text(790, y + 25, note, 11.5, color=MUTED, anchor="start")
        y += 48
    s.box(526, y + 8, 438, 76, "cold area at the end of the block",
          ["slow path: callx8 into MAME for I/O and banks", "flags only where a later instruction reads them"],
          "gray", title_size=13, row_size=11.5)
    s.save("codegen-memory.svg")


def registers():
    s = Svg(1000, 400, "Host registers across a call")
    s.text(24, 34, "what survives a windowed call in the block's registers", 15, 700, INK, anchor="start")

    def row(y, title, keep, color, labels):
        s.text(24, y + 26, title, 13, 700, INK, anchor="start")
        for r in range(16):
            x = 150 + r * 52
            kept = r < keep
            stroke, bg, tx = C[color] if kept else C["gray"]
            fill = bg if kept else "#ffffff"
            dash = '' if kept else ' stroke-dasharray="4 3"'
            s.add(f'<rect x="{x}" y="{y}" width="46" height="40" rx="6" fill="{fill}" stroke="{stroke}" '
                  f'stroke-width="1.4"{dash}/>')
            s.text(x + 23, y + 17, f"a{r}", 11, 700, tx if kept else MUTED)
            lab = labels.get(r, "")
            if lab:
                s.text(x + 23, y + 32, lab, 10, 600, tx if kept else MUTED)
        return y

    common = {0: "ret", 1: "sp", 2: "base", 3: "&cyc", 4: "addr", 5: "pc", 6: "cyc", 7: "value"}
    row(70, "callx8 today", 8, "orange", {**common, 8: "tmp", 9: "tmp", 10: "arg", 11: "arg"})
    s.text(150 + 8 * 52, 136, "a8-a15 become the callee's a0-a7: lost at every call", 12, color=C["red"][0],
           anchor="start")
    row(180, "callx12 (F4)", 12, "blue", {**common, 8: "D0", 9: "D1", 10: "A0", 11: "A7"})
    s.text(150 + 12 * 52, 246, "args in a14, a15", 12, color=MUTED, anchor="start")
    s.box(150, 290, 826, 86, "pinned guest registers",
          ["the 4 most used (from F0's counts, e.g. D0 D1 A0 A7) live in a8-a11 for the whole block",
           "written back to Musashi's dar[] only before a handler call and when the block leaves"],
          "blue", title_size=13.5, row_size=12)
    s.save("codegen-registers.svg")


def steps():
    st = [("F0", "measure", "bytes per instruction by kind, flushes/min, 68000 ms", "gray"),
          ("F1", "16-bit forms", "l32i.n / s32i.n / mov.n / add.n / addi.n / movi.n", "orange"),
          ("F2", "IRQs between instructions", "interpreter AND dynarec, new reference hashes, webcam", "amber"),
          ("F3", "direct ROM / RAM access", "page table shared with the interpreter (9d-1), idle hash kept", "teal"),
          ("F4", "pinned registers", "callx12, 4 guest registers in a8-a11", "blue"),
          ("F5", "lazy flags", "only if flags are still > 15 % of the code after F2", "purple"),
          ("F6", "code cache in IRAM", "deferred: needs >= 24 KB of internal RAM free", "gray")]
    rh = 58
    s = Svg(1000, 70 + len(st) * rh + 70, "Code generation plan steps")
    s.text(24, 34, "each step: QEMU fuzz 0 mismatches (Musashi 4.5 + 3.1), MAMEBENCH 7/7 hashes, 68000 ms measured",
           13, 650, INK, anchor="start")
    y = 56
    for i, (n, t, d, col) in enumerate(st):
        stroke = C[col][0]
        s.add(f'<rect x="24" y="{y}" width="56" height="44" rx="10" fill="{stroke}"/>')
        s.text(52, y + 28, n, 15, 700, "#ffffff")
        s.box(92, y, 884, 44, None, [], col, shadow=False, dashed=(n in ("F5", "F6")))
        s.text(108, y + 27, t, 13.5, 700, C[col][2], anchor="start")
        s.text(400, y + 27, d, 12, color=INK, anchor="start")
        if i < len(st) - 1:
            s.arrow([(52, y + 44), (52, y + rh - 1)])
        y += rh
    s.box(24, y + 6, 952, 52, "goal: ~20-25 bytes per 68000 instruction, 68000 under the interpreter's 8.71 ms "
          "(aim 5-6 ms)", [], "green", title_size=13.5)
    s.save("codegen-steps.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (bytes_per_insn, memory_access, registers, steps):
        fn()
    print("written:", sorted(f for f in os.listdir(OUT) if f.startswith("codegen-")))
