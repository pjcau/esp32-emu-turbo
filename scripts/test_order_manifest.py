#!/usr/bin/env python3
"""Mutation tests for order_manifest.py — the freshness gate must be
able to fail.

A manifest gate that passes on a tampered file is worse than no gate: it
stamps "the order matches" on files it never actually compared. So:

    T1  a fresh manifest over intact files passes
    T2  a single flipped byte in one order file turns the check red
    T3  a missing manifest is red, never a soft-pass
    T4  a missing order file is a hard error in BOTH modes (the absence
        must never shrink the manifest into one that then passes forever)
    T5  verify_order_manifest is in VERIFY_ALL_SCRIPTS and the dispatch
        law routes it — a gate nobody runs or owns contains nothing
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import order_manifest as om  # noqa: E402
from issue_dispatch import gates_from_makefile, route  # noqa: E402


def make_release(tmp: Path) -> Path:
    rel = tmp / "release_jlcpcb"
    rel.mkdir()
    for name in om.ORDER_FILES:
        (rel / name).write_bytes(f"payload of {name}\n".encode() * 10)
    return rel


def main() -> int:
    print("=" * 72)
    print("ORDER-MANIFEST MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    tmp = Path(tempfile.mkdtemp(prefix="order_manifest_test_"))
    try:
        rel = make_release(tmp)

        # T1: intact files, fresh manifest -> green
        om.write_manifest(release_dir=str(rel), project_dir=str(tmp))
        check("T1 fresh manifest passes",
              om.check_manifest(release_dir=str(rel)) == 0)

        # T2: flip one byte in one order file -> red
        victim = rel / om.ORDER_FILES[1]
        data = bytearray(victim.read_bytes())
        data[0] ^= 0xFF
        victim.write_bytes(bytes(data))
        check("T2 tampered order file is caught",
              om.check_manifest(release_dir=str(rel)) != 0)

        # T3: no manifest at all -> red
        (rel / om.MANIFEST_NAME).unlink()
        check("T3 missing manifest is red",
              om.check_manifest(release_dir=str(rel)) != 0)

        # T4: a missing order file is a hard error in both modes
        om.write_manifest(release_dir=str(rel), project_dir=str(tmp))
        (rel / om.ORDER_FILES[0]).unlink()
        try:
            om.check_manifest(release_dir=str(rel))
            check("T4a missing order file hard-errors in --check", False,
                  "no error raised")
        except SystemExit as e:
            check("T4a missing order file hard-errors in --check",
                  e.code not in (0, None))
        try:
            om.write_manifest(release_dir=str(rel), project_dir=str(tmp))
            check("T4b missing order file hard-errors in write", False,
                  "no error raised")
        except SystemExit as e:
            check("T4b missing order file hard-errors in write",
                  e.code not in (0, None))
    finally:
        shutil.rmtree(tmp)

    # T5: the gate is run and owned
    gates = gates_from_makefile()
    check("T5a verify_order_manifest in VERIFY_ALL_SCRIPTS",
          "verify_order_manifest" in gates)
    check("T5b dispatch routes verify_order_manifest",
          route("verify_order_manifest") is not None)
    check("T5c dispatch routes test_order_manifest",
          route("test_order_manifest") is not None)

    print("=" * 72)
    if failures:
        print(f"FAIL — {len(failures)} test(s): {', '.join(failures)}")
        return 1
    print("PASS — the order-manifest gate can fail, and does so for the "
          "right reasons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
