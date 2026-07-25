#!/usr/bin/env python3
"""Fail when the Net Explorer data is stale vs the .kicad_pcb.

`run-verifiers.sh` invokes every entry of VERIFY_ALL_SCRIPTS as
`python3 scripts/<name>.py` with no arguments, so the `--check` mode of
the generator needs its own entry point to be part of the suite.

The explorer is documentation about where every track goes. Documentation
that silently lags the board it describes is worse than none — someone
traces a net in the browser, reads a route that no longer exists, and
trusts it. This check is what makes `make verify-all` refuse to pass
after a routing, placement or BOM change until `make net-explorer` has
been run.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_net_explorer import main as generate  # noqa: E402

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--check"]
    sys.exit(generate())
