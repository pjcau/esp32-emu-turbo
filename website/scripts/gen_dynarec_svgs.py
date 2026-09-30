#!/usr/bin/env python3
"""Draw the SVG figures of docs/software/gba-dynarec.md.

Hand-placed boxes and arrows, one palette, one font stack: the figures stay
vector, readable in both site themes (each has its own card background) and
reproducible. Run: python3 website/scripts/gen_dynarec_svgs.py
Output: website/static/img/gba-dynarec/*.svg
"""
import os

from svgfig import C, INK, MUTED, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "gba-dynarec")

Svg.out_dir = OUT


# ---------------------------------------------------------------------------
def interp_vs_dynarec():
    s = Svg(1000, 330, "Interpreter vs dynarec")
    s.group(20, 20, 470, 290, "Interpreter  ·  execute_arm", "gray")
    s.text(255, 60, "pays fetch + decode + dispatch on EVERY instruction, every frame", 12, color=MUTED)
    s.box(60, 90, 170, 64, "fetch", ["next ARM/Thumb opcode"], "gray")
    s.box(280, 90, 170, 64, "decode", ["big switch in C"], "gray")
    s.box(170, 210, 170, 64, "execute", ["C code per opcode"], "gray")
    s.arrow([(230, 122), (278, 122)])
    s.arrow([(365, 156), (300, 208)])
    s.arrow([(200, 208), (140, 158)])
    s.group(510, 20, 470, 290, "Dynarec  ·  execute_arm_translate", "green")
    s.text(745, 60, "pays them ONCE per block, then runs native Xtensa code", 12, color=MUTED)
    s.box(540, 90, 410, 64, "first time a block is reached", ["decode it once, write Xtensa code into the cache"],
          "orange")
    s.box(540, 210, 410, 64, "every other time", ["jump straight into the generated code (blocks chain)"], "green")
    s.arrow([(745, 156), (745, 208)], "translate once", lx=745, ly=182)
    s.save("interp-vs-dynarec.svg")


def stack():
    s = Svg(1000, 690, "The stack, layer by layer")
    rows = [
        ("GBA game", "gray", [("ARM7TDMI code in the cartridge ROM", "", 700)]),
        ("retro-go", "blue", [("launcher", "pick a game · resume/save states", 300),
                              ("gbsp app", "frame loop · input · display · audio · menus", 390)]),
        ("gpSP core", "teal", [("GBA hardware model", "memory map · DMA · timers · IRQ · sound · renderer", 380),
                               ("CPU", "interpreter (cpu.cpp)  or  translator (cpu_threaded.c)", 310)]),
        ("Xtensa dynarec", "orange", [("backend", "xtensa_emit*.h · xtensa_stub.c: what each op becomes", 380),
                                      ("xjit core", "encoders · labels · executable memory", 310)]),
        ("ESP-IDF 5.4", "purple", [("FreeRTOS + drivers", "2 cores · esp_mmu_map (PSRAM exec) · cache sync · heap caps", 700)]),
        ("ESP32-S3 N16R8", "gray", [("2 × Xtensa LX7 240 MHz", "32 KB I-cache shared · 64 KB D-cache", 340),
                                    ("memory", "~190 KB internal free · 8 MB PSRAM · 16 MB flash", 350)]),
    ]
    y = 24
    for i, (label, col, items) in enumerate(rows):
        stroke, bg, tx = C[col]
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
            s.arrow([(500, y + h + 1), (500, y + h + 17)], head=True)
        y += h + 18
    s.save("stack.svg")


def usage():
    s = Svg(1000, 420, "How it is used by a developer")
    s.group(20, 20, 300, 250, "1 · build (docker)", "blue")
    s.box(36, 56, 268, 72, None, ["`GBAJIT=1 python rg_tool.py`", "`--target=esp32-emu-turbo`", "`build gbsp`"], "blue",
          row_size=12.5)
    s.box(36, 142, 268, 112, "optional flags", ["GBAPROF=1  profiler lines", "GBABENCH=1  self-playing benchmark",
                                                "GBAJIT_IRAM=1  experiment (off)"], "blue", row_size=12)
    s.group(350, 20, 290, 250, "2 · install", "teal")
    s.box(366, 56, 258, 100, "SD update", ["`scripts/sd_update.py`", "`--console gbsp`", "no USB flashing"], "teal")
    s.box(366, 170, 258, 84, "on the console", ["launcher > GBA > game", "gbsp runs the dynarec"], "teal")
    s.group(670, 20, 310, 250, "3 · run and measure", "green")
    s.box(686, 56, 278, 58, "scripts/board_ctl.py", ["launch · resume · volume 0 · keys"], "green")
    s.box(686, 124, 278, 58, "console lines", ["GBAPROF · GBASAMPLE · GBABENCH"], "green")
    s.box(686, 192, 278, 62, "scripts/board_cam.py", ["webcam photo of the screen"], "green")
    s.arrow([(320, 145), (348, 145)])
    s.arrow([(640, 145), (668, 145)])
    s.group(20, 296, 960, 104, "0 · correctness first, no board needed", "purple")
    s.box(36, 330, 280, 56, "gbajit-test in QEMU", ["ROM + level state, fixed input"], "purple")
    s.box(360, 330, 280, 56, "x86 reference", ["gpSP's own x86 dynarec"], "purple")
    s.box(684, 330, 280, 56, "video + audio hashes equal", ["or the change is rejected"], "purple")
    s.arrow([(316, 358), (358, 358)])
    s.arrow([(640, 358), (682, 358)])
    s.arrow([(170, 270), (170, 294)], None, dashed=True)
    s.save("usage.svg")


def memory():
    s = Svg(1000, 520, "Where everything lives")
    s.group(20, 20, 300, 400, "internal RAM · fast", "green")
    s.box(36, 56, 268, 120, "hot C helpers (XT_HOT)", ["xt_load / xt_store · update_gba", "timers · sound_timer · IRQ",
                                                        "block lookup · m4a_run"], "green")
    s.box(36, 188, 268, 84, "core-1 renderer hot path", ["render_scanline_text<u16>", "display_task"], "green")
    s.box(36, 284, 268, 60, "reg[]", ["ARM registers · flags · helper table"], "green")
    s.text(170, 380, "fetched directly: no cache, no misses", 12, color=C["green"][0], weight=600)
    s.group(350, 20, 300, 400, "PSRAM 8 MB · slow for code", "orange")
    s.box(366, 56, 268, 70, "GBA memory", ["EWRAM · VRAM · IWRAM · ROM pages"], "orange")
    s.box(366, 138, 268, 56, "block hash tables", [], "orange")
    s.box(366, 206, 268, 120, "translation caches", ["ROM 2 MB + RAM 384 KB", "mapped twice: data + exec",
                                                     "Metal Slug: ~900 KB of code"], "orange")
    s.group(680, 20, 300, 400, "flash · XIP", "gray")
    s.box(696, 56, 268, 90, "cold code", ["translator (cpu_threaded.c)", "menus · file system · rest"], "gray")
    s.box(696, 158, 268, 70, "rest of the renderer", ["blending / affine / OBJ variants"], "gray")
    # I-cache
    s.add('<rect x="380" y="444" width="240" height="60" rx="30" fill="#fef2f2" stroke="#dc2626" stroke-width="2" filter="url(#sh)"/>')
    s.text(500, 470, "32 KB instruction cache", 14, 700, "#7f1d1d")
    s.text(500, 489, "shared by core 0 AND core 1", 12, 400, "#7f1d1d")
    s.arrow([(500, 328), (500, 440)], "translated code\n(a miss costs ~11x)", lx=500, ly=372, color="#dc2626")
    s.arrow([(830, 230), (830, 474), (624, 474)], "flash code", lx=830, ly=395, color="#64748b")
    s.save("memory.svg")


def lifecycle():
    s = Svg(1000, 450, "Life of a block")
    s.box(40, 190, 170, 70, "lookup PC", ["hash table (ROM / RAM)"], "blue")
    s.box(330, 40, 200, 70, "translate", ["decode once, emit Xtensa", "sync the cache"], "orange")
    s.box(330, 190, 200, 70, "run", ["native code, cycles in a3"], "green")
    s.box(700, 60, 240, 70, "linked", ["exit patched into a direct j"], "teal")
    s.box(700, 300, 240, 70, "flushed", ["cache full, or the game", "overwrote code in RAM"], "red")
    s.box(330, 330, 200, 60, "update_gba", ["timers · DMA · IRQ · frame end"], "gray", title_size=13)
    s.arrow([(210, 205), (328, 92)], "miss", lx=262, ly=140)
    s.arrow([(430, 112), (430, 188)], "done", lx=430, ly=150)
    s.arrow([(210, 222), (328, 222)], "hit", lx=268, ly=222)
    s.arrow([(530, 205), (698, 112)], "exit taken once", lx=612, ly=150)
    s.arrow([(760, 132), (760, 234), (532, 234)], "next time: direct jump, no lookup", lx=660, ly=234, dashed=True)
    s.arrow([(328, 250), (212, 250)], None)
    s.text(270, 276, "indirect branch", 11.5, color=MUTED)
    s.text(270, 291, "(bx, pop pc, IRQ)", 11.5, color=MUTED)
    s.arrow([(430, 262), (430, 328)], "cycles run out", lx=430, ly=296)
    s.arrow([(328, 360), (125, 360), (125, 262)], "next slice", lx=226, ly=360, dashed=True)
    s.arrow([(530, 256), (698, 330)], "SMC / cache full", lx=610, ly=300)
    s.arrow([(820, 372), (820, 425), (70, 425), (70, 262)], "everything retranslated on demand", lx=445, ly=425,
            dashed=True)
    s.save("lifecycle.svg")


def instruction():
    s = Svg(1000, 400, "One instruction, end to end")
    steps = [
        ("ROM bytes", ["`0x1888`", "adds r0, r1, r2"], "gray"),
        ("decode", ["cpu_threaded.c", "format 2 · flags dead"], "teal"),
        ("ARM/Thumb op", ["xtensa_emit_ops.h", "thumb_data_proc(add)"], "orange"),
        ("Xtensa op", ["xtensa_emit.h · xt_add_op", "no C/V: straight into rd"], "orange"),
        ("encode", ["xjit_emit.h", "16-bit density forms"], "purple"),
    ]
    x = 24
    for i, (t, r, c) in enumerate(steps):
        s.box(x, 30, 176, 96, t, r, c)
        if i < len(steps) - 1:
            s.arrow([(x + 176, 78), (x + 194, 78)])
        x += 194
    s.arrow([(906, 128), (906, 170), (560, 170), (560, 196)], "8 bytes into the translation cache", lx=730, ly=170)
    s.code(300, 200, 520, [
        "l32i.n  a10, a2, 8      ; a10 = r2   (reg[2])",
        "l32i.n  a11, a2, 4      ; a11 = r1   (reg[1])",
        "add.n   a10, a10, a11   ; r1 + r2",
        "s32i.n  a10, a2, 0      ; reg[0] = result",
    ], title="generated Xtensa code")
    s.box(24, 200, 250, 150, "if flags are live", ["C: saltu", "V: xor · and · extui", "Z: nsau · extui",
                                                  "N: extui", "each stored as a 0/1 word"], "amber", row_size=12)
    s.text(560, 350, "a2 = &reg[0] · guest registers r0..r15 at offsets 0..60 (reach of l32i.n)", 12, color=MUTED)
    s.save("instruction.svg")


def frame():
    s = Svg(1000, 600, "How a frame runs")
    lanes = [("frame loop", "core 0", "blue"), ("execute_arm_translate", "core 0", "teal"),
             ("translated block", "PSRAM", "orange"), ("C helper", "IRAM", "green"), ("renderer", "core 1", "purple")]
    xs = [110, 300, 500, 700, 890]
    for (t, sub, c), x in zip(lanes, xs):
        s.box(x - 85, 20, 170, 56, t, [sub], c, title_size=13)
        s.add(f'<path d="M{x},78 L{x},580" stroke="{C[c][0]}" stroke-width="1.5" stroke-dasharray="4 5" opacity="0.6"/>')
    def msg(a, b, y, label, dashed=False):
        x1, x2 = xs[a], xs[b]
        d = 1 if x2 > x1 else -1
        s.arrow([(x1 + 4 * d, y), (x2 - 6 * d, y)], None, dashed=dashed)
        s.text((x1 + x2) / 2, y - 7, label, 12, color=INK)
    msg(0, 1, 118, "run one frame of cycles")
    msg(1, 2, 160, "xt_enter, first block")
    s.add('<rect x="420" y="186" width="370" height="170" rx="10" fill="#fff7ed" fill-opacity="0.6" stroke="#ea580c" stroke-dasharray="5 4"/>')
    s.text(432, 204, "loop until the cycle budget runs out", 11.5, 600, "#c2410c", anchor="start")
    s.text(500, 228, "ALU ops on reg[]", 12, color=INK)
    msg(2, 3, 262, "memory access (callx8)")
    msg(3, 2, 292, "value, or redirect (IRQ, SMC)", dashed=True)
    s.text(500, 330, "branch: direct jump to the next block", 12, color=INK)
    msg(2, 3, 392, "xt_update_gba (cycles used up)")
    msg(3, 4, 428, "scanline ready (queue + notify)")
    msg(3, 1, 466, "frame done: retw", dashed=True)
    msg(1, 0, 500, "return", dashed=True)
    msg(0, 4, 536, "wait for the last lines, then display + audio")
    s.save("frame.svg")


def pieces():
    s = Svg(1000, 560, "The pieces")
    s.group(20, 20, 960, 100, "gbsp app  ·  retro-go/gbsp/main/main.c", "blue")
    s.box(40, 52, 430, 54, "frame loop", ["input · execute · display · audio"], "blue")
    s.box(510, 52, 450, 54, "GBAPROF / GBABENCH", ["profiler · deterministic benchmark"], "blue")
    s.group(20, 140, 960, 124, "gpSP core  ·  gbsp-libretro", "teal")
    s.box(40, 172, 220, 76, "translator", ["cpu_threaded.c", "decode · lookup · flags"], "teal")
    s.box(276, 172, 210, 76, "interpreter", ["cpu.cpp", "GBAJIT=0 fallback"], "teal", dashed=True)
    s.box(502, 172, 220, 76, "memory · DMA · IRQ", ["gba_memory.c · main.c"], "teal")
    s.box(738, 172, 222, 76, "renderer · m4a HLE", ["video.cpp (core 1)", "m4a_hle.h"], "teal")
    s.group(20, 284, 960, 124, "Xtensa backend  ·  gbsp-libretro/xtensa", "orange", badge="NEW")
    s.box(40, 316, 290, 76, "xtensa_emit_ops.h", ["ARM/Thumb op to Xtensa", "port of the x86 backend"], "orange")
    s.box(346, 316, 290, 76, "xtensa_emit.h", ["host registers · immediates", "exits and patching"], "orange")
    s.box(652, 316, 308, 76, "xtensa_stub.c", ["C helpers the code calls", "loads/stores · update · xt_enter"], "orange")
    s.group(20, 428, 960, 116, "xjit shared core  ·  retro-go/components/xjit", "purple", badge="REUSABLE")
    s.box(40, 460, 290, 68, "xjit_emit.h", ["encoders, checked vs the assembler"], "purple")
    s.box(346, 460, 290, 68, "xjit_block.c", ["labels · literal pools"], "purple")
    s.box(652, 460, 308, 68, "xjit_exec.c", ["PSRAM mapped for fetch · cache sync"], "purple")
    s.arrow([(255, 106), (150, 170)])
    s.arrow([(150, 248), (185, 314)])
    s.arrow([(330, 354), (344, 354)])
    s.arrow([(490, 392), (185, 458)])
    s.arrow([(806, 314), (612, 250)], "calls", lx=720, ly=280)
    s.arrow([(806, 392), (806, 458)], None, dashed=True)
    s.save("pieces.svg")


def verify():
    s = Svg(1000, 250, "How every change is verified")
    steps = [("encoders", ["xjit_emit vs objdump", "(PC)"], "purple"),
             ("QEMU esp32s3", ["gbajit-test, 8 MB PSRAM", "hashes == x86 dynarec"], "purple"),
             ("board: GBABENCH", ["work ms/frame", "screen hash unchanged"], "blue"),
             ("board: played run", ["fps on screen", "webcam photos"], "green")]
    x = 24
    for i, (t, r, c) in enumerate(steps):
        s.box(x, 60, 220, 96, t, r, c)
        if i < len(steps) - 1:
            s.arrow([(x + 220, 108), (x + 244, 108)])
        x += 244
    s.text(500, 36, "a change moves right only if the step before it passes", 13, 600, MUTED)
    s.box(268, 180, 220, 50, "x86 reference", ["gpSP x86 dynarec (i386 docker)"], "gray", row_size=11.5, title_size=13)
    s.arrow([(378, 180), (378, 158)])
    s.save("verify.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (interp_vs_dynarec, stack, usage, memory, lifecycle, instruction, frame, pieces, verify):
        fn()
    print("written:", sorted(os.listdir(OUT)))
