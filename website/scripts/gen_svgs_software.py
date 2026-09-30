#!/usr/bin/env python3
"""Draw the SVG figures that replaced the text diagrams of the software docs.

Same kit as the other doc figures (svgfig.py): hand-placed, vector, one
palette, readable in both site themes. Run: python3 website/scripts/gen_svgs_software.py
Output: website/static/img/diagrams/sw-*.svg

  sw-memory-map.svg     software/overview.md          (memory map)
  sw-simulator.svg      software/simulator.md         (architecture)
  sw-frame-budget.svg   software/snes-optimization.md (why SNES is hard)
  sw-dual-core.svg      software/snes-optimization.md (4.2.1 dual-core split)
  sw-p4-hosted.svg      next-steps/plan-esp32-p4.md   (two chips, two firmwares)
"""
import os

from svgfig import C, INK, LINE, MUTED, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "diagrams")

Svg.out_dir = OUT


def seg(s, x, y, w, h, color, free=False, rx=0):
    """One segment of a stacked bar; free space is drawn white and dashed."""
    stroke, bg, _ = C[color]
    if free:
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="#ffffff" stroke="{LINE}" '
              'stroke-width="1.2" stroke-dasharray="4 3"/>')
    else:
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{stroke}" fill-opacity="0.85" '
              'stroke="#ffffff" stroke-width="1.5"/>')


def swatch(s, x, y, color, free=False):
    if free:
        s.add(f'<rect x="{x}" y="{y - 11}" width="14" height="14" rx="4" fill="#ffffff" stroke="{LINE}" '
              'stroke-width="1.4" stroke-dasharray="3 2"/>')
    else:
        s.add(f'<rect x="{x}" y="{y - 11}" width="14" height="14" rx="4" fill="{C[color][0]}" fill-opacity="0.85"/>')


# ---------------------------------------------------------------------------
def memory_map():
    # (name, size label, weight for the bar, color, free?)
    regions = [
        ("Internal SRAM", "520 KB", "green", "fast · on-chip", [
            ("FreeRTOS stacks", "~32 KB", 32, "blue"),
            ("DMA buffers (display)", "~40 KB", 40, "teal"),
            ("I2S audio DMA", "~8 KB", 8, "purple"),
            ("Emulator hot buffers", "~150 KB (SNES)", 150, "orange"),
            ("Input / misc", "~10 KB", 10, "amber"),
            ("Free", "~280 KB", 280, None),
        ]),
        ("Octal PSRAM", "8 MB", "orange", "large · slower", [
            ("ROM image", "up to 6 MB", 6144, "red"),
            ("Emulator state / VRAM", "~512 KB", 512, "purple"),
            ("Frame buffer (x2)", "~300 KB", 300, "teal"),
            ("Save states", "~256 KB", 256, "blue"),
            ("Free", "~1 MB", 1024, None),
        ]),
        ("Flash", "16 MB", "gray", "code + storage", [
            ("Firmware", "~2-4 MB", 3, "blue"),
            ("NVS (settings)", "~64 KB", 0.0625, "amber"),
            ("OTA partition", "~4 MB (optional)", 4, "purple"),
            ("Free / SPIFFS", "~8 MB", 8, None),
        ]),
    ]
    card_h, gap, top = 176, 18, 20
    s = Svg(1000, top + len(regions) * (card_h + gap) + 14, "Memory map")
    y = top
    for name, size, col, note, items in regions:
        stroke, bg, tx = C[col]
        s.add(f'<rect x="20" y="{y}" width="960" height="{card_h}" rx="14" fill="{bg}" stroke="{stroke}" '
              'stroke-width="1.4"/>')
        s.text(40, y + 30, name, 16, 700, tx, anchor="start")
        s.badge(40 + len(name) * 9.4 + 10, y + 16, size, col)
        s.text(960, y + 30, note, 12, color=MUTED, anchor="end", italic=True)
        # bar, to scale within this memory
        bx, bw, by, bh = 40, 920, y + 46, 34
        total = sum(it[2] for it in items)
        s.add(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="8" fill="#ffffff"/>')
        x = bx
        for label, sz, wgt, c in items:
            w = max(bw * wgt / total, 3)
            seg(s, x, by, w, bh, c or "gray", free=c is None)
            if w > 120:
                s.text(x + w / 2, by + bh / 2 + 4.5, label, 12, 600, "#ffffff" if c else MUTED)
            x += w
        # legend: 3 columns
        cols = 3
        for i, (label, sz, _, c) in enumerate(items):
            lx = 40 + (i % cols) * 310
            ly = y + 112 + (i // cols) * 28
            swatch(s, lx, ly, c, free=c is None)
            s.text(lx + 22, ly, label, 13, 600, INK, anchor="start")
            s.text(lx + 290, ly, sz, 12.5, color=MUTED, anchor="end")
        y += card_h + gap
    s.text(500, y - 2, "bars to scale inside each memory (firmware drawn at 3 MB, the middle of ~2-4 MB)", 11.5,
           color=MUTED, italic=True)
    s.h = y + 12
    s.save("sw-memory-map.svg")


def simulator():
    rows = [
        (("ILI9488 480×320", ["8080 parallel bus", "GPIO 4-11, 12-14, 46"]),
         ("SDL2 window 480×320", ["`sim_display_write()`"]), "display"),
        (("12 tact switches", ["GPIO 40, 41, 42, 1, ..."]),
         ("Keyboard WASD / JK / UI", ["`sim_buttons_read()`"]), "buttons"),
        (("PDM, PAM8403 amp, speaker", ["GPIO 17 (DOUT only)"]),
         ("SDL2 audio 32 kHz mono", ["`sim_audio_write()`"]), "audio"),
        (("SD card on SPI (TF-01A)", ["GPIO 44, 43, 38, 39"]),
         ("Host filesystem (test-roms/)", ["`sdcard_sim_load_rom()`"]), "storage"),
    ]
    bh, gap, top = 76, 16, 70
    s = Svg(1000, top + len(rows) * (bh + gap) + 18, "Hardware vs desktop simulator")
    s.group(20, 20, 400, top - 20 + len(rows) * (bh + gap) + 6, "ESP32 hardware (PCB)", "orange")
    s.group(580, 20, 400, top - 20 + len(rows) * (bh + gap) + 6, "Simulator (SDL2)", "teal")
    s.text(500, 40, "same HAL", 12, 700, MUTED)
    s.text(500, 56, "identical emulator cores", 11.5, color=MUTED)
    for i, (hw, sim, what) in enumerate(rows):
        y = top + i * (bh + gap)
        s.box(40, y, 360, bh, hw[0], hw[1], "orange", title_size=13.5)
        s.box(600, y, 360, bh, sim[0], sim[1], "teal", title_size=13.5, row_size=12.5)
        s.arrow([(404, y + bh / 2), (596, y + bh / 2)], what, lx=500, ly=y + bh / 2, both=True)
    s.save("sw-simulator.svg")


def frame_budget():
    parts = [("65C816 CPU emulation", 4.5, 27, "blue"),
             ("PPU rendering (2 BG layers)", 5.0, 30, "teal"),
             ("SPC700 audio DSP", 8.0, 48, "red"),
             ("Display transfer", 1.5, 9, "purple")]
    s = Svg(1000, 330, "SNES frame time budget (pre-hardware estimate)")
    s.text(40, 40, "Frame time budget: 16.67 ms (for 60 fps)", 16, 700, INK, anchor="start")
    s.text(960, 40, "pre-hardware estimate, single core", 12, color=MUTED, anchor="end", italic=True)
    x0, scale, by, bh = 40, 46, 120, 56          # 46 px per ms: 20 ms = 920 px
    # axis
    for ms in range(0, 21, 2):
        x = x0 + ms * scale
        s.add(f'<path d="M{x},{by + bh + 6} L{x},{by + bh + 12}" stroke="{LINE}" stroke-width="1.2"/>')
        s.text(x, by + bh + 27, f"{ms}", 11.5, color=MUTED)
    s.text(x0 + 20 * scale, by + bh + 45, "ms", 11.5, color=MUTED, anchor="end")
    # over-budget zone
    xb = x0 + 16.67 * scale
    xt = x0 + 19.0 * scale
    s.add(f'<rect x="{xb}" y="{by - 14}" width="{xt - xb}" height="{bh + 28}" fill="{C["red"][1]}" '
          f'stroke="{C["red"][0]}" stroke-width="1" stroke-dasharray="3 3"/>')
    x = x0
    for i, (name, ms, pct, col) in enumerate(parts):
        w = ms * scale
        seg(s, x, by, w, bh, col)
        if w > 150:
            s.text(x + w / 2, by + 24, name, 12.5, 650, "#ffffff")
            s.text(x + w / 2, by + 42, f"~{ms} ms · {pct}%", 12, color="#ffffff")
        else:
            # narrow segment: label above with a leader
            s.text(x + w / 2, by - 36, f"{name}", 12, 650, C[col][2])
            s.text(x + w / 2, by - 21, f"~{ms} ms · {pct}%", 11.5, color=MUTED)
        x += w
    # budget line
    s.add(f'<path d="M{xb},{by - 60} L{xb},{by + bh + 14}" stroke="{INK}" stroke-width="2.2"/>')
    s.text(xb - 8, by - 64, "16.67 ms budget", 12, 700, INK, anchor="end")
    # callouts
    spc_x = x0 + (4.5 + 5.0 + 4.0) * scale
    s.arrow([(spc_x, by + bh + 58), (spc_x, by + bh + 4)], color=C["red"][0])
    s.text(spc_x, by + bh + 76, "bottleneck", 12.5, 700, C["red"][0])
    s.add(f'<rect x="{x0}" y="{by + bh + 92}" width="920" height="38" rx="10" fill="{C["red"][1]}" '
          f'stroke="{C["red"][0]}" stroke-width="1.4"/>')
    s.text(x0 + 16, by + bh + 116, "TOTAL  ~19.0 ms  =  114% of the budget", 14, 700, C["red"][2], anchor="start")
    s.text(x0 + 904, by + bh + 116, "over budget: ~30 fps instead of 60", 12.5, 600, C["red"][0], anchor="end")
    s.h = by + bh + 150
    s.save("sw-frame-budget.svg")


def dual_core():
    s = Svg(1000, 400, "Dual-core split: Core 0 main, Core 1 audio")
    lanes = [
        ("Core 0 (main)", "blue", ["65C816 CPU emulation", "PPU rendering", "Display transfer", "Input polling"]),
        ("Core 1 (audio)", "purple", ["SPC700 CPU emulation", "DSP (assembly from Phase 4.1)",
                                      "I2S DMA output feed"]),
    ]
    for i, (name, col, items) in enumerate(lanes):
        x = 20 + i * 490
        s.group(x, 20, 470, 190, name, col)
        yy = 56
        for it in items:
            s.box(x + 20, yy, 430, 30, None, [], col, r=8, shadow=False)
            s.text(x + 235, yy + 20, it, 12.5, 600, C[col][2])
            yy += 36
    # ms/frame bars on a common scale against the 16.67 ms frame
    x0, scale = 170, 44          # 44 px per ms: 17 ms = 748 px
    top = 250
    s.text(40, top - 10, "ms per frame", 12, 700, MUTED, anchor="start")
    for ms in range(0, 18, 2):
        x = x0 + ms * scale
        s.text(x, top + 118, f"{ms}", 11.5, color=MUTED)
    xb = x0 + 16.67 * scale
    s.add(f'<path d="M{xb},{top - 4} L{xb},{top + 104}" stroke="{INK}" stroke-width="2" stroke-dasharray="5 4"/>')
    s.text(xb, top - 12, "16.67 ms", 11.5, 700, INK)
    # core 0
    s.text(x0 - 14, top + 30, "Core 0", 13, 700, C["blue"][2], anchor="end")
    seg(s, x0, top + 10, 10.5 * scale, 32, "blue", rx=6)
    s.text(x0 + 10.5 * scale / 2, top + 31, "~10.5 ms/frame", 12.5, 650, "#ffffff")
    s.text(x0 + 10.5 * scale + 10, top + 31, "bottleneck at 11 ms", 12, 600, C["blue"][0], anchor="start")
    # core 1
    s.text(x0 - 14, top + 80, "Core 1", 13, 700, C["purple"][2], anchor="end")
    seg(s, x0, top + 60, 8.0 * scale, 32, "purple", free=True, rx=6)
    seg(s, x0, top + 60, 5.0 * scale, 32, "purple", rx=6)
    s.text(x0 + 5.0 * scale / 2, top + 81, "~5 ms with ASM", 12.5, 650, "#ffffff")
    s.text(x0 + 6.5 * scale, top + 81, "~8.0", 12, 600, MUTED)
    s.text(x0 + 8.0 * scale + 10, top + 81, "runs fully in parallel", 12, 600, C["purple"][0], anchor="start")
    s.h = top + 136
    s.save("sw-dual-core.svg")


def p4_hosted():
    s = Svg(1000, 420, "ESP32-P4 and the radio chip: two firmwares")
    s.group(20, 20, 960, 190, "ESP32-P4", "blue", badge="OUR FIRMWARE")
    s.box(40, 56, 920, 40, None, [], "blue", r=8, shadow=False)
    s.text(500, 81, "retro-go launcher + emulators", 13.5, 650, C["blue"][2])
    s.box(40, 104, 450, 44, None, [], "blue", r=8, shadow=False)
    s.text(265, 131, "lwIP network stack", 13, 600, C["blue"][2])
    s.box(510, 104, 450, 44, None, [], "blue", r=8, shadow=False)
    s.text(735, 124, "Bluedroid Bluetooth host", 13, 600, C["blue"][2])
    s.text(735, 140, "HID host for controllers", 11.5, color=MUTED)
    s.box(40, 156, 920, 40, None, [], "blue", r=8, shadow=False)
    s.text(500, 175, "esp_hosted + esp_wifi_remote", 12.5, 600, INK,
           font="'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace")
    s.text(500, 190, "Wi-Fi calls look local (esp_wifi_*)", 11.5, color=MUTED)
    s.arrow([(500, 212), (500, 298)], "SDIO (4-bit, 40 MHz) or SPI  ·  RESET line  ·  UART pads", lx=500, ly=255,
            both=True, width=2.4)
    s.group(20, 300, 960, 100, "radio chip", "gray", badge="ESPRESSIF FIRMWARE")
    s.box(40, 336, 920, 48, None, [], "gray", r=8, shadow=False)
    s.text(500, 356, "ESP-Hosted slave", 13.5, 650, C["gray"][2])
    s.text(500, 373, "Wi-Fi driver + Bluetooth controller (HCI over VHCI)", 12, color=MUTED)
    s.save("sw-p4-hosted.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (memory_map, simulator, frame_budget, dual_core, p4_hosted):
        fn()
    print("written:", sorted(f for f in os.listdir(OUT) if f.startswith("sw-")))
