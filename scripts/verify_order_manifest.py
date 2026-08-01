#!/usr/bin/env python3
"""Fail when release_jlcpcb/order-manifest.json is stale vs the order files.

`run-verifiers.sh` invokes every entry of VERIFY_ALL_SCRIPTS as
`python3 scripts/<name>.py` with no arguments, so the `--check` mode of
the manifest writer needs its own entry point to be part of the suite.

Containment layer 1 (docs/containment-roadmap.md): the manifest is what
the upload protocol compares against; a manifest that lags the files it
fingerprints re-opens the "the fix never reached the order" bug class.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from order_manifest import main as manifest_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(manifest_main(["--check"]))
