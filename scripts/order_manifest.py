#!/usr/bin/env python3
"""Order manifest — SHA256 fingerprint of exactly what goes to JLCPCB.

Containment layer 1 of docs/containment-roadmap.md (closes residual-risk
class 3: drift between what was verified and what was uploaded). Two
incidents motivated it: the U4 rotation fix that sat months outside
`release_jlcpcb/`, and the C2 polarity fix that never reached the
uploaded order. No geometric gate can see JLC's website; what a gate CAN
see is whether the manifest that the upload protocol checks against
still matches the files on disk.

Modes
-----
    python3 scripts/order_manifest.py            # write the manifest
    python3 scripts/order_manifest.py --check    # fail if stale (gate mode)

Write mode hashes the order files in `release_jlcpcb/` and writes
`release_jlcpcb/order-manifest.json`. Check mode recomputes the hashes
and fails when they disagree with the manifest — the same relationship
`verify_net_explorer_fresh` has to the Net Explorer data.

At upload time the protocol is: `make order-manifest` (if not fresh),
read the printed SHA256s, and after uploading verify file-by-file that
what the JLC order preview shows (file names, sizes, the rendered board)
came from THESE files — then record the manifest hash in the release
notes. A fix that is not in these hashes is not in the order.

Provenance fields (`generatedAt`, `gitHead`) are recorded for the human
reading the manifest next to an order confirmation; `--check` compares
ONLY the file hashes, or every commit would make the manifest "stale".
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_DIR = os.path.join(PROJECT_DIR, "release_jlcpcb")
MANIFEST_NAME = "order-manifest.json"

# The three files JLCPCB actually receives. Everything else in
# release_jlcpcb/ (renders, reports, README) is documentation about the
# order, not the order.
ORDER_FILES = ["gerbers.zip", "bom.csv", "cpl.csv"]


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_order_files(release_dir: str) -> dict:
    """Hash every order file, failing loudly on a missing one.

    A missing order file must never produce a smaller manifest that then
    passes --check forever: the absence IS the finding.
    """
    missing = [f for f in ORDER_FILES
               if not os.path.exists(os.path.join(release_dir, f))]
    if missing:
        raise SystemExit(
            f"order_manifest: missing order file(s) in {release_dir}: "
            f"{', '.join(missing)} — there is no order to fingerprint.")
    return {
        name: {
            "sha256": sha256_of(os.path.join(release_dir, name)),
            "bytes": os.path.getsize(os.path.join(release_dir, name)),
        }
        for name in ORDER_FILES
    }


def git_head(project_dir: str) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=project_dir,
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def write_manifest(release_dir: str = RELEASE_DIR,
                   project_dir: str = PROJECT_DIR) -> int:
    manifest = {
        "generatedAt": datetime.date.today().isoformat(),
        "gitHead": git_head(project_dir),
        "files": hash_order_files(release_dir),
    }
    out = os.path.join(release_dir, MANIFEST_NAME)
    with open(out, "w") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print(f"Order manifest -> {os.path.relpath(out, project_dir)}")
    for name, entry in manifest["files"].items():
        print(f"  {entry['sha256']}  {name} ({entry['bytes']} bytes)")
    print("Upload protocol: these hashes go in the release notes; a fix "
          "that is not in these hashes is not in the order.")
    return 0


def check_manifest(release_dir: str = RELEASE_DIR) -> int:
    path = os.path.join(release_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        print(f"FAIL  {MANIFEST_NAME} does not exist — run "
              "`make order-manifest`. Without it the upload protocol has "
              "nothing to compare against, which is exactly how the U4 and "
              "C2 fixes missed their orders.")
        return 1
    with open(path) as fh:
        manifest = json.load(fh)
    recorded = manifest.get("files", {})
    if sorted(recorded) != sorted(ORDER_FILES):
        print(f"FAIL  {MANIFEST_NAME} covers {sorted(recorded)} but the "
              f"order is {sorted(ORDER_FILES)} — regenerate it.")
        return 1
    current = hash_order_files(release_dir)
    stale = [name for name in ORDER_FILES
             if recorded[name]["sha256"] != current[name]["sha256"]]
    if stale:
        for name in stale:
            print(f"FAIL  {name} changed since the manifest was written "
                  f"(manifest {recorded[name]['sha256'][:12]}…, "
                  f"on disk {current[name]['sha256'][:12]}…)")
        print("The order files moved after fingerprinting — run "
              "`make order-manifest` so the upload protocol checks "
              "against what is actually on disk.")
        return 1
    print(f"PASS  order manifest matches {len(ORDER_FILES)} order files "
          f"(written {manifest.get('generatedAt', '?')} at "
          f"{manifest.get('gitHead', '?')})")
    return 0


def main(argv: list[str]) -> int:
    if "--check" in argv:
        return check_manifest()
    return write_manifest()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
