#!/usr/bin/env python3
"""Net connectivity verification — walks the per-net copper graph and
asserts that every net forms a single connected component.

Gap in the prior verification pipeline:
    verify_datasheet_nets.py checks that each pad has the EXPECTED net
    assignment — but it cannot tell whether the copper on that net is
    actually continuous. A pad can be correctly labeled "BAT+" while
    sitting on an isolated copper island that never reaches the rest
    of the BAT+ network.

This script closes that gap by building a graph per net and running
union-find:

    nodes = pads ∪ vias ∪ segments     (all items on the net)
    edges = physical-overlap pairs     (pad↔seg, via↔seg, seg↔seg, …)

A net with more than one connected component is a FAB BUG — one or
more components of the circuit are electrically floating. These bugs
were all present in release v3.3 and undetected by all other scripts.

Historical motivation:
    Session on 2026-04-10 surfaced R5-CRIT-1..6 while investigating
    12 DRC dangling vias after the trace-through-pad hard gate landed
    (commit eff85e6). Without this script the bugs would have shipped
    indefinitely — the pad-net labels were correct, only the copper
    continuity was broken. See hardware-audit-bugs.md §R5 for details.

Coverage and limitations:
    - Zone-filled nets (GND / +3V3 / +5V) are SKIPPED by default because
      we don't parse zone filled_polygons — the zone is assumed to
      stitch everything together. Override with --include-zones.
    - The check is pure-geometric: items that overlap in 2D and share
      at least one copper layer are considered electrically connected.
    - Vias are treated as multi-layer nodes (connect F.Cu ↔ B.Cu at
      their center).
    - Through-hole pads are treated as multi-layer nodes.

Usage:
    python3 scripts/verify_net_connectivity.py
    Exit code 0 = pass, 1 = at least one net fragmented.
"""

import math
import os
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache  # noqa: E402

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

# Nets that have full-board copper pour zones. The zone-fill is assumed
# to stitch every item on these nets together. We skip the connectivity
# check for them to avoid false positives.
#
# If you add a new pour zone in routing.py::_power_zones(), add the net
# name here so the new zone is respected.
ZONE_FILLED_NETS = {"GND", "+3V3", "+5V"}

# ─── Accepted fragmentations (technical debt, not failures) ─────────
#
# These nets are KNOWN to be fragmented for a documented reason and are
# reported at INFO level instead of failing the check. Each entry MUST
# include a justification. Adding an entry without justification will be
# rejected in code review.
#
# The "never silence errors" rule: entries here are NOT silenced — the
# verifier still reports the fragmentation count + reason, just doesn't
# exit non-zero. To bail out on these too, run with --strict.
#
# Format: {net_name: (max_accepted_components, rationale)}
ACCEPTED_FRAGMENTATIONS = {
    # C22 is a series DC-blocking capacitor between ESP32 PDM TX
    # (GPIO21 = I2S_DOUT) and the PAM8403 Class-D audio input (INL, INR).
    # Both pads are labeled "I2S_DOUT" in datasheet_specs.py because there
    # is no separate net name for the AC-coupled PAM input side. The cap
    # body physically separates C22.1 (ESP32 side) from C22.2 (PAM side) —
    # so there are 2 distinct copper components on this "logical" net.
    # Electrically this is the correct DC-block behavior. For a fully clean
    # netlist we should introduce a new net "PAM_IN_AC" for the PAM side,
    # but that is cosmetic and out of scope for R6. TODO v2 PCB respin.
    "I2S_DOUT": (
        2,
        "C22 DC-block cap between ESP32 PDM TX and PAM8403 INL (AC coupling by design; both sides labeled I2S_DOUT, v2 respin should rename PAM side)",
    ),

    # All 12 button nets have a pull-up resistor (R4..R15) and debounce cap
    # (C5..C16) placed in a strip at y=[46,50] with refs aligned at
    # x=43+i*5. The R/C junction is properly wired between R.1 and C.1
    # (same-net 4mm vertical), but that junction was never connected to
    # the main button signal path (which runs the long perimeter route
    # SW → ESP32). Consequence: pull-ups pull up nothing, debounce caps
    # see no signal.
    #
    # Functional impact: firmware enables internal ESP32-S3 pull-ups on
    # all button GPIOs via gpio_config() — see software/main/input.c.
    # Buttons work WITHOUT the external pull-ups; debouncing is done in
    # software. The external R/C strip is a BOM cost without function.
    #
    # Fixing this requires per-button routing from each R.1 pad to the
    # matching button signal line. Each bridge must avoid the 11 other
    # button signals running through the same area + the ESP32 pin
    # approach traces. High-risk refactor for marginal gain when the
    # firmware workaround is already in place. Deferred to v2 PCB respin.
    # Tracked as R5-CRIT-4 in hardware-audit-bugs.md.
    #
    # Accepted components per button: 2 (main signal + isolated R/C junction).
    # BTN_SELECT/START/L/R have additional components from D1 menu diode
    # and SW_BOOT that ARE fixed in R6 — their acceptance count stays at 2
    # after those fixes (only the R/C junction remains isolated).
    # BTN_B, BTN_X, BTN_Y, BTN_R: R7 FIXED by _button_pullup_bridges() in
    # routing.py (commit 259868d). Pull-up/debounce junctions now properly
    # connected to main signal paths — removed from allowlist.
    "BTN_A":      (2, "R8/C9 pull-up/debounce isolated from signal — R5-CRIT-4, firmware internal pullup (R7 remaining: 23mm route through LCD area)"),
    "BTN_UP":     (2, "R4/C5 pull-up/debounce isolated from signal — R5-CRIT-4, firmware internal pullup (R7 remaining: 27mm route, D-pad area)"),
    "BTN_DOWN":   (2, "R5/C6 pull-up/debounce isolated from signal — R5-CRIT-4, firmware internal pullup (R7 remaining: 23mm route, D-pad area)"),
    "BTN_LEFT":   (2, "R6/C7 pull-up/debounce isolated from signal — R5-CRIT-4, firmware internal pullup (R7 remaining: 20mm route, D-pad area)"),
    "BTN_RIGHT":  (2, "R7/C8 pull-up/debounce isolated from signal — R5-CRIT-4, firmware internal pullup (R7 remaining: 20mm route, D-pad area)"),
    "BTN_L":      (2, "R14 DNP per strapping + C15 debounce isolated from signal — R5-CRIT-4, firmware internal pullup (R7 remaining: 22mm route)"),

    # BTN_START has 3 components:
    #   1. Main signal (SW9 → ESP32 GPIO)
    #   2. R12/C13 pull-up junction isolated (R5-CRIT-4)
    #   3. D1.1 menu-combo diode anode isolated (R5-CRIT-6)
    # D1 is the BAT54C dual Schottky that would let SW13 (menu button) trigger
    # BTN_START + BTN_SELECT simultaneously by pulling the common cathode LOW
    # through both anodes. D1.1 was placed but never routed to the main
    # BTN_START network — routing it requires a long cross-board trace from
    # (156.95, 53.60) to the main signal path near ESP32 U1.11 at (88.75, 34.94),
    # threading LCD data bus and SD card area. Deferred to v2 respin.
    # Workaround: press START and SELECT separately to reach the menu.
    "BTN_START":  (3, "R12/C13 junction + D1.1 menu-diode anode isolated — R5-CRIT-4, R5-CRIT-6 menu-combo disabled (v2 respin)"),

    # BTN_SELECT has 4 components:
    #   1. Main signal (SW10 → ESP32 GPIO + SW_PWR.4b/4d shell same-net Fix 1c)
    #   2. R13/C14 pull-up junction isolated (R5-CRIT-4)
    #   3. SW_BOOT.2 isolated (R5-CRIT-5) — boot button is decorative
    #   4. D1.2 menu-combo diode anode isolated (R5-CRIT-6)
    # SW_BOOT and D1.2 both need cross-board bridges that require layout
    # surgery outside R6 scope. Deferred to v2 respin. Workarounds:
    # - USB-JTAG or manual GPIO0 short to enter download mode (not SW_BOOT)
    # - Press START+SELECT manually for menu (not SW13 combo)
    "BTN_SELECT": (4, "R13/C14 junction + SW_BOOT.2 + D1.2 isolated — R5-CRIT-4/5/6, boot button + menu combo need v2 respin"),

    # USB-C receptacle VBUS pins J1.2, J1.9, J1.11 should all be shorted for
    # reversible-plug operation. The PCB escape area south of the J1 footprint
    # is densely packed with USB_CC1/CC2, USB_D+/D-, and GND escapes, leaving
    # no room for B.Cu stubs between the 0.5mm-pitch pads. Via-in-pad is not
    # feasible because the SMD pads are 0.3mm wide — smaller than the 0.46mm
    # JLCPCB minimum via. Current state:
    #   - J1.2 (front VBUS): connected to main network ✓
    #   - J1.9 / J1.11 (back VBUS): isolated
    # Impact: USB-C works in ONE plug orientation only. The reverse orientation
    # would present VBUS on J1.9/J1.11 which won't reach the IP5306 VIN pin.
    # Workaround: insert plug the "correct" way — the device still boots.
    # Tracked as R5-CRIT-9 for v2 PCB respin (requires repositioning the USB-C
    # footprint or using a different escape layout).
    #
    # Components counted:
    #   1: main VBUS network (J1.2, U2.1, U4.5, C17.1 via the R6 fix, plus vias/segs)
    #   2: J1.9 isolated
    #   3: J1.11 isolated
    "VBUS": (3, "J1.9/J1.11 USB-C reverse-orientation VBUS pads isolated — R5-CRIT-9, single-orientation workaround (v2 respin)"),
}

# Nets that intentionally have only one pin or no pins in the PCB
# (typically unused/NC sensors or future-expansion labels). A single-pin
# net is always "connected" (1 component) by definition — no need to
# treat them specially — but a zero-pin or all-segment-no-pad net is
# worth skipping.
EXCLUDED_NET_PREFIXES = ("unconnected-", "Net-(",)

COPPER_LAYERS = ("F.Cu", "B.Cu")

# ─── Component-internal pad bridging ─────────────────────────────────
# Some components short pads electrically inside their body. A PCB doesn't
# need to provide copper between these pads — the component does. Without
# this rule the connectivity verifier would falsely flag nets like MENU_K
# (SW13.1 and SW13.2 are the same mechanical terminal of the tact switch).
#
# Format: {ref_prefix: [(pad_a, pad_b), ...]}
#
# The ref matches by prefix. SW_PWR is explicitly excluded because its
# slide-switch internal bridging depends on position (not static).
INTERNAL_PAD_BRIDGES = {
    # 4-pin tact switches (SW_PUSH_6mm family): pads 1-2 are one terminal,
    # 3-4 the other; pressing shorts {1,2} to {3,4}. With no external copper
    # between same-terminal pads, the switch body still bridges them.
    # Applies to SW1..SW13, SW_RST, SW_BOOT. Does NOT apply to SW_PWR.
    "SW":      [("1", "2"), ("3", "4")],
    "SW_RST":  [("1", "2"), ("3", "4")],
    "SW_BOOT": [("1", "2"), ("3", "4")],
}
# Explicit exclusions: these refs match a bridging prefix but must NOT
# have internal bridging applied.
INTERNAL_BRIDGE_EXCLUDE = {"SW_PWR"}


def _ref_bridges(ref):
    """Return the list of internally-bridged pad pairs for a given ref,
    or [] if none. Uses prefix matching with explicit exclusions."""
    if ref in INTERNAL_BRIDGE_EXCLUDE:
        return []
    # Longest-prefix match wins
    best = None
    best_len = -1
    for prefix, bridges in INTERNAL_PAD_BRIDGES.items():
        if ref.startswith(prefix) and len(prefix) > best_len:
            best = bridges
            best_len = len(prefix)
    return best or []


# ─────────────────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────────────────

def _seg_layers(seg):
    return (seg["layer"],) if seg["layer"] in COPPER_LAYERS else ()


def _pad_layers(pad):
    # Through-hole pads appear on both F.Cu and B.Cu in most footprints.
    # The cache stores the primary layer; infer TH from drill > 0.
    if pad.get("type") in ("thru_hole", "np_thru_hole"):
        return COPPER_LAYERS
    # SMD pads are on a single layer
    return (pad["layer"],) if pad["layer"] in COPPER_LAYERS else ()


def _via_layers(via):
    # Vias in this design always span F.Cu ↔ B.Cu
    return COPPER_LAYERS


def _point_in_rect(px, py, rx, ry, rw, rh, margin=0.0):
    """Point inside axis-aligned rectangle (center, w, h) with margin."""
    return (
        abs(px - rx) <= rw / 2 + margin
        and abs(py - ry) <= rh / 2 + margin
    )


def _rect_rect_overlap(a, b):
    """Two axis-aligned rectangles (cx, cy, w, h) overlap?"""
    return (
        abs(a[0] - b[0]) <= (a[2] + b[2]) / 2
        and abs(a[1] - b[1]) <= (a[3] + b[3]) / 2
    )


def _point_seg_dist(px, py, sx1, sy1, sx2, sy2):
    """Minimum distance from point (px,py) to line segment [(sx1,sy1),(sx2,sy2)]."""
    dx = sx2 - sx1
    dy = sy2 - sy1
    ln2 = dx * dx + dy * dy
    if ln2 < 1e-12:
        return math.hypot(px - sx1, py - sy1)
    t = max(0.0, min(1.0, ((px - sx1) * dx + (py - sy1) * dy) / ln2))
    qx = sx1 + t * dx
    qy = sy1 + t * dy
    return math.hypot(px - qx, py - qy)


def _seg_pad_touches(seg, pad, eps=0.01):
    """Segment touches pad if any point on the segment is within the
    pad bbox (expanded by seg half-width)."""
    if seg["layer"] not in _pad_layers(pad):
        return False
    hw = seg["width"] / 2
    phw = pad["w"] / 2
    phh = pad["h"] / 2
    # Sample endpoints + midpoint + walk
    ln = math.hypot(seg["x2"] - seg["x1"], seg["y2"] - seg["y1"])
    steps = max(2, int(ln / 0.1))
    for i in range(steps + 1):
        t = i / steps
        x = seg["x1"] + t * (seg["x2"] - seg["x1"])
        y = seg["y1"] + t * (seg["y2"] - seg["y1"])
        dx = max(0.0, abs(x - pad["x"]) - phw)
        dy = max(0.0, abs(y - pad["y"]) - phh)
        if math.hypot(dx, dy) <= hw + eps:
            return True
    return False


def _seg_seg_touches(a, b, eps=0.01):
    """Two segments on the same layer touch if the min distance between
    them is ≤ sum of half-widths + eps."""
    if a["layer"] != b["layer"]:
        return False
    hwa = a["width"] / 2
    hwb = b["width"] / 2
    # Min distance segment-to-segment = min of endpoint-to-segment distances
    d = min(
        _point_seg_dist(a["x1"], a["y1"], b["x1"], b["y1"], b["x2"], b["y2"]),
        _point_seg_dist(a["x2"], a["y2"], b["x1"], b["y1"], b["x2"], b["y2"]),
        _point_seg_dist(b["x1"], b["y1"], a["x1"], a["y1"], a["x2"], a["y2"]),
        _point_seg_dist(b["x2"], b["y2"], a["x1"], a["y1"], a["x2"], a["y2"]),
    )
    return d <= hwa + hwb + eps


def _via_pad_touches(via, pad, eps=0.01):
    if not (set(_via_layers(via)) & set(_pad_layers(pad))):
        return False
    # Via-pad distance (circle-rect)
    dx = max(0.0, abs(via["x"] - pad["x"]) - pad["w"] / 2)
    dy = max(0.0, abs(via["y"] - pad["y"]) - pad["h"] / 2)
    return math.hypot(dx, dy) <= via["size"] / 2 + eps


def _via_seg_touches(via, seg, eps=0.01):
    if seg["layer"] not in _via_layers(via):
        return False
    d = _point_seg_dist(
        via["x"], via["y"],
        seg["x1"], seg["y1"], seg["x2"], seg["y2"],
    )
    return d <= via["size"] / 2 + seg["width"] / 2 + eps


def _via_via_touches(a, b, eps=0.01):
    return (
        math.hypot(a["x"] - b["x"], a["y"] - b["y"])
        <= (a["size"] + b["size"]) / 2 + eps
    )


def _pad_pad_touches(a, b, eps=0.01):
    if not (set(_pad_layers(a)) & set(_pad_layers(b))):
        return False
    dx = max(0.0, abs(a["x"] - b["x"]) - (a["w"] + b["w"]) / 2)
    dy = max(0.0, abs(a["y"] - b["y"]) - (a["h"] + b["h"]) / 2)
    return math.hypot(dx, dy) <= eps


# ─────────────────────────────────────────────────────────────────────
# Union-Find
# ─────────────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


# ─────────────────────────────────────────────────────────────────────
# Per-net connectivity check
# ─────────────────────────────────────────────────────────────────────

def _describe_item(kind, item):
    if kind == "pad":
        return f"pad {item.get('ref')}.{item.get('num')}@({item['x']:.2f},{item['y']:.2f})"
    if kind == "via":
        return f"via@({item['x']:.2f},{item['y']:.2f})"
    if kind == "seg":
        return (
            f"{item['layer']}({item['x1']:.2f},{item['y1']:.2f})-"
            f"({item['x2']:.2f},{item['y2']:.2f})"
        )
    return "?"


def analyze_net(net_name, pads, vias, segs):
    """Return a list of connected-component descriptions. Each component
    is a list of (kind, item) tuples."""
    items = [("pad", p) for p in pads] + [("via", v) for v in vias] + [("seg", s) for s in segs]
    n = len(items)
    if n <= 1:
        return [items] if items else []

    uf = UnionFind(n)

    # ── Physical overlap edges ──────────────────────────────────
    for i in range(n):
        ki, ii = items[i]
        for j in range(i + 1, n):
            kj, ij = items[j]
            connected = False
            if ki == "pad" and kj == "pad":
                connected = _pad_pad_touches(ii, ij)
            elif (ki == "pad" and kj == "seg") or (ki == "seg" and kj == "pad"):
                seg, pad = (ij, ii) if ki == "pad" else (ii, ij)
                connected = _seg_pad_touches(seg, pad)
            elif (ki == "pad" and kj == "via") or (ki == "via" and kj == "pad"):
                via, pad = (ij, ii) if ki == "pad" else (ii, ij)
                connected = _via_pad_touches(via, pad)
            elif ki == "seg" and kj == "seg":
                connected = _seg_seg_touches(ii, ij)
            elif (ki == "seg" and kj == "via") or (ki == "via" and kj == "seg"):
                via, seg = (ij, ii) if ki == "seg" else (ii, ij)
                connected = _via_seg_touches(via, seg)
            elif ki == "via" and kj == "via":
                connected = _via_via_touches(ii, ij)
            if connected:
                uf.union(i, j)

    # ── Internal-bridge edges (component body shorts pads) ──────
    # Index pads by (ref, num) for fast lookup
    pad_index = {}
    for idx, (kind, item) in enumerate(items):
        if kind == "pad":
            pad_index[(item.get("ref"), str(item.get("num")))] = idx
    # For each pad in the net, if its ref has internal bridges, link pads
    for idx, (kind, item) in enumerate(items):
        if kind != "pad":
            continue
        ref = item.get("ref")
        num = str(item.get("num"))
        for (pa, pb) in _ref_bridges(ref):
            if num == pa:
                other_idx = pad_index.get((ref, pb))
                if other_idx is not None:
                    uf.union(idx, other_idx)
            elif num == pb:
                other_idx = pad_index.get((ref, pa))
                if other_idx is not None:
                    uf.union(idx, other_idx)

    # Collect components
    comps = defaultdict(list)
    for idx in range(n):
        root = uf.find(idx)
        comps[root].append(items[idx])
    return list(comps.values())


def run_check(cache, include_zones=False):
    """Run the connectivity check on every net in the cache."""
    net_map = {n["id"]: n["name"] for n in cache["nets"]}

    # Bucket items by net id
    by_net_pads = defaultdict(list)
    by_net_vias = defaultdict(list)
    by_net_segs = defaultdict(list)
    for p in cache["pads"]:
        if p["net"]:
            by_net_pads[p["net"]].append(p)
    for v in cache["vias"]:
        if v["net"]:
            by_net_vias[v["net"]].append(v)
    for s in cache["segments"]:
        if s["net"]:
            by_net_segs[s["net"]].append(s)

    results = []  # list of (net_name, components)
    for net_id, name in sorted(net_map.items(), key=lambda kv: kv[1]):
        if any(name.startswith(pref) for pref in EXCLUDED_NET_PREFIXES):
            continue
        if not include_zones and name in ZONE_FILLED_NETS:
            continue
        pads = by_net_pads.get(net_id, [])
        vias = by_net_vias.get(net_id, [])
        segs = by_net_segs.get(net_id, [])
        if not pads and not vias and not segs:
            continue
        comps = analyze_net(name, pads, vias, segs)
        if len(comps) > 1:
            results.append((name, comps))
    return results


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--include-zones",
        action="store_true",
        help="Also check GND/+3V3/+5V nets (may false-positive if zones aren't parsed)",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Fail on ACCEPTED_FRAGMENTATIONS as well (bypass technical-debt allowlist)",
    )
    args = ap.parse_args()

    cache = load_cache(PCB_FILE)

    print()
    print("=" * 62)
    print("Per-net connectivity check (union-find on copper graph)")
    print("=" * 62)
    print()

    net_count = len(cache["nets"])
    skipped = 0 if args.include_zones else len(ZONE_FILLED_NETS)
    print(f"  Nets in PCB          : {net_count}")
    print(f"  Zone-filled (skipped): {skipped} ({', '.join(sorted(ZONE_FILLED_NETS))})")
    print(f"  Pads checked         : {len(cache['pads'])}")
    print(f"  Vias checked         : {len(cache['vias'])}")
    print(f"  Segments checked     : {len(cache['segments'])}")
    print()

    fragmented = run_check(cache, include_zones=args.include_zones)

    # Partition into failures vs. accepted technical debt
    failures = []
    accepted = []
    for net_name, comps in fragmented:
        if not args.strict and net_name in ACCEPTED_FRAGMENTATIONS:
            allowed, rationale = ACCEPTED_FRAGMENTATIONS[net_name]
            if len(comps) <= allowed:
                accepted.append((net_name, comps, rationale))
                continue
        failures.append((net_name, comps))

    if accepted:
        print(
            f"  INFO  {len(accepted)} net(s) have ACCEPTED fragmentation "
            f"(documented technical debt, not a failure):"
        )
        for net_name, comps, rationale in accepted:
            print(f"    {net_name}: {len(comps)} components — {rationale}")
        print()

    if not failures:
        print("  PASS  Every checked net is a single connected copper component.")
        if accepted:
            print(
                f"        ({len(accepted)} net(s) accepted as documented tech debt; "
                f"re-run with --strict to include them.)"
            )
        print()
        print("=" * 62)
        pass_count = sum(1 for _ in cache["nets"]) - len(accepted) - skipped
        print(f"Results: PASS ({len(accepted)} accepted, 0 failed)")
        print("=" * 62)
        return 0

    print(
        f"  FAIL  {len(failures)} net(s) have fragmented copper "
        f"(multiple disconnected components):"
    )
    print()
    for net_name, comps in failures:
        print(f"  ── {net_name} — {len(comps)} components ──")
        for ci, comp in enumerate(comps, 1):
            print(f"    Component {ci}: {len(comp)} item(s)")
            # Sort items to show pads first (more meaningful)
            comp_sorted = sorted(comp, key=lambda it: (0 if it[0] == "pad" else 1 if it[0] == "via" else 2))
            for kind, item in comp_sorted[:6]:
                print(f"      {_describe_item(kind, item)}")
            if len(comp) > 6:
                print(f"      ... and {len(comp) - 6} more")
        print()

    print("=" * 62)
    print(f"Results: {len(failures)} fragmented net(s), {len(accepted)} accepted")
    print("=" * 62)
    print()
    print("REMEDIATION:")
    print("  Each fragmented net has components that should be electrically")
    print("  connected but have no copper path joining them. Most commonly:")
    print("  - A dangling via was placed expecting a zone fill that doesn't exist")
    print("  - A route was partially deleted during refactoring")
    print("  - Pull-up/debounce passives placed but not wired into the signal line")
    print()
    print("  Fix by adding the missing traces in scripts/generate_pcb/routing.py,")
    print("  then re-run this script until it reports 0 fragmented nets.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
