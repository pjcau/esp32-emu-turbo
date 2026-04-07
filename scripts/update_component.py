#!/usr/bin/env python3
"""Update a component across all BOM, CPL, and documentation files.

When a component's LCSC part number changes (e.g., SMD to THT variant),
multiple files need updating atomically. This script handles all of them.

Usage:
    python3 scripts/update_component.py --ref J3 --lcsc C173752 \
        --comment "JST PH 2-pin THT" --footprint "JST-PH-2P" \
        --type THT --side Bottom

    python3 scripts/update_component.py --ref J3 --lcsc C173752 \
        --comment "JST PH 2-pin THT" --footprint "JST-PH-2P" --yes
"""

import argparse
import csv
import glob
import io
import os
import re
import sys


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOM_FILES = [
    "hardware/kicad/jlcpcb/bom.csv",
    "release_jlcpcb/bom.csv",
    "release_jlcpcb/jlcpcb/bom.csv",
]

CPL_FILES = [
    "hardware/kicad/jlcpcb/cpl.csv",
    "release_jlcpcb/cpl.csv",
    "release_jlcpcb/jlcpcb/cpl.csv",
    "release_jlcpcb/cpl_u5_rot0.csv",
    "release_jlcpcb/cpl_u5_rot90.csv",
    "release_jlcpcb/cpl_u5_rot180.csv",
    "release_jlcpcb/cpl_u5_rot270.csv",
]

DOCS_DIR = "website/docs"


def abs_path(rel):
    """Return absolute path from project-relative path."""
    return os.path.join(BASE, rel)


def read_csv_lines(path):
    """Read a CSV file and return (header, rows) as raw string lists."""
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        lines = list(reader)
    if not lines:
        return [], []
    return lines[0], lines[1:]


def write_csv_lines(path, header, rows):
    """Write header + rows back to a CSV file."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    with open(path, "w", newline="") as f:
        f.write(buf.getvalue())


def find_designator_in_bom(rows, ref):
    """Find the row index where the designator column contains the ref.

    BOM Designator column may contain grouped refs like "R1,R2,R3".
    Returns (index, old_row) or (None, None).
    """
    for i, row in enumerate(rows):
        if len(row) < 4:
            continue
        designators = [d.strip() for d in row[1].split(",")]
        if ref in designators:
            return i, list(row)
    return None, None


def find_designator_in_cpl(rows, ref):
    """Find the row index where the designator column matches the ref.

    CPL files have one row per designator (no grouping).
    Returns (index, old_row) or (None, None).
    """
    for i, row in enumerate(rows):
        if len(row) < 7:
            continue
        if row[0].strip() == ref:
            return i, list(row)
    return None, None


def compute_bom_changes(path, ref, comment, footprint, lcsc):
    """Compute changes needed for a BOM file.

    Returns (old_values, new_values, header, rows, row_idx) or None if
    the file does not exist or the ref is not found.
    """
    full = abs_path(path)
    if not os.path.exists(full):
        return None

    header, rows = read_csv_lines(full)
    idx, old_row = find_designator_in_bom(rows, ref)
    if idx is None:
        return None

    # BOM format: Comment, Designator, Footprint, LCSC Part #
    old_vals = {
        "Comment": old_row[0],
        "Footprint": old_row[2],
        "LCSC Part #": old_row[3],
    }
    new_vals = {}
    if comment and old_row[0] != comment:
        new_vals["Comment"] = comment
        rows[idx][0] = comment
    if footprint and old_row[2] != footprint:
        new_vals["Footprint"] = footprint
        rows[idx][2] = footprint
    if lcsc and old_row[3] != lcsc:
        new_vals["LCSC Part #"] = lcsc
        rows[idx][3] = lcsc

    if not new_vals:
        return None

    return old_vals, new_vals, header, rows, full


def compute_cpl_changes(path, ref, footprint, layer):
    """Compute changes needed for a CPL file.

    Returns (old_values, new_values, header, rows, row_idx) or None if
    the file does not exist or the ref is not found.
    """
    full = abs_path(path)
    if not os.path.exists(full):
        return None

    header, rows = read_csv_lines(full)
    idx, old_row = find_designator_in_cpl(rows, ref)
    if idx is None:
        return None

    # CPL format: Designator, Val, Package, Mid X, Mid Y, Rotation, Layer
    old_vals = {
        "Package": old_row[2],
        "Layer": old_row[6],
    }
    new_vals = {}
    if footprint and old_row[2] != footprint:
        new_vals["Package"] = footprint
        rows[idx][2] = footprint
    if layer and old_row[6] != layer:
        new_vals["Layer"] = layer
        rows[idx][6] = layer

    if not new_vals:
        return None

    return old_vals, new_vals, header, rows, full


def find_docs_with_lcsc(old_lcsc):
    """Find .md files in website/docs/ that reference the old LCSC number."""
    docs_path = abs_path(DOCS_DIR)
    if not os.path.isdir(docs_path):
        return []

    results = []
    for md_file in glob.glob(os.path.join(docs_path, "**", "*.md"), recursive=True):
        with open(md_file, "r") as f:
            content = f.read()
        if old_lcsc in content:
            results.append(md_file)
    return results


def replace_in_docs(doc_files, old_lcsc, new_lcsc):
    """Replace old LCSC part number with new one in doc files."""
    modified = []
    for path in doc_files:
        with open(path, "r") as f:
            content = f.read()
        new_content = content.replace(old_lcsc, new_lcsc)
        if new_content != content:
            with open(path, "w") as f:
                f.write(new_content)
            modified.append(path)
    return modified


def print_diff(label, old_vals, new_vals):
    """Print a colored diff-like summary for one file."""
    print(f"\n  {label}")
    for key in new_vals:
        old = old_vals.get(key, "")
        new = new_vals[key]
        print(f"    {key}: {old} -> {new}")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Update a component across all BOM/CPL/doc files.",
        epilog=(
            "Example:\n"
            "  python3 scripts/update_component.py --ref J3 --lcsc C173752 \\\n"
            '    --comment "JST PH 2-pin THT" --footprint "JST-PH-2P" \\\n'
            "    --type THT --side Bottom"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ref", required=True,
        help="Component reference designator (e.g., J3, U1, R5)")
    parser.add_argument(
        "--lcsc", required=True,
        help="New LCSC part number (e.g., C173752)")
    parser.add_argument(
        "--comment",
        help="New BOM comment/description (e.g., 'JST PH 2-pin THT')")
    parser.add_argument(
        "--footprint",
        help="New footprint/package name (e.g., 'JST-PH-2P')")
    parser.add_argument(
        "--type", choices=["THT", "SMD"], dest="comp_type",
        help="Component type: THT or SMD")
    parser.add_argument(
        "--side", choices=["Top", "Bottom"],
        help="Board side / layer: Top or Bottom")
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip confirmation prompt and apply changes immediately")
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    ref = args.ref
    lcsc = args.lcsc
    comment = args.comment
    footprint = args.footprint
    layer = args.side
    auto_yes = args.yes

    # Collect old LCSC to find in docs (need to read it before changes)
    old_lcsc = None
    for bom_path in BOM_FILES:
        full = abs_path(bom_path)
        if not os.path.exists(full):
            continue
        header, rows = read_csv_lines(full)
        idx, old_row = find_designator_in_bom(rows, ref)
        if idx is not None:
            old_lcsc = old_row[3]
            break

    if old_lcsc is None:
        print(f"ERROR: Designator '{ref}' not found in any BOM file.")
        sys.exit(1)

    # ── Compute all changes ──────────────────────────────────────────
    bom_changes = []
    for path in BOM_FILES:
        result = compute_bom_changes(path, ref, comment, footprint, lcsc)
        if result:
            bom_changes.append((path, result))

    cpl_changes = []
    for path in CPL_FILES:
        result = compute_cpl_changes(path, ref, footprint, layer)
        if result:
            cpl_changes.append((path, result))

    doc_files = []
    if old_lcsc != lcsc:
        doc_files = find_docs_with_lcsc(old_lcsc)

    # ── Check if there is anything to do ─────────────────────────────
    if not bom_changes and not cpl_changes and not doc_files:
        print(f"No changes needed for {ref} — all files already up to date.")
        sys.exit(0)

    # ── Show diff ────────────────────────────────────────────────────
    print(f"=== Changes for {ref} (LCSC: {old_lcsc} -> {lcsc}) ===")

    if bom_changes:
        print("\nBOM files:")
        for path, (old_vals, new_vals, _, _, _) in bom_changes:
            print_diff(path, old_vals, new_vals)

    if cpl_changes:
        print("\nCPL files:")
        for path, (old_vals, new_vals, _, _, _) in cpl_changes:
            print_diff(path, old_vals, new_vals)

    if doc_files:
        print(f"\nDocumentation files ({old_lcsc} -> {lcsc}):")
        for path in doc_files:
            rel = os.path.relpath(path, BASE)
            print(f"  {rel}")

    total = len(bom_changes) + len(cpl_changes) + len(doc_files)
    print(f"\nTotal: {total} file(s) will be modified.")

    # ── Confirm ──────────────────────────────────────────────────────
    if not auto_yes:
        try:
            answer = input("\nApply changes? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(1)
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(1)

    # ── Apply changes ────────────────────────────────────────────────
    modified = []

    for path, (_, _, header, rows, full) in bom_changes:
        write_csv_lines(full, header, rows)
        modified.append(path)

    for path, (_, _, header, rows, full) in cpl_changes:
        write_csv_lines(full, header, rows)
        modified.append(path)

    if doc_files and old_lcsc != lcsc:
        updated_docs = replace_in_docs(doc_files, old_lcsc, lcsc)
        for path in updated_docs:
            modified.append(os.path.relpath(path, BASE))

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n=== Done: {len(modified)} file(s) modified ===")
    for path in modified:
        print(f"  [OK] {path}")

    if modified:
        print(
            "\nReminder: Run 'python3 scripts/verify_dfa.py' to validate "
            "BOM/CPL consistency."
        )


if __name__ == "__main__":
    main()
