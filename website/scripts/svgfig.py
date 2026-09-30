"""Shared drawing kit for the hand-placed SVG figures of the docs.

One palette, one font stack, the same boxes / groups / arrows / badges /
code panels everywhere, so every figure on the site reads as one family.
Each figure draws its own white card, so it stays readable in both site
themes. Figure scripts: gen_dynarec_svgs.py, gen_doc_svgs.py.
"""
import os
from html import escape

FONT = "Inter, 'Segoe UI', system-ui, -apple-system, Roboto, sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace"

# (stroke/accent, fill, text)
C = {
    "blue":   ("#2563eb", "#eff6ff", "#1e3a8a"),
    "green":  ("#16a34a", "#f0fdf4", "#14532d"),
    "orange": ("#ea580c", "#fff7ed", "#7c2d12"),
    "purple": ("#7c3aed", "#f5f3ff", "#4c1d95"),
    "teal":   ("#0d9488", "#f0fdfa", "#134e4a"),
    "red":    ("#dc2626", "#fef2f2", "#7f1d1d"),
    "gray":   ("#64748b", "#f8fafc", "#1e293b"),
    "amber":  ("#d97706", "#fffbeb", "#78350f"),
}
INK = "#0f172a"
MUTED = "#475569"
LINE = "#94a3b8"


class Svg:
    out_dir = None  # set by each figure script

    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    # ---- primitives -------------------------------------------------------
    def text(self, x, y, s, size=13, weight=400, color=INK, anchor="middle", font=FONT, italic=False):
        st = ' font-style="italic"' if italic else ""
        sp = ' xml:space="preserve"' if font == MONO else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
                 f'fill="{color}" text-anchor="{anchor}"{st}{sp}>{escape(s)}</text>')

    def lines(self, x, y, rows, size=12, color=INK, anchor="middle", gap=None, font=FONT, weight=400):
        gap = gap or size + 5
        for i, r in enumerate(rows):
            mono = r.startswith("`") and r.endswith("`")
            self.text(x, y + i * gap, r.strip("`") if mono else r, size=size - (1 if mono else 0), color=color,
                      anchor=anchor, font=MONO if mono else font, weight=weight)

    def box(self, x, y, w, h, title=None, rows=(), color="gray", r=10, title_size=14, row_size=12,
            fill=None, dashed=False, align="middle", shadow=True):
        stroke, bg, tx = C[color]
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        flt = ' filter="url(#sh)"' if shadow else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or bg}" '
                 f'stroke="{stroke}" stroke-width="1.6"{dash}{flt}/>')
        n = (1 if title else 0) + len(rows)
        gap = row_size + 6
        total = (title_size + 6 if title else 0) + len(rows) * gap
        cy = y + (h - total) / 2 + title_size - 2
        ax = x + w / 2 if align == "middle" else x + 14
        if title:
            self.text(ax, cy, title, size=title_size, weight=650, color=tx, anchor=align if align != "left" else "start")
            cy += title_size + 6
        for i, r_ in enumerate(rows):
            mono = r_.startswith("`") and r_.endswith("`")
            self.text(ax, cy + i * gap, r_.strip("`") if mono else r_, size=row_size - (1 if mono else 0),
                      color=tx if not mono else INK, font=MONO if mono else FONT,
                      anchor=align if align != "left" else "start")

    def group(self, x, y, w, h, label, color="gray", badge=None):
        stroke, bg, tx = C[color]
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{bg}" fill-opacity="0.55" '
                 f'stroke="{stroke}" stroke-width="1.4" stroke-dasharray="2 0"/>')
        self.text(x + 14, y + 22, label, size=13, weight=700, color=stroke, anchor="start")
        if badge:
            bw = 12 + 7.2 * len(badge)
            self.add(f'<rect x="{x + w - bw - 12}" y="{y + 9}" width="{bw}" height="20" rx="10" fill="{stroke}"/>')
            self.text(x + w - bw / 2 - 12, y + 23, badge, size=11, weight=700, color="#ffffff")

    def arrow(self, pts, label=None, color=LINE, dashed=False, lx=None, ly=None, width=1.8, label_color=MUTED,
              curve=False, head=True, both=False):
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        if curve and len(pts) == 3:
            (x1, y1), (cx, cy), (x2, y2) = pts
            d = f"M{x1},{y1} Q{cx},{cy} {x2},{y2}"
        else:
            d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        mk = ' marker-end="url(#ah)"' if head else ""
        if both:
            mk += ' marker-start="url(#ah)"'
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash}{mk}/>')
        if label:
            if lx is None:
                a, b = pts[len(pts) // 2 - 1], pts[len(pts) // 2]
                lx, ly = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            rows = label.split("\n")
            wmax = max(len(r) for r in rows) * 6.6 + 12
            hh = len(rows) * 15 + 6
            self.add(f'<rect x="{lx - wmax / 2}" y="{ly - hh / 2 - 1}" width="{wmax}" height="{hh}" rx="6" '
                     f'fill="#ffffff" fill-opacity="0.95"/>')
            for i, r_ in enumerate(rows):
                self.text(lx, ly - hh / 2 + 15 + i * 15, r_, size=11.5, color=label_color)

    def badge(self, x, y, s, color="gray"):
        stroke = C[color][0]
        bw = 12 + 6.8 * len(s)
        self.add(f'<rect x="{x}" y="{y}" width="{bw}" height="20" rx="10" fill="{stroke}"/>')
        self.text(x + bw / 2, y + 14, s, size=11, weight=700, color="#ffffff")

    def chip_w(self, s, size=11.5):
        return len(s) * size * 0.6 + 18

    def chip(self, x, y, s, color="gray", size=11.5, h=26):
        """A mono pill: one command / skill name."""
        stroke, bg, tx = C[color]
        w = self.chip_w(s, size)
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="#ffffff" '
                 f'stroke="{stroke}" stroke-width="1.3"/>')
        self.text(x + w / 2, y + h / 2 + size * 0.36, s, size=size, color=tx, font=MONO)
        return w

    def chips(self, x, y, w, items, color="gray", gap=8, h=26):
        """Flow chips left to right inside width w; returns the height used."""
        cx, cy = x, y
        for it in items:
            cw = self.chip_w(it)
            if cx > x and cx + cw > x + w:
                cx, cy = x, cy + h + gap
            self.chip(cx, cy, it, color, h=h)
            cx += cw + gap
        return cy + h - y

    def code(self, x, y, w, rows, title=None):
        h = 18 * len(rows) + (34 if title else 18)
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#0f172a" filter="url(#sh)"/>')
        yy = y + 22
        if title:
            self.text(x + 14, yy, title, size=11.5, weight=600, color="#94a3b8", anchor="start")
            yy += 18
        for r_ in rows:
            code, _, comment = r_.partition(";")
            self.text(x + 14, yy, code.rstrip(), size=12.5, color="#e2e8f0", anchor="start", font=MONO)
            if comment:
                self.text(x + 14 + 7.6 * 24, yy, ";" + comment, size=12.5, color="#7dd3fc", anchor="start", font=MONO)
            yy += 18
        return h

    def save(self, name):
        assert self.out_dir, "set Svg.out_dir before saving"
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
                f'height="{self.h}" role="img" aria-label="{escape(self.title)}">'
                f'<title>{escape(self.title)}</title>'
                '<defs>'
                '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker>'
                '<filter id="sh" x="-5%" y="-5%" width="110%" height="120%">'
                '<feDropShadow dx="0" dy="1.5" stdDeviation="1.6" flood-color="#0f172a" flood-opacity="0.12"/>'
                '</filter></defs>'
                f'<rect x="0" y="0" width="{self.w}" height="{self.h}" rx="16" fill="#ffffff"/>')
        with open(os.path.join(self.out_dir, name), "w") as f:
            f.write(head + "".join(self.parts) + "</svg>\n")
