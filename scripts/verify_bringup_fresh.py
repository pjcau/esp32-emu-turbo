#!/usr/bin/env python3
"""Fail when the bring-up firmware is stale w.r.t. board_config.h.

`run-verifiers.sh` invokes every entry of VERIFY_ALL_SCRIPTS as
`python3 scripts/<name>.py`, so the `--check` mode of the bring-up
generator needs its own entry point to be part of the suite.

Containment layer 5 (docs/containment-roadmap.md): the bring-up firmware
is the multimeter for a bench with no instruments. If it lags
board_config.h it measures the wrong pins, and every verdict it prints —
PASS and FAIL alike — is about a board that does not exist. That is a
blind spot, not a broken board, and it must go red before a report is
ever trusted.
"""
import os
import subprocess
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(PROJECT, "software", "bringup_test", "generate.py")

if __name__ == "__main__":
    if not os.path.exists(GENERATOR):
        print(f"FAIL  {os.path.relpath(GENERATOR, PROJECT)} does not exist "
              "— the bring-up firmware generator is gone, so first "
              "power-on has no telemetry.")
        sys.exit(1)
    sys.exit(subprocess.run(
        [sys.executable, GENERATOR, "--check"], cwd=PROJECT).returncode)
