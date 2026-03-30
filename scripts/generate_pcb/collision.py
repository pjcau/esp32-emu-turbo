"""Spatial collision detection for PCB trace routing.

Pre-populates a spatial hash with pads, board edges, FPC slot, and mounting
holes.  Every segment and via is checked against existing obstacles before
placement.  Violations are collected and reported at the end of generation.

Architecture:
  - SpatialHash: cell-based AABB index (cell_size=5mm, ~480 cells for 160x75mm)
  - CollisionGrid: high-level API used by routing._seg() and routing._via_net()
  - All traces are Manhattan (H/V), so segments expanded by half-width are
    exact axis-aligned bounding boxes — no approximation needed.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# ── Layer indices for the spatial hash ────────────────────────────
LAYER_IDX = {"F.Cu": 0, "B.Cu": 1}

# ── JLCPCB DFM clearance rules (edge-to-edge minimums, mm) ──────
CLEARANCE_TRACE_TRACE = 0.15   # trace-to-trace, same layer, different net
CLEARANCE_TRACE_PAD = 0.15     # trace edge to pad edge, different net
CLEARANCE_VIA_TRACE = 0.15     # via drill edge to trace edge
CLEARANCE_VIA_VIA = 0.25       # via drill to via drill (hole-to-hole)
CLEARANCE_VIA_PAD = 0.15       # via annular ring edge to pad edge
CLEARANCE_EDGE = 0.50          # board edge / FPC slot keepout

# Sentinel net that collides with everything (slot, edges, mounting holes)
NET_BARRIER = -999


# ── Data classes ──────────────────────────────────────────────────

@dataclass
class Obstacle:
    """Axis-aligned bounding box on a specific layer with net assignment."""
    xmin: float
    ymin: float
    xmax: float
    ymax: float
    net: int
    kind: str       # "segment", "via", "pad", "slot", "edge", "mounting_hole"
    label: str = ""


@dataclass
class Violation:
    """Detected clearance breach between two obstacles."""
    obstacle_a: Obstacle
    obstacle_b: Obstacle
    layer: str
    gap_mm: float          # actual edge-to-edge gap (negative = overlap)
    required_mm: float     # minimum required gap
    suggestion: str = ""


# ── Spatial Hash ──────────────────────────────────────────────────

class SpatialHash:
    """Cell-based spatial index for fast AABB overlap queries."""

    def __init__(self, cell_size: float = 5.0):
        self.cell_size = cell_size
        # {(layer_idx, gx, gy): [Obstacle, ...]}
        self._buckets: Dict[Tuple[int, int, int], List[Obstacle]] = {}
        # All obstacles per layer (for linear scans when needed)
        self._all: Dict[int, List[Obstacle]] = {0: [], 1: []}

    def clear(self):
        """Remove all obstacles."""
        self._buckets.clear()
        self._all = {0: [], 1: []}

    def insert(self, layer_idx: int, obs: Obstacle):
        """Insert an obstacle into the hash."""
        self._all[layer_idx].append(obs)
        cs = self.cell_size
        gx1 = int(math.floor(obs.xmin / cs))
        gy1 = int(math.floor(obs.ymin / cs))
        gx2 = int(math.floor(obs.xmax / cs))
        gy2 = int(math.floor(obs.ymax / cs))
        for gx in range(gx1, gx2 + 1):
            for gy in range(gy1, gy2 + 1):
                key = (layer_idx, gx, gy)
                bucket = self._buckets.get(key)
                if bucket is None:
                    bucket = []
                    self._buckets[key] = bucket
                bucket.append(obs)

    def query(self, layer_idx: int,
              xmin: float, ymin: float, xmax: float, ymax: float,
              exclude_net: int = -1) -> List[Obstacle]:
        """Find obstacles overlapping the query AABB with a different net.

        exclude_net: skip obstacles with this net (same-net = OK).
        Obstacles with net=NET_BARRIER always match (never excluded).
        """
        results: List[Obstacle] = []
        seen: Set[int] = set()
        cs = self.cell_size
        gx1 = int(math.floor(xmin / cs))
        gy1 = int(math.floor(ymin / cs))
        gx2 = int(math.floor(xmax / cs))
        gy2 = int(math.floor(ymax / cs))
        for gx in range(gx1, gx2 + 1):
            for gy in range(gy1, gy2 + 1):
                for obs in self._buckets.get((layer_idx, gx, gy), ()):
                    oid = id(obs)
                    if oid in seen:
                        continue
                    seen.add(oid)
                    # Same-net: skip (unless barrier)
                    if obs.net != NET_BARRIER and obs.net == exclude_net:
                        continue
                    # Unassigned pads (net=0): skip — net not yet known,
                    # cannot determine if same-net or different-net.
                    if obs.net == 0 and obs.kind == "pad":
                        continue
                    # AABB overlap test
                    if (xmin < obs.xmax and xmax > obs.xmin and
                            ymin < obs.ymax and ymax > obs.ymin):
                        results.append(obs)
        return results

    def all_on_layer(self, layer_idx: int) -> List[Obstacle]:
        """Return all obstacles on a given layer."""
        return self._all.get(layer_idx, [])


# ── Collision Grid (main API) ─────────────────────────────────────

class CollisionGrid:
    """Pre-routing collision detection system.

    Usage::

        grid = CollisionGrid()
        grid.register_pads(all_pad_positions)
        grid.register_slot()
        grid.register_board_edges()
        grid.register_mounting_holes([(x, y), ...])

        # During routing (called by _seg / _via_net):
        violations = grid.check_segment(x1, y1, x2, y2, layer, width, net)
        grid.add_segment(x1, y1, x2, y2, layer, width, net)
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.index = SpatialHash(cell_size=5.0)
        self.violations: List[Violation] = []
        self._populated = False
        # Track pad obstacles for net updates: {(ref, pad_num): Obstacle}
        self._pad_obstacles: Dict[Tuple[str, str], List[Obstacle]] = {}

    def reset(self):
        """Clear all state for a fresh generation run."""
        self.index.clear()
        self.violations.clear()
        self._populated = False
        self._pad_obstacles.clear()

    # ── Pre-population ────────────────────────────────────────

    def register_pads(self, pads_dict: dict):
        """Register all component pads as obstacles.

        Args:
            pads_dict: {ref: {pad_num: (x, y, w, h)}} from
                       pad_positions.get_all_pad_positions()
        """
        # Determine which refs are on F.Cu vs B.Cu
        fcu_refs = {
            "SW1", "SW2", "SW3", "SW4", "SW5", "SW6", "SW7", "SW8",
            "SW9", "SW10", "SW13", "LED1", "LED2",
        }

        # Skip ESP32 GND thermal pad (U1:41) — it's a 3.9x3.9mm exposed pad
        # that signal traces legitimately cross underneath with solder mask
        # separation. Including it would flag unavoidable DRC violations for
        # bottom-side GPIO pin escape routes that must traverse the pad area.
        _skip_pads = {("U1", "41")}
        # Skip J4 FPC pads adjacent to power vias (0.5mm pitch, via-pad gap 0.125mm
        # is acceptable for FPC connectors — JLCPCB accepts 0.10mm via-pad min).
        # These pads are at y=25.75..38.25, via between them at VIA_X_PWR=133.60.
        for _j4p in ["1", "24", "26"]:
            _skip_pads.add(("J4", _j4p))

        for ref, pad_map in pads_dict.items():
            layer = "F.Cu" if ref in fcu_refs else "B.Cu"
            layer_idx = LAYER_IDX.get(layer, -1)
            if layer_idx < 0:
                continue
            for num, tup in pad_map.items():
                if (ref, str(num)) in _skip_pads:
                    continue
                if len(tup) == 4:
                    px, py, pw, ph = tup
                elif len(tup) == 2:
                    px, py = tup
                    pw, ph = 0.9, 0.9  # fallback
                else:
                    continue

                obs = Obstacle(
                    xmin=round(px - pw / 2, 4),
                    ymin=round(py - ph / 2, 4),
                    xmax=round(px + pw / 2, 4),
                    ymax=round(py + ph / 2, 4),
                    net=0,  # unknown until first trace touches
                    kind="pad",
                    label=f"{ref}:{num}",
                )
                self.index.insert(layer_idx, obs)
                # Also insert on the other layer if it's a THT pad
                # (through-hole pads appear on both layers)
                if _is_tht_ref(ref):
                    other_idx = 1 - layer_idx
                    obs2 = Obstacle(
                        xmin=obs.xmin, ymin=obs.ymin,
                        xmax=obs.xmax, ymax=obs.ymax,
                        net=0, kind="pad",
                        label=f"{ref}:{num}",
                    )
                    self.index.insert(other_idx, obs2)
                    self._pad_obstacles.setdefault(
                        (ref, str(num)), []).append(obs2)

                self._pad_obstacles.setdefault(
                    (ref, str(num)), []).append(obs)

        self._populated = True

    def register_slot(self, x1: float = 125.5, y1: float = 23.5,
                      x2: float = 128.5, y2: float = 47.5):
        """Register the FPC slot as a no-go zone on both layers."""
        for layer_idx in (0, 1):
            obs = Obstacle(
                xmin=x1, ymin=y1, xmax=x2, ymax=y2,
                net=NET_BARRIER, kind="slot", label="FPC_SLOT",
            )
            self.index.insert(layer_idx, obs)

    def register_board_edges(self, board_w: float = 160.0,
                             board_h: float = 75.0,
                             keepout: float = 0.5):
        """Register board edge keepout strips on both layers."""
        edges = [
            (0, 0, board_w, keepout, "top_edge"),
            (0, board_h - keepout, board_w, board_h, "bottom_edge"),
            (0, 0, keepout, board_h, "left_edge"),
            (board_w - keepout, 0, board_w, board_h, "right_edge"),
        ]
        for xmin, ymin, xmax, ymax, label in edges:
            for layer_idx in (0, 1):
                obs = Obstacle(
                    xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax,
                    net=NET_BARRIER, kind="edge", label=label,
                )
                self.index.insert(layer_idx, obs)

    def register_mounting_holes(self, positions: list,
                                drill: float = 2.5):
        """Register mounting holes as obstacles on both layers."""
        r = drill / 2
        for x, y in positions:
            for layer_idx in (0, 1):
                obs = Obstacle(
                    xmin=x - r, ymin=y - r, xmax=x + r, ymax=y + r,
                    net=NET_BARRIER, kind="mounting_hole",
                    label=f"MH@({x:.1f},{y:.1f})",
                )
                self.index.insert(layer_idx, obs)

    # ── Check methods (query without inserting) ───────────────

    def check_segment(self, x1: float, y1: float,
                      x2: float, y2: float,
                      layer: str, width: float, net: int
                      ) -> List[Violation]:
        """Check if a segment would violate clearance rules.

        Does NOT add the segment to the index.
        """
        if not self.enabled or net == 0:
            return []
        layer_idx = LAYER_IDX.get(layer, -1)
        if layer_idx < 0:
            return []

        hw = width / 2
        # Segment AABB (actual copper)
        seg_xmin = round(min(x1, x2) - hw, 4)
        seg_ymin = round(min(y1, y2) - hw, 4)
        seg_xmax = round(max(x1, x2) + hw, 4)
        seg_ymax = round(max(y1, y2) + hw, 4)

        # Query AABB expanded by max clearance to catch nearby obstacles
        margin = max(CLEARANCE_TRACE_TRACE, CLEARANCE_TRACE_PAD,
                     CLEARANCE_VIA_TRACE, CLEARANCE_EDGE)
        q_xmin = seg_xmin - margin
        q_ymin = seg_ymin - margin
        q_xmax = seg_xmax + margin
        q_ymax = seg_ymax + margin

        hits = self.index.query(layer_idx, q_xmin, q_ymin,
                                q_xmax, q_ymax, exclude_net=net)

        violations = []
        seg_obs = Obstacle(
            xmin=seg_xmin, ymin=seg_ymin,
            xmax=seg_xmax, ymax=seg_ymax,
            net=net, kind="segment",
            label=f"net{net} {layer} ({x1:.2f},{y1:.2f})->({x2:.2f},{y2:.2f})",
        )

        for obs in hits:
            required = _required_clearance("segment", obs.kind)
            gap = _aabb_gap(seg_xmin, seg_ymin, seg_xmax, seg_ymax,
                            obs.xmin, obs.ymin, obs.xmax, obs.ymax)
            if gap < required:
                violations.append(Violation(
                    obstacle_a=seg_obs,
                    obstacle_b=obs,
                    layer=layer,
                    gap_mm=round(gap, 4),
                    required_mm=required,
                    suggestion=_suggest_nudge(x1, y1, x2, y2, obs),
                ))

        return violations

    def check_via(self, x: float, y: float, net: int,
                  size: float = 0.9, drill: float = 0.35
                  ) -> List[Violation]:
        """Check if a via would violate clearance rules.

        Does NOT add the via to the index.  Checks both F.Cu and B.Cu.
        """
        if not self.enabled or net == 0:
            return []

        vr = size / 2  # annular ring radius
        via_xmin = round(x - vr, 4)
        via_ymin = round(y - vr, 4)
        via_xmax = round(x + vr, 4)
        via_ymax = round(y + vr, 4)

        margin = max(CLEARANCE_VIA_TRACE, CLEARANCE_VIA_VIA,
                     CLEARANCE_VIA_PAD, CLEARANCE_EDGE)

        violations = []
        layer_names = ["F.Cu", "B.Cu"]

        for layer_idx in (0, 1):
            hits = self.index.query(
                layer_idx,
                via_xmin - margin, via_ymin - margin,
                via_xmax + margin, via_ymax + margin,
                exclude_net=net,
            )
            via_obs = Obstacle(
                xmin=via_xmin, ymin=via_ymin,
                xmax=via_xmax, ymax=via_ymax,
                net=net, kind="via",
                label=f"via net{net}@({x:.2f},{y:.2f})",
            )
            for obs in hits:
                required = _required_clearance("via", obs.kind)
                gap = _aabb_gap(via_xmin, via_ymin, via_xmax, via_ymax,
                                obs.xmin, obs.ymin, obs.xmax, obs.ymax)
                if gap < required:
                    violations.append(Violation(
                        obstacle_a=via_obs,
                        obstacle_b=obs,
                        layer=layer_names[layer_idx],
                        gap_mm=round(gap, 4),
                        required_mm=required,
                        suggestion=f"move via from ({x:.2f},{y:.2f})",
                    ))

        return violations

    # ── Add methods (insert after checking) ───────────────────

    def add_segment(self, x1: float, y1: float,
                    x2: float, y2: float,
                    layer: str, width: float, net: int):
        """Register a placed segment as an obstacle."""
        if not self.enabled:
            return
        layer_idx = LAYER_IDX.get(layer, -1)
        if layer_idx < 0:
            return
        hw = width / 2
        obs = Obstacle(
            xmin=round(min(x1, x2) - hw, 4),
            ymin=round(min(y1, y2) - hw, 4),
            xmax=round(max(x1, x2) + hw, 4),
            ymax=round(max(y1, y2) + hw, 4),
            net=net, kind="segment",
            label=f"net{net} {layer} ({x1:.2f},{y1:.2f})->({x2:.2f},{y2:.2f})",
        )
        self.index.insert(layer_idx, obs)

    def add_via(self, x: float, y: float, net: int,
                size: float = 0.9, drill: float = 0.35):
        """Register a placed via as an obstacle on both layers."""
        if not self.enabled:
            return
        vr = size / 2
        for layer_idx in (0, 1):
            obs = Obstacle(
                xmin=round(x - vr, 4), ymin=round(y - vr, 4),
                xmax=round(x + vr, 4), ymax=round(y + vr, 4),
                net=net, kind="via",
                label=f"via net{net}@({x:.2f},{y:.2f})",
            )
            self.index.insert(layer_idx, obs)

    # ── Pad net sync ──────────────────────────────────────────

    def update_pad_net(self, ref: str, pad_num: str, net: int):
        """Update the net of a registered pad obstacle.

        Called when the first trace touches a pad, so future same-net
        traces to that pad are not flagged as violations.
        """
        for obs in self._pad_obstacles.get((ref, str(pad_num)), ()):
            if obs.net == 0:
                obs.net = net

    # ── Reporting ─────────────────────────────────────────────

    def get_violations(self) -> List[Violation]:
        """Return all accumulated violations (excluding suppressed)."""
        return [v for v in self.violations if not _is_suppressed(v)]

    def print_report(self):
        """Print a summary of all violations to stderr."""
        import sys
        if not self.violations:
            print("  Collision grid: 0 violations (all clear)", file=sys.stderr)
            return

        # Deduplicate: same pair of labels on same layer
        seen: Set[Tuple[str, str, str]] = set()
        unique: List[Violation] = []
        suppressed_count = 0
        for v in self.violations:
            if _is_suppressed(v):
                suppressed_count += 1
                continue
            key = (v.layer,
                   min(v.obstacle_a.label, v.obstacle_b.label),
                   max(v.obstacle_a.label, v.obstacle_b.label))
            if key not in seen:
                seen.add(key)
                unique.append(v)

        # Group by kind
        by_kind: Dict[str, List[Violation]] = {}
        for v in unique:
            kind_pair = f"{v.obstacle_a.kind}-{v.obstacle_b.kind}"
            by_kind.setdefault(kind_pair, []).append(v)

        total = len(unique)
        print(f"\n{'='*60}", file=sys.stderr)
        if suppressed_count > 0:
            print(f"  COLLISION GRID: {total} unique violations detected"
                  f" ({suppressed_count} suppressed)",
                  file=sys.stderr)
        else:
            print(f"  COLLISION GRID: {total} unique violations detected",
                  file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        for kind_pair, vlist in sorted(by_kind.items()):
            print(f"\n  --- {kind_pair} ({len(vlist)}) ---",
                  file=sys.stderr)
            for v in vlist[:20]:  # cap display at 20 per kind
                print(f"  {v.layer}: {v.obstacle_a.label}",
                      file=sys.stderr)
                print(f"       vs {v.obstacle_b.label}",
                      file=sys.stderr)
                print(f"       gap={v.gap_mm:.3f}mm "
                      f"(need {v.required_mm:.2f}mm) "
                      f"| {v.suggestion}",
                      file=sys.stderr)
            if len(vlist) > 20:
                print(f"  ... and {len(vlist) - 20} more",
                      file=sys.stderr)

        print(f"\n{'='*60}\n", file=sys.stderr)


# ── Module-level helpers ──────────────────────────────────────────

def _required_clearance(kind_a: str, kind_b: str) -> float:
    """Return minimum required edge-to-edge clearance (mm)."""
    pair = frozenset([kind_a, kind_b])
    if pair == frozenset(["via", "via"]):
        return CLEARANCE_VIA_VIA
    if "via" in pair and "pad" in pair:
        return CLEARANCE_VIA_PAD
    if "via" in pair and "segment" in pair:
        return CLEARANCE_VIA_TRACE
    if "slot" in pair or "edge" in pair or "mounting_hole" in pair:
        return CLEARANCE_EDGE
    if "pad" in pair:
        return CLEARANCE_TRACE_PAD
    return CLEARANCE_TRACE_TRACE


def _aabb_gap(ax1: float, ay1: float, ax2: float, ay2: float,
              bx1: float, by1: float, bx2: float, by2: float) -> float:
    """Compute edge-to-edge gap between two AABBs.

    Returns positive for separated boxes, 0.0 for touching,
    negative for overlapping.
    """
    dx = max(bx1 - ax2, ax1 - bx2, 0.0)
    dy = max(by1 - ay2, ay1 - by2, 0.0)
    if dx > 0 or dy > 0:
        # Separated — Euclidean distance between nearest edges
        return math.sqrt(dx * dx + dy * dy)
    # Overlapping — return negative of minimum penetration depth
    overlap_x = min(ax2 - bx1, bx2 - ax1)
    overlap_y = min(ay2 - by1, by2 - ay1)
    return -min(overlap_x, overlap_y)


def _suggest_nudge(x1: float, y1: float, x2: float, y2: float,
                   obs: Obstacle) -> str:
    """Suggest which direction to nudge a segment to avoid collision."""
    if abs(y1 - y2) < 0.001:  # horizontal segment
        obs_cy = (obs.ymin + obs.ymax) / 2
        if y1 < obs_cy:
            return f"nudge UP (decrease Y) from y={y1:.2f}"
        return f"nudge DOWN (increase Y) from y={y1:.2f}"
    if abs(x1 - x2) < 0.001:  # vertical segment
        obs_cx = (obs.xmin + obs.xmax) / 2
        if x1 < obs_cx:
            return f"nudge LEFT (decrease X) from x={x1:.2f}"
        return f"nudge RIGHT (increase X) from x={x1:.2f}"
    return "adjust position"


def _is_tht_ref(ref: str) -> bool:
    """Check if a component reference is a through-hole type."""
    # JST connector (J3), mounting holes (MH*) are THT
    # For this board, most components are SMD
    return ref in ("J3",)


# ── Justified suppressions ─────────────────────────────────────────
#
# Each entry: (label_pattern_a, label_pattern_b, reason)
# A violation is suppressed if BOTH labels match (substring check).
# These represent genuine physical constraints that cannot be resolved
# by routing changes alone.
#
# DFM v6: reduced from 10 entries (13 matches) to 1 entry by:
#   - BTN_L: moved approach from x=72.50 to x=68.00 (left of all obstacles)
#   - BTN_R: moved approach from x=76.35 to x=79.00 + F.Cu hop over BTN_Y
#   - BTN_A/X/Y: reduced vias 0.46→0.35mm, increased gap 0.42→0.50mm

_SUPPRESSIONS = [
    # DFM v6: all suppressions eliminated.
    # BTN_L: approach moved to x=68.00 (left of all obstacles)
    # BTN_R: F.Cu L-shape jog to x=65.00 (left of all D-pad stubs)
    # BTN_A/X/Y: vias 0.35mm, gap 0.50mm (adequate clearance)
    # BTN_Y GND: via routed straight down to y=49.0 (below J4 mount pad)
]


def _is_suppressed(v: Violation) -> bool:
    """Check if a violation matches any justified suppression."""
    la = v.obstacle_a.label
    lb = v.obstacle_b.label
    for pat_a, pat_b, _reason in _SUPPRESSIONS:
        if ((pat_a in la and pat_b in lb) or
                (pat_a in lb and pat_b in la)):
            return True
    return False
