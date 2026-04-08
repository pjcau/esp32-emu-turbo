#!/usr/bin/env python3
"""Verify PCB pad-to-net assignments against datasheet specifications.

Loads the centralized datasheet specs from hardware/datasheet_specs.py
and compares every pin against the actual PCB cache data.

Reports: PASS, FAIL, INFO (intentionally unconnected), WARN (type mismatch)

Usage:
    python3 scripts/verify_datasheet_nets.py
    python3 scripts/verify_datasheet_nets.py --verbose
    python3 scripts/verify_datasheet_nets.py --component J1
"""

import argparse
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from hardware.datasheet_specs import COMPONENT_SPECS
from pcb_cache import load_cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_net_map(cache):
    """Build net_id -> net_name mapping."""
    return {n["id"]: n["name"] for n in cache["nets"]}


def _build_pad_lookup(cache):
    """Build (ref, pad_num) -> pad_info dict. Dedup by taking first layer."""
    lookup = {}
    for p in cache["pads"]:
        key = (p["ref"], p["num"])
        if key not in lookup:
            lookup[key] = p
    return lookup


def _check_net_match(expected_spec, actual_net_name):
    """Check if actual net name matches the expected spec.

    Returns: (passed: bool, detail: str)
    """
    match_type = expected_spec.get("match", "exact")

    if match_type == "unconnected":
        if actual_net_name == "" or actual_net_name is None:
            return True, "unconnected (expected)"
        else:
            return False, f"expected unconnected, got '{actual_net_name}'"

    elif match_type == "exact":
        expected_net = expected_spec["net"]
        if actual_net_name == expected_net:
            return True, f"= {actual_net_name}"
        elif actual_net_name == "" or actual_net_name is None:
            return False, f"UNCONNECTED (expected '{expected_net}')"
        else:
            return False, f"= {actual_net_name} (expected '{expected_net}')"

    elif match_type == "any_of":
        allowed = expected_spec["nets"]
        if actual_net_name in allowed:
            return True, f"= {actual_net_name}"
        elif actual_net_name == "" or actual_net_name is None:
            if "" in allowed:
                return True, "unconnected (allowed)"
            return False, f"UNCONNECTED (expected one of {allowed})"
        else:
            return False, f"= {actual_net_name} (expected one of {allowed})"

    return False, f"unknown match type: {match_type}"


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class Stats:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.info = 0
        self.warn = 0
        self.failures = []

    @property
    def total(self):
        return self.passed + self.failed + self.info + self.warn


def verify_component(ref, spec, pad_lookup, net_map, verbose=False):
    """Verify one component's pins against spec.

    Returns Stats object.
    """
    stats = Stats()
    comp_name = spec["component"]

    print(f"\n── {ref} {comp_name} ──")
    if spec.get("datasheet"):
        print(f"   Datasheet: {spec['datasheet']}, page {spec.get('datasheet_page', '?')}")

    for pin_num, pin_spec in sorted(spec["pins"].items(), key=lambda x: (len(x[0]), x[0])):
        key = (ref, pin_num)
        pad = pad_lookup.get(key)

        if pad is None:
            # NPTH pads (pad num "") won't match — skip silently for unnamed pads
            if pin_num == "":
                continue
            # Check if this pad exists at all
            stats.failed += 1
            detail = f"PAD NOT FOUND in PCB"
            stats.failures.append(f"{ref} pad {pin_num}: {detail}")
            print(f"  FAIL  {ref} pad {pin_num}: {detail}  [{pin_spec['function']}]")
            continue

        actual_net_id = pad.get("net", 0)
        actual_net_name = net_map.get(actual_net_id, "")
        actual_type = pad.get("type", "smd")

        # Check net assignment
        expected_net_spec = pin_spec["net"]
        passed, detail = _check_net_match(expected_net_spec, actual_net_name)

        # Check pad type
        expected_type = pin_spec.get("type")
        type_ok = True
        type_detail = ""
        if expected_type and actual_type != expected_type:
            # np_thru_hole is acceptable when thru_hole is expected (positioning holes)
            if not (expected_type == "thru_hole" and actual_type == "np_thru_hole"):
                type_ok = False
                type_detail = f" [TYPE: got {actual_type}, expected {expected_type}]"

        # Check drill size for THT pads
        drill_detail = ""
        min_drill = pin_spec.get("min_drill", 0)
        if min_drill > 0 and pad.get("drill", 0) > 0:
            if pad["drill"] < min_drill:
                drill_detail = f" [DRILL: {pad['drill']}mm < min {min_drill}mm]"
                type_ok = False

        if passed and type_ok:
            if expected_net_spec.get("match") == "unconnected":
                stats.info += 1
                if verbose:
                    print(f"  INFO  {ref} pad {pin_num}: {detail}  [{pin_spec['function']}]")
            else:
                stats.passed += 1
                print(f"  PASS  {ref} pad {pin_num} {detail}")
        elif passed and not type_ok:
            stats.warn += 1
            msg = f"{ref} pad {pin_num} {detail}{type_detail}{drill_detail}"
            stats.failures.append(msg)
            print(f"  WARN  {msg}  [{pin_spec['function']}]")
        else:
            stats.failed += 1
            msg = f"{ref} pad {pin_num}: {detail}{type_detail}{drill_detail}"
            stats.failures.append(msg)
            print(f"  FAIL  {msg}  [{pin_spec['function']}]")

    # Extra validation for tact switches: check signal pair and GND pair
    sig_pair = spec.get("_require_signal_pair")
    if sig_pair:
        sig_pins = sig_pair["pins"]
        required_net = sig_pair["net"]
        found = False
        for sp in sig_pins:
            p = pad_lookup.get((ref, sp))
            if p:
                nn = net_map.get(p.get("net", 0), "")
                if nn == required_net:
                    found = True
                    break
        if not found:
            stats.failed += 1
            detail = f"Neither pin {sig_pins[0]} nor {sig_pins[1]} has net '{required_net}'"
            stats.failures.append(f"{ref}: {detail}")
            print(f"  FAIL  {ref}: {detail}")
        else:
            stats.passed += 1
            print(f"  PASS  {ref} signal pair: '{required_net}' found")

    gnd_pair = spec.get("_require_gnd_pair")
    if gnd_pair:
        gnd_pins = gnd_pair["pins"]
        required_net = gnd_pair["net"]
        found = False
        for gp in gnd_pins:
            p = pad_lookup.get((ref, gp))
            if p:
                nn = net_map.get(p.get("net", 0), "")
                if nn == required_net:
                    found = True
                    break
        if not found:
            stats.failed += 1
            detail = f"Neither pin {gnd_pins[0]} nor {gnd_pins[1]} has net '{required_net}'"
            stats.failures.append(f"{ref}: {detail}")
            print(f"  FAIL  {ref}: {detail}")
        else:
            stats.passed += 1
            print(f"  PASS  {ref} GND pair: '{required_net}' found")

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Verify PCB nets against datasheet specs")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show INFO lines for intentionally unconnected pins")
    parser.add_argument("--component", "-c", type=str, default=None,
                        help="Verify only this component (e.g. J1, U1)")
    args = parser.parse_args()

    pcb_path = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

    print("=" * 60)
    print("  Datasheet Net Verification")
    print("=" * 60)

    # Load PCB cache
    cache = load_cache(pcb_path)
    net_map = _build_net_map(cache)
    pad_lookup = _build_pad_lookup(cache)

    total_stats = Stats()

    # Determine which components to verify
    if args.component:
        refs = [args.component.upper()]
        if refs[0] not in COMPONENT_SPECS:
            print(f"\nERROR: No spec defined for '{refs[0]}'")
            print(f"Available: {', '.join(sorted(COMPONENT_SPECS.keys()))}")
            sys.exit(1)
    else:
        refs = sorted(COMPONENT_SPECS.keys())

    for ref in refs:
        spec = COMPONENT_SPECS[ref]
        s = verify_component(ref, spec, pad_lookup, net_map, verbose=args.verbose)
        total_stats.passed += s.passed
        total_stats.failed += s.failed
        total_stats.info += s.info
        total_stats.warn += s.warn
        total_stats.failures.extend(s.failures)

    # Summary
    print("\n" + "=" * 60)
    print(f"  SUMMARY: {len(refs)} components verified")
    print(f"    PASS: {total_stats.passed}")
    print(f"    FAIL: {total_stats.failed}")
    print(f"    WARN: {total_stats.warn}")
    print(f"    INFO: {total_stats.info} (intentionally unconnected)")
    print(f"    TOTAL: {total_stats.total} checks")

    if total_stats.failures:
        print(f"\n  FAILURES ({len(total_stats.failures)}):")
        for f in total_stats.failures:
            print(f"    - {f}")

    print("=" * 60)

    if total_stats.failed > 0:
        print(f"\nFAILED: {total_stats.failed} pin(s) have wrong net assignment")
        sys.exit(1)
    elif total_stats.warn > 0:
        print(f"\nWARNING: {total_stats.warn} pin(s) have type/drill warnings")
        sys.exit(0)
    else:
        print(f"\nALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
