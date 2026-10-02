#!/usr/bin/env python3
"""mbsum.py <log>: MAMEBENCH hashes and the average NEOPROF ms (68000, video, total core 0)"""
import sys, re
hashes, rows = [], []
for l in open(sys.argv[1], errors="replace"):
    m = re.search(r"MAMEBENCH frames (\d+) hash ([0-9a-f]+)", l)
    if m: hashes.append(f"{m.group(1)}:{m.group(2)}")
    m = re.search(r"NEOPROF ms/frame: other ([\d.]+) 68000 ([\d.]+) z80 ([\d.]+) ym2610 ([\d.]+) video ([\d.]+) mixer ([\d.]+) blit ([\d.]+) out ([\d.]+)", l)
    if m: rows.append([float(x) for x in m.groups()])
print("hashes", " ".join(hashes))
if rows:
    r = rows[2:] if len(rows) > 4 else rows          # skip the warm-up
    avg = [sum(c) / len(r) for c in zip(*r)]
    print("avg over %d: 68000 %.2f video %.2f other %.2f mixer %.2f -> core0 %.2f ms" % (len(r), avg[1], avg[4], avg[0], avg[5], sum(avg)))
