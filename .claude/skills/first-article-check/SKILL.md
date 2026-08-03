---
name: first-article-check
description: Pre-payment and first-article inspection protocol — verify orientation per package FAMILY on the JLC 3D preview before paying, and photo-vs-render per side when boards arrive. Formalizes the v4.3.1 systemic-rotation lesson.
argument-hint: [pre-order | arrival]
---

# First-Article Check — orientation containment at the two moments that matter

Containment layer 4 of `docs/archived/containment-roadmap.md` (closes residual-risk
class 2: assembly conventions). The v4.3.1 batch shipped with **at least 8
bottom-side parts seated 90° off their pads** from a syntactically perfect
CPL — JLC placed exactly what the file said, no vision correction. Every
geometric gate was green. The two moments a human (or a photo) can still
catch this are **before paying** and **when the boards arrive**. This skill
is the checklist for both.

Ground truth for method: `website/docs/rework/incident-v431-rotations.md`
and memory `feedback_photo_pixel_estimates_unreliable`.

## Non-negotiable principles

1. **Sweep by package FAMILY, never by component.** When one SOT-23-5 is
   misrotated, every SOT-23-5 placed from the same convention is suspect.
   v4.3.1's error was systemic (one wrong frame → 8 parts); a per-component
   check reads each part in isolation and misses the pattern.
2. **Judge orientation by body-vs-pad contradiction, not by eye.** A part is
   wrong when its terminals do not land on its pads' long axis — never
   estimate angles from photo pixels ("looks like 45°" was wrong twice).
3. **Identify parts by unique context** (neighbors, silk, connectors),
   locate by landmarks. Reference designators may be unreadable in photos.
4. **Never fix a rotation in JLC's online editor** — the CPL in
   `release_jlcpcb/` is the only source of truth; fix there, re-verify,
   re-upload (memory: `feedback_upload_only_with_release`).

## Phase A — pre-order (before paying, on the JLC order preview)

Run with the order preview open side by side with our renders
(`release_jlcpcb/renders/`, regenerate with `/pcba-render` if stale).

1. `make verify-all` green at the release tag, `release_jlcpcb/` synced at
   HEAD, `make order-manifest` fresh — record the three SHA256s in the
   release notes. If any of this fails, STOP: do not upload.
2. In the JLC 3D/2D viewer, check **every package family** on **each side**,
   bottom side first (that is where v4.3.1 failed). Family checklist:
   - **ICs with pin-1 marks** (SOP/SOIC/QFN — U2, U3, U5…): dot/bevel on
     the same corner as the render; body long axis parallel to the pad rows.
   - **SOT-23-x** (regulators, transistors — Q1…): 2-pin side vs 1-pin
     side must match the pad pattern, not just "roughly aligned".
   - **Polarized 2-terminal** (diodes, tantalum — D1, C2 class): cathode
     band / polarity stripe on the same end as the render AND as
     `hardware/datasheets/POLARITY_AUDIT.md` — do not re-derive polarity.
   - **Inductors with directional marking** (L1): marking axis matches.
   - **Connectors/switches** (USB-C, SD, JST, MSK12C02): keying and pin 1
     against the render.
   - **MLCC/resistor arrays**: spot-check that the family sits along, not
     across, its pads.
3. Any single mismatch → sweep that part's whole family, then STOP the
   order and open `/fix-rotation` for the ref. The fix lands in the
   generator/CPL, goes through `make verify-all`, and produces a NEW
   upload — never an online-editor touch-up.
4. Only after every family passes: pay, and record order number + manifest
   hashes together.

## Phase B — arrival (first article, photos only)

Assume no bench instruments (project constraint): photos are the
telemetry, the bring-up firmware is the multimeter (roadmap layer 5).

1. Photograph both sides square-on, good light, before any power-up.
2. Compare photo vs render **per side, per package family** with the same
   checklist as Phase A. The top side being perfect does NOT clear the
   bottom side — on v4.3.1 the top was flawless and the bottom was not.
3. Check the known polarity-critical parts against
   `hardware/datasheets/POLARITY_AUDIT.md` explicitly (C2's reversed
   stripe was visible in a photo before the 0 Ω short was measured).
4. Any body-vs-pad contradiction → do NOT power the board. Document with a
   close-up photo, record in `website/docs/rework/` (pattern:
   `incident-v431-rotations.md`), and decide rework vs write-off.
5. If all families pass: first power-up follows the bring-up protocol
   (`/hardware-test-gen` firmware when available), lowest-current supply
   first.
6. **Respin watch list** — three readings that no gate can settle, so the
   first article is the only place they get answered. All three need
   nothing but the board, which is the point:
   - **C33 wake RC** (`PWR_SW` → `IP5306_KEY`). The one BENCH-VALIDATE
     value in the design: its pulse runs against the IP5306's
     *undocumented* internal KEY pull-up, so 1 µF is a starting guess.
     Test: USB out, SW16 OFF for a full minute (that guarantees the 32 s
     light-load shutdown has fired), then ON. The board must come back up
     on the cell alone. If it only starts when USB is plugged in, the
     pulse is too short → larger C33. To separate "pulse too short" from
     "wake path dead", fit **SW17** — the do-not-place momentary beside
     C33 on the KEY node, C720477 — and press it.
   - **Q1 orientation** (CLAIM-006). Visual, not electrical: SOT-23's
     2+1 lead pattern is not 180°-symmetric, so a wrongly-rotated Q1
     cannot seat on the lands. Confirm on the Phase A preview and again
     in the arrival photo.
   - **U3 `BUCK_FB` = 0.600 V**, the buck's own reference showing the
     divider is doing what `R25/R26` say it does.
   Batch them: they are one trip to the board, and the C33 result is what
   decides whether SW17 has to be populated on the next build.

## Output

A short report: families checked per side, verdict each, photos/screenshots
referenced, and — pre-order — the manifest hashes that the paid order
corresponds to. "Checked" without the per-family list is not a pass.
