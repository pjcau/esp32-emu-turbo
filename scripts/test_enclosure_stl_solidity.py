"""Mutation tests for the S12 solidity check in verify_enclosure_stl.py.

S12 (mesh_solidity()) reads an exported STL with numpy only (no trimesh —
it runs under the system python3) and must flag the exact defect class
meshcheck found 2026-10-10 in case_top.stl: a CSG operand exactly
coincident or tangent with another, left as zero-volume two-triangle
sheets, disconnected from the main body. These cases are synthetic STLs
written directly (no Docker, no OpenSCAD) so the suite runs in
milliseconds:

    T1 closed tetrahedron alone                 solid       -> solidity OK
    T2 T1 + a disconnected zero-volume sheet     defect      -> solidity FAILS
    T3 T1 with shared-vertex coords jittered     still solid -> solidity OK
       by 1e-6 mm (well inside the merge tolerance): proves the merge
       step doesn't itself cause false positives
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_enclosure_stl as ves  # noqa: E402

# A standard closed tetrahedron: 4 faces, consistent winding (every
# undirected edge used by exactly 2 triangles, opposite directions).
TETRA = {
    "A": (0.0, 0.0, 0.0),
    "B": (1.0, 0.0, 0.0),
    "C": (0.0, 1.0, 0.0),
    "D": (0.0, 0.0, 1.0),
}
TETRA_FACES = [("A", "C", "B"), ("A", "B", "D"), ("A", "D", "C"), ("B", "C", "D")]

# A flat, disconnected 2-triangle sheet (zero volume, floating away from
# the tetrahedron): the exact shape of the real defect — two triangles
# sharing one internal diagonal, with an open (non-watertight) boundary.
SHEET_PTS = {
    "P0": (0.0, 0.0, 100.0),
    "P1": (1.0, 0.0, 100.0),
    "P2": (1.0, 1.0, 100.0),
    "P3": (0.0, 1.0, 100.0),
}
SHEET_FACES = [("P0", "P1", "P2"), ("P0", "P2", "P3")]


def write_stl(path: Path, points: dict, faces: list[tuple[str, str, str]]) -> None:
    lines = ["solid test"]
    for a, b, c in faces:
        lines.append("  facet normal 0 0 0")
        lines.append("    outer loop")
        for name in (a, b, c):
            x, y, z = points[name]
            lines.append(f"      vertex {x} {y} {z}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid test")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    print("=" * 72)
    print("ENCLOSURE-STL SOLIDITY (S12) MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)

        t1 = tdp / "t1_tetra.stl"
        write_stl(t1, TETRA, TETRA_FACES)
        s1 = ves.mesh_solidity(t1)
        ok1 = s1["watertight"] and s1["bodies"] == 1 and s1["volume"] > 1e-6
        check("T1 closed tetrahedron is solid", ok1, str(s1))

        t2 = tdp / "t2_tetra_plus_sheet.stl"
        write_stl(t2, {**TETRA, **SHEET_PTS}, TETRA_FACES + SHEET_FACES)
        s2 = ves.mesh_solidity(t2)
        defect_caught = not (s2["watertight"] and s2["bodies"] == 1 and s2["volume"] > 1e-6)
        check("T2 duplicated zero-volume sheet is caught", defect_caught,
              f"{s2} (watertight must be False or bodies != 1)")

        jittered = {k: (x + 7e-7, y - 3e-7, z + 2e-7) for k, (x, y, z) in TETRA.items()}
        t3 = tdp / "t3_tetra_jitter.stl"
        write_stl(t3, jittered, TETRA_FACES)
        s3 = ves.mesh_solidity(t3)
        ok3 = s3["watertight"] and s3["bodies"] == 1 and s3["volume"] > 1e-6
        check("T3 sub-tolerance float noise still merges solid", ok3, str(s3))

    print("-" * 72)
    if failures:
        print(f"Results: FAIL — {len(failures)} case(s): {', '.join(failures)}")
        return 1
    print("Results: PASS — 3/3 solidity mutations detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
