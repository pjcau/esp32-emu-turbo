#!/usr/bin/env python3
"""mbsum.py <log>: MAMEBENCH hashes, the average NEOPROF ms (68000, video, total core 0)
and, from the same window, the V0 video split (palette / clear / sprites / fix) with the
KB each part moves per frame (sprite and fix writes are upper bounds)."""
import sys, re
hashes, rows, split, core1 = [], [], [], []
for l in open(sys.argv[1], errors="replace"):
    m = re.search(r"MAMEBENCH frames (\d+) hash ([0-9a-f]+)", l)
    if m: hashes.append(f"{m.group(1)}:{m.group(2)}")
    m = re.search(r"NEOPROF ms/frame: other ([\d.]+) 68000 ([\d.]+) z80 ([\d.]+) ym2610 ([\d.]+) video ([\d.]+) mixer ([\d.]+) blit ([\d.]+) out ([\d.]+)", l)
    if m: rows.append([float(x) for x in m.groups()])
    m = re.search(r"NEOPROF video ms/frame: palette ([\d.]+) clear ([\d.]+) sprites ([\d.]+) fix ([\d.]+) rest ([\d.]+)(?: copy ([\d.]+))?"
                  r" \| KB/frame: clear w ([\d.]+) sprites r ([\d.]+) w<=([\d.]+) strips ([\d.]+) fix r ([\d.]+) w<=([\d.]+) tiles ([\d.]+)(?: copy w ([\d.]+))?", l)
    if m: split.append([float(x or 0) for x in m.groups()])   # copy: NEOBAND builds only
    m = re.search(r"NEOPROF core1 ms/frame: .*ym2610 ([\d.]+) display ([\d.]+)(?: dmawait ([\d.]+) sends ([\d.]+))? \| busy core0 (\d+)% .*core1 (\d+)%", l)
    if m: core1.append([float(x or 0) for x in m.groups()])
print("hashes", " ".join(hashes))
def window(rows):
    return rows[2:] if len(rows) > 4 else rows      # skip the warm-up
if rows:
    r = window(rows)
    avg = [sum(c) / len(r) for c in zip(*r)]
    print("avg over %d: 68000 %.2f video %.2f other %.2f mixer %.2f -> core0 %.2f ms" % (len(r), avg[1], avg[4], avg[0], avg[5], sum(avg)))
if core1:
    r = window(core1)
    a = [sum(c) / len(r) for c in zip(*r)]
    print("core1 over %d: ym2610 %.2f display %.2f ms (dma wait %.2f, %.0f sends) | busy core0 %.0f%% core1 %.0f%%" % (len(r), a[0], a[1], a[2], a[3], a[4], a[5]))
if split:
    r = window(split)
    a = [sum(c) / len(r) for c in zip(*r)]
    print("video split over %d: palette %.2f clear %.2f sprites %.2f fix %.2f rest %.2f copy %.2f ms" % (len(r), a[0], a[1], a[2], a[3], a[4], a[5]))
    print("PSRAM KB/frame: clear w %.1f | sprites r %.1f w<=%.1f (%.0f strips) | fix r %.1f w<=%.1f (%.0f tiles) | copy w %.1f | total r %.1f w<=%.1f"
          % (a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13], a[7] + a[10], a[6] + a[8] + a[11] + a[13]))
