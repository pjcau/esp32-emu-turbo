# Diagnostic LEDs roadmap — visual bring-up without instruments

Date: 2026-08-01 · Decision: user-approved ("un LED per settore" refined
to a two-tier diagnostic tree) · Target: the NEXT fabrication run (the
in-progress JLCPCB v4.4.0 quote is superseded — nothing was paid; the
upload is redone after this lands).

## Why

The user debugs with photos and a multimeter only. The board's historical
dead-board classes (split +3V3 plane, C2 reversed short, U2 rotation
killing the boost, blown protection) all manifest as "a rail is missing" —
and today that diagnosis needs a multimeter on test points. Three passive
LEDs make the power tree photo-diagnosable; one firmware LED extends the
tree to every logic sector via blink codes. GPIO budget makes per-sector
driven LEDs impossible anyway: of the unassigned pins, GPIO26-37 belong
to the module's flash/octal PSRAM — only GPIO15 and GPIO16 are real.

## Design (locked)

| Ref | Net | Tier | Diagnoses |
|---|---|---|---|
| LED3 + R28 | VBUS (post-F1) | passive | USB present, fuse intact |
| LED4 + R29 | +5V | passive | IP5306 boost alive |
| LED5 + R30 | +3V3 | passive | buck alive, rail not shorted, divider sane |
| LED6 + R31 | LED_HB (GPIO15) | driven | boot/straps OK; blink codes per subsystem |

- All four LEDs are **C19171391** — the red 0603 already on the BOM as
  LED1/LED2 (one BOM line, JLC Basic, polarity + rotation law already
  field-proven on this exact package).
- Series resistors sized for ~1 mA (visible indoors, minimal drain);
  prefer values already on the BOM; new values allowed only as Basic
  parts with the value recorded in datasheet_specs.
- Placement: TOP side, near the board edge, grouped and silk-labelled
  (VBUS/5V/3V3/HB) — visible with the case open during bring-up. NO
  enclosure light pipes: these are commissioning LEDs, not user UI.
- **prototype-only / DNP in production**: BOM comment marks them; the
  constant drain (~3-4 mA total) is acceptable on the bench, not in the
  shipped handheld. Footprints stay for rework.
- No LED on BAT+ (constant battery drain; SW16 is not in series —
  permanent invariant, and the respin keeps it that way: Q2 switches the
  +5V load rail, not the cell). BUCK_FB/EN stay multimeter-only via their
  gated test points.
- Heartbeat firmware contract (bringup_test): 1 Hz steady = alive;
  N blinks + pause = subsystem N failed (2=SD, 3=display, 4=audio,
  5=buttons, 6=PSRAM) — telemetry stays the rich channel, the LED is
  the cable-free fallback.

## Workstreams

- **H (pcb-engineer)**: config GPIO15->LED_HB · schematic (power sheet:
  LED3-5; MCU sheet: LED6) · board placements + routing · BOM/CPL ·
  vbench models + datasheet_specs (each rail sees ~1 mA extra — declare
  it, rails/thermal read it) · full pipeline green · release regen +
  order manifest.
- **F (software-dev)**: board_config.h sync (generated) · heartbeat task
  + blink-code map in software/bringup_test · docs of the code table.
- **D (coordinator)**: this roadmap · website docs (new
  `website/docs/debug/diagnostic-leds.md` + links from bring-up/rework
  pages, BOM docs regen) · verify-all + injection audit · commit(s) ·
  release/tag decision with the user · JLC re-upload afterwards.

## Landing rules

Same iron rules as the gate-coverage expansion: every gate green in the
same commit (94-gate suite incl. enclosure-sync), six-file chain + vbench
in one commit, release_jlcpcb + `make order-manifest` in that commit,
`make repo-map`, no tag without the user's word.


## RESUME CHECKLIST — session paused 2026-08-01 (~14:00)

State at the WIP push (branch `worktree-diag-leds`, NOT merged to main):

DONE and verified:
- Firmware (workstream F): heartbeat + blink codes in the bringup_test
  GENERATOR, both build branches compiled via Docker, fast-flutter for
  uncovered failures (approved), `BRINGUP-LED` telemetry line.
  Active-high assumption: GPIO15 -> R31 -> LED6 anode, cathode to GND
  (`HB_LED_ACTIVE_LEVEL 1`) — MUST be cross-checked on the schematic.
- Docs: this roadmap · website/docs/rework/diagnostic-leds.md ·
  website/docs/manufacturing/first-boot.md (staged session, battery
  last) · bring-up-protocol.md (58 checks + BRINGUP-LED + links) ·
  short-test-multimeter.md (historical banner, T15 caps fixed,
  section F superseded by first-boot) · hardware-test-gen SKILL 58.

IN FLIGHT at push time — hardware (workstream H, agent ws-led-hw):
config GPIO15->LED_HB done, LED3-6+R28-31 in schematic/board/CPL/BOM,
datasheet_specs touched; regeneration + gate pass was still running.
The WIP commit may hold a TORN hardware state — trust nothing until
re-verified.

Resume sequence (any future session):
1. `git worktree list` / re-enter or recreate from branch
   `worktree-diag-leds`; `git submodule update --init retro-go`.
2. Assess the hardware state DIRECTLY from the tree (agent transcripts
   are machine-local and will not exist on another PC): `git log --stat`,
   `grep LED_HB scripts/generate_schematics/config.py`,
   `grep -c LED hardware/kicad/jlcpcb/cpl.csv` (expect 6),
   `git status` for anything half-regenerated.
3. `make generate-pcb` + zone fill + `python3 -m
   scripts.generate_schematics hardware/kicad` to converge generation.
4. Cross-check LED6 polarity on the schematic = ACTIVE HIGH (see above).
5. `make firmware-sync-check` + `make bringup-check` (LED_HB define
   must now exist; the `led.heartbeat` check flips from SKIP to real).
6. `python3 scripts/verify_dfa.py` · `make verify-all` (baseline 93 +
   any suites main gained meanwhile) · fix causes, never waivers.
7. Release regen: `make export-gerbers-fast`, sync release_jlcpcb/
   (incl. nested mirror), `make render-pcb`, `make order-manifest`.
8. `make repo-map` · full injection audit
   (`python3 scripts/verify_gate_coverage.py`) — all faults by owner.
9. Squash/commit properly (replace the WIP commit if desired), merge
   origin/main into the branch, push, merge to main.
10. THEN, per the user's explicit sequencing: tag (proposed v4.5.0) +
    GitHub Release (their scheme: next is v3.1) + JLCPCB re-upload
    from release_jlcpcb/ with /first-article-check phase A, STOP
    before payment. The old half-done JLC quote is superseded.
