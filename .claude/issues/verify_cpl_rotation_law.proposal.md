# verify_cpl_rotation_law — PROPOSAL

**Reproduce:** `python3 scripts/verify_cpl_rotation_law.py`
**Failing refs:** U2 (off by 90°), J4 (off by 180°), U4 (off by 90°)
**Verdict per ref (one-line summary; details below):**

| ref  | LCSC     | verdict                       | one-line fix                                                                                              |
|------|----------|-------------------------------|-----------------------------------------------------------------------------------------------------------|
| U2   | C181692  | LAW needs a declared exception | Add `_LAW_EXCEPTIONS["U2"] = (90, …)` — EasyEDA draws ESOP-8 horizontally; empirically OK on R4-R8.        |
| U4   | C7519    | LAW needs a declared exception | Add `_LAW_EXCEPTIONS["U4"] = (270, …)` — EasyEDA draws SOT-23-6 horizontally; SOT-23 family formula holds. |
| J4   | C2856812 | INSUFFICIENT EVIDENCE — hold   | Do NOT add an exception. `_JLCPCB_ROT_DELTAS["J4"]=180` predates the 2026-07-25 checker correction and must be re-audited against JLCPCB 3D preview / prototype photo before either action. |

The current `release_jlcpcb/cpl.csv` at HEAD is asserted correct for U2 and U4 by this pass; J4 is unresolved.
Reminder: **a design-side fix is not done until the CPL is re-uploaded** — this proposal does NOT change any emitted CPL angle. It only proposes to update the LAW gate so it stops flagging U2/U4 as false FAILs, and to explicitly withhold judgment on J4 pending visual evidence.

---

## 1. Root cause

The LAW `cpl + row_board + row_ee ≡ 180°` (bottom) assumes EasyEDA's drawing angle equals the JLCPCB tape-and-reel angle for every part. That assumption is empirically false for at least two package families in this BOM:

- **`scripts/generate_pcb/footprints.py:202` (`esop8`)** — draws pin row along **±Y** (`pad 1 (-3.0, -1.905)`, `pad 2 (-3.0, -0.635)` → pad-1→2 bearing 90°). The EasyEDA reference `scripts/.easyeda_cache/C181692/fp.pretty/ESOP-8_L4.9-W3.9-P1.27-LS6.0-BL-EP.kicad_mod` draws the same physical part with pin row along **±X** (`pad 1 (-1.91, +2.91)`, `pad 2 (-0.63, +2.91)` → bearing 0°). Same tape, different drawing angle → the LAW residual is off by 90° for U2 while the physical CPL is correct.
- **`scripts/generate_pcb/footprints.py:708` (`sot23_6`)** — draws pins 1-3 horizontally (bearing 0°), just like EasyEDA. But EasyEDA draws **SOT-23-3** vertically (`C10487` pad 1 (+1.24, +0.95), pad 2 (+1.24, -0.95), bearing 270°). Q1 (SOT-23-3) and U4 (SOT-23-6) share the same physical tape (`^SOT-23` family, `-90` correction in `_JLCPCB_ROT_CORRECTIONS`) yet EasyEDA draws them 90° apart. Q1 satisfies the LAW by accident because the drawing offset happens to cancel the row_board offset; U4 fails for the same reason it happened to line up for Q1.

For J4 the origin is different:

- **`scripts/generate_pcb/jlcpcb_export.py:96` — `_JLCPCB_ROT_DELTAS["J4"] = 180`**, comment: *"FPC-40P (C2856812) — JLCPCB 3D: 90° puts pins on wrong side, 270° aligns"*. The δ_row is 0 (our footprint matches EasyEDA byte-for-byte for pads 1-2). The 180° delta is a **pre-2026-07-25 empirical claim** copied from the old `_JLCPCB_ROT_OVERRIDES` table (per `POLARITY_AUDIT.md::J4` — dated 2026-04-15). The 2026-07-25 checker correction explicitly flagged "any δ_row=0 with a rotation override" as the signature the old checker used to fabricate false FAILs, so **an additive delta on a δ_row=0 part is exactly the pattern the corrected model warns against**.

The 41-N pin reversal in `scripts/generate_pcb/routing.py:638-647` is **orthogonal** to this issue and is not the cause of any CPL failure: it affects which panel signal is assigned to which numbered footprint pad, not where physical pin 1 lands.

## 2. Why the gate is right — or where it is wrong

- **U2 (IP5306, C181692) — the LAW is wrong here.** Independent evidence the current CPL 0° works: `scripts/verify_easyeda_footprint.py` already lists U2 as `[ALLOW]` with δ_row=90° and evidence *"Boards R4-R8 charge via USB-C and boost to 5V → IP5306 operational on correct pins → physical pin mapping validated empirically"*. If the LAW's proposed CPL 90° were applied, it would rotate a part that has demonstrably worked on 5+ prototype batches. `_JLCPCB_ROT_CORRECTIONS` has no `^ESOP-` entry, so it falls through to the default 180° correction, which yields CPL 0° — this is the value that has always shipped and has always worked.
- **U4 (USBLC6-2SC6, C7519) — the LAW is wrong here.** U4 and Q1 are the same physical tape family (`^SOT-23`), the family constant `-90` in `_JLCPCB_ROT_CORRECTIONS:52` yields CPL 90° for both, and Q1 is empirically validated on R4-R8 (boards power up through Q1's reverse-polarity protection). Two working data points in the same family with different `row_ee` and the same CPL angle directly refute the LAW's premise that `cpl + row_board + row_ee` is constant across a layer — this is exactly the argument `POLARITY_AUDIT.md` uses in its "Checker model correction (2026-07-25)" section. `verify_easyeda_footprint.py` also reports U4 as `[OK]` with δ_row=0.
- **J4 (FPC-05F-40PH20 XUNPU right-angle, C2856812) — cannot be decided from the desk.** Two contradictory signals:
  - The LAW gate + the 2026-07-25 checker principle (*"δ_row = 0 does not by itself justify an additive override"*) both say `_JLCPCB_ROT_DELTAS["J4"] = 180` is suspect and should be removed → CPL becomes 90°.
  - `POLARITY_AUDIT.md::J4` (2026-04-15) claims *"Without override, JLCPCB 3D model places pin 1 triangle on the opposite end vs our silk"* — an empirical observation that the delta is required. `verify_easyeda_footprint.py` echoes this as `[REVIEW]` with the comment *"footprint OK; override kept for 3D-model orientation"*.
  - Neither has been re-checked under the post-2026-07-25 model, and the underlying datasheet PDF is corrupted (`POLARITY_AUDIT.md` action item #2). The right-angle vertical-mount FPC is exactly the sort of package where tape orientation could legitimately differ from the flat-drawing angle, so the 3D-preview claim is plausible — but "plausible" is not the standard this repo enforces (`feedback_never_silence_errors`).
  - The one datum that would settle it (a screenshot of JLCPCB's 3D preview for C2856812, or a photo of a prototype with the FPC installed) is not in the tree. This finding does not tip the LAW gate either way — it tips it *toward "prove one of the two claims"*.

## 3. Proposed change

**Only `scripts/verify_cpl_rotation_law.py` is edited. No hardware, no CPL, no gerbers.**

Replace the empty `_LAW_EXCEPTIONS: dict[str, tuple[float, str]] = {}` at line 71 with:

```python
_LAW_EXCEPTIONS: dict[str, tuple[float, str]] = {
    "U2": (
        90.0,
        "IP5306 ESOP-8 (C181692). EasyEDA draws ESOP-8 with pins along the "
        "horizontal row (row_ee=0), our footprints.esop8() draws them along "
        "the vertical row (row_board=90 after B.Cu mirror). Same physical "
        "tape, drawing-convention difference only — no _JLCPCB_ROT_CORRECTIONS "
        "entry for ^ESOP-, so the default 180° correction yields CPL 0° and "
        "that value has been assembled correctly on R4-R8 (USB-C charge + 5V "
        "boost operational). Cross-reference: verify_easyeda_footprint.py "
        "reports [ALLOW] with δ_row=90° and the same empirical evidence."
    ),
    "U4": (
        270.0,
        "USBLC6-2SC6 SOT-23-6 (C7519). Same physical tape family as Q1 "
        "(SOT-23-3), same -90° correction in _JLCPCB_ROT_CORRECTIONS['^SOT-23'], "
        "same CPL 90°. Q1 is empirically validated on R4-R8 (reverse-polarity "
        "MOSFET conducts under normal battery power); U4 inherits its physical "
        "tape orientation from that family constant. The residual differs from "
        "Q1's only because EasyEDA draws SOT-23-3 vertically (row_ee=270°) and "
        "SOT-23-6 horizontally (row_ee=0°) — a drawing inconsistency internal "
        "to EasyEDA's library, not a polarity defect. verify_easyeda_footprint "
        ".py reports [OK] with δ_row=0. See POLARITY_AUDIT.md 'Checker model "
        "correction (2026-07-25)' for the derivation."
    ),
    # J4 (C2856812) — NOT added here.
    #
    # J4 fails by 180°, i.e. it accuses _JLCPCB_ROT_DELTAS['J4']=180 of being
    # an unjustified additive override. The only recorded justification for
    # that delta is a 2026-04-15 JLCPCB-3D-preview observation in
    # POLARITY_AUDIT.md::J4, made under the pre-2026-07-25 checker model that
    # was later shown to over-recommend overrides. It has not been re-verified
    # against either (a) a fresh JLCPCB 3D preview of C2856812 or (b) a photo
    # of the FPC on a physical prototype. Adding an exception here would
    # silently endorse the delta; removing the delta could dead-board the
    # display. Withhold judgment: leave J4 FAILing until one of those two
    # pieces of evidence is captured and cited here.
}
```

Nothing else changes.

## 4. Blast radius

- **Files touched by this proposal, if applied:** `scripts/verify_cpl_rotation_law.py` only.
- **CPL emitted (`release_jlcpcb/cpl.csv`):** unchanged. U2, U4, J4 keep their current 0°/90°/270° angles byte-for-byte.
- **Gerbers, `_JLCPCB_ROT_DELTAS`, `_JLCPCB_ROT_CORRECTIONS`, footprints:** untouched.
- **`board_config.h` and firmware:** unaffected (rotation gate is assembly-only).
- **Documentation:** `POLARITY_AUDIT.md::U3` is stale (still describes AMS1117 SOT-223; U3 is now SY8089 SOT-23-5, C78988). Not touched in this pass, but flagged — this rotation-law investigation surfaces it. Same for `MEMORY.md`'s "USB-C shield THT" line and the pre-`42f51ef` J4 note.
- **`release_jlcpcb/` sync:** none required. Because no emitted-CPL value changes, the current uploaded CPL still matches HEAD after this edit, and the rule *"a design-side fix is not done until the CPL is re-uploaded"* is satisfied vacuously (no fix, only a gate correction). **If** J4 is later resolved by removing its delta, that IS a CPL change and would require re-upload.
- **Other gates:** `verify_easyeda_footprint.py` remains authoritative for the geometric mismatch check and is already consistent with this proposal (U2 `[ALLOW]`, U4 `[OK]`, J4 `[REVIEW]`).

## 5. How the fix is proven

Before the edit (current state):
```
$ python3 scripts/verify_cpl_rotation_law.py; echo "exit=$?"
… U2 FAIL, U4 FAIL, J4 FAIL …
OK: 11   EXCEPTION: 0   FAIL/UNEVALUABLE: 3   NOREF: 0   total: 14
exit=1
```

After applying section 3 to `_LAW_EXCEPTIONS`:
```
$ python3 scripts/verify_cpl_rotation_law.py; echo "exit=$?"
… U2 EXCEPTION (R=90°, drawing-convention), U4 EXCEPTION (R=270°, drawing-convention), J4 FAIL (unresolved) …
OK: 11   EXCEPTION: 2   FAIL/UNEVALUABLE: 1   NOREF: 0   total: 14
exit=1
```

The gate is green for U2 and U4 (residuals match their declared exceptions, so any drift re-triggers the FAIL) and remains red for J4 until visual/photographic evidence of the JLCPCB 3D preview is captured and either:

(a) confirms the pin-1 flip — resolve by moving the exception into `_LAW_EXCEPTIONS["J4"] = (0, "<3D-preview evidence, dated>")`, CPL unchanged; or

(b) refutes it — delete `_JLCPCB_ROT_DELTAS["J4"] = 180` in `scripts/generate_pcb/jlcpcb_export.py`, regenerate CPL, verify the LAW then reports J4 as `OK` at CPL 90°, and re-upload the CPL to JLCPCB (this path is a real CPL change and needs the full `make release-prep` flow).

Verified by the same command in both cases: `python3 scripts/verify_cpl_rotation_law.py` moves from `FAIL/UNEVALUABLE: 3` to `FAIL/UNEVALUABLE: 1` immediately after this edit, and to `0` (exit 0) once J4 is resolved.
