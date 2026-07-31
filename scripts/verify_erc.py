#!/usr/bin/env python3
"""Gate: KiCad ERC on the generated schematic — zero error-severity findings.

Why this gate exists
--------------------
ERC never ran on this project until 2026-07-31: the KiBot container could
not load the schematic (KiCad 9 vs 10), then non-IPC references (SW_PWR &
co.) hard-blocked the schematic phase, and the one parser that did read an
ERC report looked for top-level ``violations[]`` — the DRC shape — while
ERC nests findings under ``sheets[]``, producing a false "0 errors". The
first real run found a decoupling cap (C3) whose tap wire ended in empty
space one step away from shorting +3V3 into LCD_CS. This gate makes ERC a
standing check instead of a one-off.

Scope: error severity only. The ~650 warning-severity findings (mostly
endpoint_off_grid and lib_symbol_issues) are a separate cleanup; gating on
them today would just get this gate ignored (a red gate stops being read).

Requires kicad-cli on PATH — and fails loudly when it is missing, because
a silently skipped check is how ERC stayed unread for four months.
"""
import json
import os
import subprocess
import sys
import tempfile

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SCH = os.path.join(PROJECT, "hardware", "kicad",
                           "esp32-emu-turbo.kicad_sch")


def collect_violations(report: dict) -> list[dict]:
    """Flatten ERC findings. ERC nests them under sheets[]; keep the
    top-level list too so a future format change cannot silently hide
    findings from this gate."""
    out = list(report.get("violations", []))
    for sheet in report.get("sheets", []):
        for v in sheet.get("violations", []):
            v = dict(v)
            v["_sheet"] = sheet.get("path", "?")
            out.append(v)
    return out


def main() -> int:
    sch = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SCH
    print("=" * 60)
    print("KiCad ERC gate (error severity)")
    print("=" * 60)

    if not os.path.exists(sch):
        print(f"  FAIL  schematic not found: {sch}")
        return 1

    with tempfile.TemporaryDirectory() as td:
        report_path = os.path.join(td, "erc.json")
        try:
            proc = subprocess.run(
                ["kicad-cli", "sch", "erc", "--severity-error",
                 "--format", "json", "-o", report_path, sch],
                capture_output=True, text=True, timeout=300,
            )
        except FileNotFoundError:
            print("  FAIL  kicad-cli not on PATH — this gate cannot run.")
            print("STATUS: FAIL — a skipped ERC is not a passed ERC")
            return 1

        if not os.path.exists(report_path):
            print(f"  FAIL  kicad-cli produced no report "
                  f"(exit {proc.returncode})")
            print((proc.stderr or proc.stdout).strip()[:500])
            return 1

        with open(report_path) as f:
            report = json.load(f)

    errors = [v for v in collect_violations(report)
              if v.get("severity") == "error"]

    for v in errors:
        items = " | ".join(
            f"{i.get('description', '?')} @({i.get('pos', {}).get('x')},"
            f"{i.get('pos', {}).get('y')})"
            for i in v.get("items", [])[:2]
        )
        print(f"  FAIL  [{v.get('_sheet', '/')}] {v.get('type')}: {items}")

    print("-" * 60)
    if errors:
        print(f"Results: FAIL — {len(errors)} error-severity ERC violation(s)")
        print("The schematic drawing disagrees with itself. Fix the sheet")
        print("generator (scripts/generate_schematics/), not the output.")
        return 1
    print("Results: PASS — ERC clean at error severity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
