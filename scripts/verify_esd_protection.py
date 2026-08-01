#!/usr/bin/env python3
"""ESD Protection Verification — net-verified evidence for external interfaces.

Checks, each answered from the nets a part's pads actually land on:

1. TVS on USB D+/D-        an ESD part (identified by its BOM description)
                           with pads on BOTH USB data nets
2. Series resistors        an inline two-net element between each USB data net
                           and the MCU-side net, value read from the BOM
3. USB CC pull-downs       a two-net element between each CC net and GND
4. Bulk cap on VBUS        a two-net capacitor between a VBUS net and GND
5. ESD clamp on VBUS       an ESD part with a pad on VBUS or VBUS_IN
6. Surge-rated TVS on VBUS the one heuristic check: it classifies the part
                           FAMILY of whatever check 5 found, from BOM text

What this script no longer does
-------------------------------
Checks 1 and 5 used to be answered by `has_tvs_in_bom`, a global OR over every
Comment field in the BOM. U4 is a USB *data-line* protector; that global OR let
it satisfy the VBUS question it says nothing about. Check 5 also had a test of
its own -- `any(ESD_KEYWORDS.search(r) for r in vbus_refs)` -- which matched the
ESD regex against reference designators ("C17", "F1") and so could never fire:
dead code whose only effect was to hand the verdict to the global OR. The USB
data check had a second escape, `has_tvs_in_sch`, an OR over the raw schematic
text, where naming a net is enough to score a hit.

All of them are gone. A check is satisfied by copper or it fails.

Promotion policy (recorded choice, 2026-08-01)
----------------------------------------------
The five NET-VERIFIED checks block: their evidence is pad-to-net
membership on the board, and a red one means protection this design
declares is genuinely absent (exit 1). The one HEURISTIC check (surge
family, read from BOM text) never blocks on its regex alone — a part-
family grep must not be in charge of releases. Instead it defers to the
claims ledger: a deliberate absence is legal only while hardware/CLAIMS.md
carries a VERIFIED-* entry for it (CLAIM-004). Claim UNVERIFIED -> WARN
(the ledger's 45-day clock is already running); claim FALSIFIED or
missing -> FAIL. No waiver list lives in this script.

Missing *evidence* is a different thing from a missing part: if the BOM or
the board cache cannot be read, or a net a check is written against does
not exist, the script exits 2 instead of quietly skipping a check.

Usage:
    python3 scripts/verify_esd_protection.py
    Exit code 0 = protected (or absence ledger-verified), 1 = a protection
    finding blocks, 2 = structural error
"""

import csv
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")
BOM_FILE = os.path.join(BASE, "release_jlcpcb", "bom.csv")
BOM_FILE_ALT = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "bom.csv")
CLAIMS_FILE = os.path.join(BASE, "hardware", "CLAIMS.md")

ESD_KEYWORDS = re.compile(r"TVS|ESD|USBLC|PESD|PRTR|TPD|SP05|CDSOT", re.I)

# Families whose supply-pin cell exists to reference the data-line steering
# diodes rather than to absorb a power-rail surge. A USBLC6-2SC6 clamps its
# Vbus pin to IEC 61000-4-2 ESD levels; it is not an 8/20 us surge element the
# way an SMF5.0A is. The distinction is only visible in the part family name,
# which is BOM text, so check 6 is reported as heuristic and never as
# net-verified evidence.
DATA_LINE_FAMILIES = re.compile(r"USBLC|PRTR|SP05|CDSOT|TPD\d", re.I)

USB_DATA_NETS = ("USB_D+", "USB_D-")
CC_NETS = ("USB_CC1", "USB_CC2")
VBUS_NETS = ("VBUS", "VBUS_IN")
GND = "GND"

# 22 R / 27 R series termination on the USB data pair.
SERIES_R_OHMS = (20.0, 30.0)
# 5.1k +-10 %: what advertises the USB-C device role on each CC line.
CC_PULLDOWN_OHMS = (4.6e3, 5.6e3)

_R_VALUE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*([RrKkMm]?)(?:\s*(?:ohms?|Ω))?\b")
_C_VALUE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*([pnuµ])F\b", re.I)
_R_MULT = {"": 1.0, "r": 1.0, "k": 1e3, "m": 1e6}
_C_MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6}


def _fatal(msg):
    """A structural error: the evidence needed to judge is missing."""
    print(f"\n  ERROR {msg}")
    sys.exit(2)


def _ohms(comment):
    """Resistance from a BOM comment, or None. '22R 0402' -> 22.0."""
    m = _R_VALUE.match(comment.strip())
    return float(m.group(1)) * _R_MULT[m.group(2).lower()] if m else None


def _farads(comment):
    """Capacitance from a BOM comment, or None. '10uF 0805' -> 1e-05."""
    m = _C_VALUE.match(comment.strip())
    return float(m.group(1)) * _C_MULT[m.group(2).lower()] if m else None


def _surge_claim():
    """The ledger entry covering the surge-TVS decision, if any.

    Returns (claim_id, status) for the first CLAIMS.md entry whose
    `- where:` field names this script, else None. Entry hygiene (status
    vocabulary, evidence, the 45-day UNVERIFIED clock) is enforced by
    verify_claims_ledger — this reader only needs identity and status.
    """
    if not os.path.exists(CLAIMS_FILE):
        return None
    with open(CLAIMS_FILE) as f:
        text = f.read()
    for block in text.split("\n## ")[1:]:
        m_id = re.match(r"(CLAIM-\d+)", block)
        m_where = re.search(r"^- where: (.+)$", block, re.M)
        m_status = re.search(r"^- status: (\S+)", block, re.M)
        if (m_id and m_status and m_where
                and "verify_esd_protection" in m_where.group(1)):
            return m_id.group(1), m_status.group(1)
    return None


def _load_bom():
    """Map designator -> Comment, merging the release and generated BOMs."""
    by_ref, files_read = {}, []
    for path in (BOM_FILE, BOM_FILE_ALT):
        if not os.path.exists(path):
            continue
        try:
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except (OSError, UnicodeDecodeError) as exc:
            _fatal(f"cannot read BOM {path}: {exc}")
        files_read.append(path)
        for row in rows:
            comment = (row.get("Comment") or "").strip()
            for ref in (row.get("Designator") or "").split(","):
                ref = ref.strip()
                if ref:
                    by_ref.setdefault(ref, comment)
    if not files_read:
        _fatal("no BOM found — looked for release_jlcpcb/bom.csv and "
               "hardware/kicad/jlcpcb/bom.csv")
    if not by_ref:
        _fatal(f"{files_read[0]} parsed to zero designators — the Comment / "
               "Designator columns are gone or renamed")
    return by_ref


def _load_board():
    """Pad-to-net membership from the SHA-keyed board cache."""
    try:
        cache = load_cache(PCB_FILE)
    except Exception as exc:                      # noqa: BLE001 — report, don't skip
        _fatal(f"cannot read board cache for {PCB_FILE}: {exc}")
    names = {n["id"]: n["name"] for n in cache["nets"]}
    nets_by_ref = defaultdict(set)
    refs_by_net = defaultdict(set)
    pads = defaultdict(list)
    for pad in cache["pads"]:
        ref, net = pad.get("ref"), names.get(pad.get("net"))
        if not ref or not net:
            continue
        nets_by_ref[ref].add(net)
        refs_by_net[net].add(ref)
        pads[(ref, net)].append(str(pad.get("num")))
    if not pads:
        _fatal("board cache holds zero net-connected pads")
    return nets_by_ref, refs_by_net, pads


def _require_nets(refs_by_net):
    """A renamed net must be followed here, not silently turn a check green."""
    missing = [n for n in USB_DATA_NETS + CC_NETS + (GND,) if n not in refs_by_net]
    if missing:
        _fatal("net(s) these checks are written against do not exist on the "
               f"board: {', '.join(missing)}")
    if not any(n in refs_by_net for n in VBUS_NETS):
        _fatal(f"none of {', '.join(VBUS_NETS)} exists on the board — the VBUS "
               "checks have nothing to judge")


def _inline_on(net, nets_by_ref, refs_by_net):
    """Two-terminal parts on `net`: [(ref, the one other net it reaches)]."""
    out = []
    for ref in sorted(refs_by_net.get(net, ())):
        other = nets_by_ref[ref] - {net}
        if len(other) == 1:
            out.append((ref, next(iter(other))))
    return out


def analyze_esd_protection():
    bom = _load_bom()
    nets_by_ref, refs_by_net, pads = _load_board()
    _require_nets(refs_by_net)

    def pad_list(ref, net):
        return ", ".join(f"{ref}.{n}" for n in sorted(pads[(ref, net)]))

    findings = []          # (level, message)
    checks = []            # (name, "net" | "heuristic")
    warns = 0
    fails = 0

    def record(name, kind, level, msg):
        nonlocal warns, fails
        # Promotion policy (see header): a net-verified finding blocks —
        # its evidence is copper. Heuristic findings pass WARN/FAIL as
        # decided at the call site (the ledger, never the regex, blocks).
        if kind == "net" and level == "WARN":
            level = "FAIL"
        checks.append((name, kind))
        findings.append((level, msg))
        if level == "WARN":
            warns += 1
        if level == "FAIL":
            fails += 1

    # ── Protection parts, identified by BOM description then located on copper
    esd_parts = {ref: c for ref, c in bom.items() if ESD_KEYWORDS.search(c)}
    for ref in sorted(esd_parts):
        if ref not in nets_by_ref:
            _fatal(f"BOM declares protection part {ref} ({esd_parts[ref]}) but "
                   "it has no net-connected pads on the board — which nets it "
                   "protects is unknowable")

    def esd_on(net):
        return sorted(r for r in esd_parts if net in nets_by_ref[r])

    # ── 1. TVS on USB D+/D- ────────────────────────────────────────────────
    on_data = {net: esd_on(net) for net in USB_DATA_NETS}
    if all(on_data.values()):
        refs = sorted({r for rs in on_data.values() for r in rs})
        who = ", ".join(f"{r} ({esd_parts[r]})" for r in refs)
        ev = "; ".join(f"{net} <- " + ", ".join(pad_list(r, net) for r in on_data[net])
                       for net in USB_DATA_NETS)
        record("usb_data_tvs", "net", "PASS",
               f"TVS on USB data lines: {who} — {ev}")
    else:
        bare = [n for n, r in on_data.items() if not r]
        elsewhere = (f" (BOM protection parts {', '.join(sorted(esd_parts))} land "
                     "on other nets)" if esd_parts else "")
        record("usb_data_tvs", "net", "WARN",
               f"No ESD part with a pad on {', '.join(bare)}"
               f"{elsewhere} — recommended: USBLC6-2SC6 or similar")

    # ── 2. Series resistors on USB D+/D- ───────────────────────────────────
    series_ok, series_notes = {}, []
    for net in USB_DATA_NETS:
        inline = [(r, o) for r, o in _inline_on(net, nets_by_ref, refs_by_net)
                  if o != GND]
        if not inline:
            series_notes.append(f"{net}: no inline two-terminal element")
            continue
        for ref, other in inline:
            if ref not in bom:
                series_notes.append(
                    f"{net}: {ref} is inline to {other} but has no BOM entry — "
                    "value unverifiable")
                continue
            ohms = _ohms(bom[ref])
            if ohms is None:
                series_notes.append(
                    f"{net}: {ref} is inline to {other} but its BOM comment "
                    f"{bom[ref]!r} is not a resistance")
            elif not SERIES_R_OHMS[0] <= ohms <= SERIES_R_OHMS[1]:
                series_notes.append(
                    f"{net}: {ref} = {bom[ref]} is outside "
                    f"{SERIES_R_OHMS[0]:.0f}-{SERIES_R_OHMS[1]:.0f} ohm")
            else:
                series_ok[net] = (ref, other, bom[ref])
    if len(series_ok) == len(USB_DATA_NETS):
        ev = "; ".join(f"{net}: {ref} ({val}) {net} -> {other}"
                       for net, (ref, other, val) in sorted(series_ok.items()))
        record("usb_series_r", "net", "PASS", f"Series resistors on USB data — {ev}")
    else:
        record("usb_series_r", "net", "WARN",
               "No verified series resistor on "
               f"{', '.join(n for n in USB_DATA_NETS if n not in series_ok)} "
               f"[{'; '.join(series_notes) or 'nothing inline'}] — recommended: "
               "22 ohm")

    # ── 3. USB CC pull-downs ───────────────────────────────────────────────
    #
    # This one was already net-based (a resistor with one pad on the CC net and
    # one on GND) after an earlier repair; before that it was
    # `re.search(r"5\.1k|5k1|CC[12]", all_sch)`, which the net NAME "USB_CC1"
    # satisfied all by itself. What is new here is that the part is found by
    # topology rather than by a refdes starting with "R", and its value is read
    # from the BOM instead of assumed.
    cc_ok, cc_notes = {}, []
    for net in CC_NETS:
        for ref, other in _inline_on(net, nets_by_ref, refs_by_net):
            if other != GND:
                continue
            if ref not in bom:
                cc_notes.append(f"{net}: {ref} goes to GND but has no BOM entry")
                continue
            ohms = _ohms(bom[ref])
            if ohms is None:
                cc_notes.append(f"{net}: {ref} comment {bom[ref]!r} is not a "
                                "resistance")
            elif not CC_PULLDOWN_OHMS[0] <= ohms <= CC_PULLDOWN_OHMS[1]:
                cc_notes.append(f"{net}: {ref} = {bom[ref]}, not 5.1k")
            else:
                cc_ok[net] = (ref, bom[ref])
                break
    if len(cc_ok) == len(CC_NETS):
        ev = ", ".join(f"{net}={ref} ({val})" for net, (ref, val) in sorted(cc_ok.items()))
        record("usb_cc_pulldown", "net", "PASS",
               f"USB CC pull-downs to GND present ({ev}) — device role advertised")
    else:
        record("usb_cc_pulldown", "net", "WARN",
               "No 5.1k pull-down to GND on "
               f"{', '.join(n for n in CC_NETS if n not in cc_ok)} "
               f"[{'; '.join(cc_notes) or 'nothing to GND'}] — the USB-C device "
               "role is not advertised without it")

    # ── 4. Bulk cap on VBUS ────────────────────────────────────────────────
    caps = []
    for net in VBUS_NETS:
        for ref, other in _inline_on(net, nets_by_ref, refs_by_net):
            if other == GND and _farads(bom.get(ref, "")) is not None:
                caps.append((ref, net, bom[ref]))
    if caps:
        ev = ", ".join(f"{ref} ({val}) on {net}" for ref, net, val in sorted(caps))
        record("vbus_bulk_cap", "net", "PASS", f"Bulk capacitance on VBUS: {ev}")
    else:
        record("vbus_bulk_cap", "net", "WARN",
               f"No capacitor between {'/'.join(VBUS_NETS)} and GND")

    # ── 5. ESD clamp on VBUS ───────────────────────────────────────────────
    #
    # The former test greppped ESD_KEYWORDS against reference designators and
    # then fell through to the BOM-wide OR. Now: which ESD part has a pad on
    # the rail, and on which pad.
    vbus_esd = sorted({(r, net) for net in VBUS_NETS for r in esd_on(net)})
    if vbus_esd:
        ev = ", ".join(f"{pad_list(r, net)} on {net}" for r, net in vbus_esd)
        who = ", ".join(sorted({f"{r} ({esd_parts[r]})" for r, _ in vbus_esd}))
        record("vbus_esd_clamp", "net", "PASS",
               f"ESD clamp on VBUS: {who} — {ev}")
    else:
        record("vbus_esd_clamp", "net", "WARN",
               f"No ESD part has a pad on {'/'.join(VBUS_NETS)} — the rail is "
               "unclamped against USB-C hot-plug transients")

    # ── 6. Surge-rated TVS on VBUS (heuristic) ─────────────────────────────
    if not vbus_esd:
        record("vbus_surge_tvs", "heuristic", "FAIL",
               "No surge-rated TVS on VBUS either — check 5 found no ESD "
               "part on the rail at all, so no recorded absence can cover "
               "this")
    else:
        surge = sorted({r for r, _ in vbus_esd
                        if not DATA_LINE_FAMILIES.search(esd_parts[r])})
        if surge:
            record("vbus_surge_tvs", "heuristic", "PASS",
                   "Rail-class TVS on VBUS: "
                   + ", ".join(f"{r} ({esd_parts[r]})" for r in surge))
        else:
            only = ", ".join(f"{r} ({esd_parts[r]})" for r, _ in vbus_esd)
            base_msg = (
                f"No surge-rated TVS on VBUS — the only ESD part on the rail "
                f"is {only}, a USB data-line protector whose supply pin is an "
                "IEC 61000-4-2 clamp, not an 8/20 us surge element "
                "(SMF5.0A class)")
            claim = _surge_claim()
            if claim and claim[1].startswith("VERIFIED"):
                record("vbus_surge_tvs", "heuristic", "PASS",
                       f"{base_msg}. Deliberate absence, recorded and "
                       f"verified as {claim[0]} ({claim[1]}) in "
                       "hardware/CLAIMS.md")
            elif claim and claim[1] == "UNVERIFIED":
                record("vbus_surge_tvs", "heuristic", "WARN",
                       f"{base_msg}. Absence parked as {claim[0]} "
                       "(UNVERIFIED — the ledger's 45-day clock is running)")
            elif claim:  # FALSIFIED
                record("vbus_surge_tvs", "heuristic", "FAIL",
                       f"{base_msg}. The recorded justification {claim[0]} "
                       f"is {claim[1]} — fit the part")
            else:
                record("vbus_surge_tvs", "heuristic", "FAIL",
                       f"{base_msg}. No CLAIMS.md entry covers the absence — "
                       "fit an SMF5.0A-class part at J1 or record the "
                       "decision in the ledger")

    # ── Context, not a check ───────────────────────────────────────────────
    inline_refs = sorted({r for net in USB_DATA_NETS
                          for r, _ in _inline_on(net, nets_by_ref, refs_by_net)}
                         | {r for net in USB_DATA_NETS for r in esd_on(net)})
    findings.append(("INFO", "Parts on USB data nets besides the connector and "
                     f"the MCU: {', '.join(inline_refs) or 'none'}"))

    # ── Report ─────────────────────────────────────────────────────────────
    print("\n── ESD Protection Analysis ──")
    for level, msg in findings:
        print(f"  {level:4s}  {msg}")

    net_checks = sum(1 for _, kind in checks if kind == "net")
    heuristic = len(checks) - net_checks
    if fails:
        print(f"\n  {fails} FAIL — declared protection is absent from the "
              "copper (or its absence has no ledger-verified claim)")
    elif warns:
        print(f"\n  {warns} advisory warning(s) — parked in the claims "
              "ledger, whose clock is running")
    else:
        print("\n  All ESD protection checks passed")
    print(f"  {len(checks)} checks: {net_checks} net-verified (evidence = "
          f"pad-to-net membership on the board), {heuristic} heuristic "
          "(part family read from BOM text; blocks only via the ledger)")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(analyze_esd_protection())
