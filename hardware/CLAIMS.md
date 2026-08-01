# Load-bearing claims ledger

Containment layer 2 of `docs/containment-roadmap.md` (closes residual-risk
class 1: right copper, wrong decision). Every geometric gate checks the
board against what we *declared*; when a declaration is wrong, all gates
go green and wrong together — R25 proved it with 24 agreeing gates, the
EN RC network survived 4 releases behind a false "the module has an
internal pull-up" comment. The most dangerous text in this repo is the
justification comment, and this file turns it into a work queue.

Rules (enforced by `scripts/verify_claims_ledger.py`, run by
`make verify-all`):

- Every claim that justifies NOT doing something, or that a gate's model
  rests on, gets an entry here — not only a comment at the site.
- `status` is one of `UNVERIFIED`, `VERIFIED-ON-DATASHEET`,
  `VERIFIED-ON-BENCH`, `FALSIFIED`.
- An `UNVERIFIED` claim older than 45 days turns the gate red: "parked"
  may not silently become "forever".
- A `VERIFIED-*` or `FALSIFIED` claim must cite its evidence; `evidence:
  none` is only legal while `UNVERIFIED`.
- Claims are never deleted. A falsified claim stays as `FALSIFIED` with
  the fix cited — it is the record of why this file exists.

Format: one `## CLAIM-NNN — title` heading per claim, followed by
exactly these `- key: value` fields: `status`, `declared`, `claim`,
`where`, `risk-if-false`, `evidence`.

## CLAIM-001 — MSK12C02 shell is isolated from the slide terminals

- status: UNVERIFIED
- declared: 2026-07-31
- claim: The metal shell/retention tabs of SW16 (MSK12C02 slide switch) are internally isolated from the slide contacts, so net-assigning shell pads 4b/4d to BTN_SELECT is electrically inert.
- where: scripts/generate_pcb/routing/_assemble.py:110 and hardware/datasheet_specs.py:472 (the justification comments); _PAD_NETS SW16 pads 4b/4d
- risk-if-false: BTN_SELECT is GPIO0, a strapping pin, and the shell is exposed metal — a shell tied to the slide contacts puts the boot strap on touchable metal 0.025 mm from a live track. Do NOT just remove the _PAD_NETS entries; verify_trace_through_pad hard-blocks while the overlap exists, so a false claim means rerouting the track.
- evidence: none

## CLAIM-002 — ESP32-S3 module has an internal pull-up on EN

- status: FALSIFIED
- declared: 2026-07-31
- claim: The ESP32-S3-WROOM-1 module provides its own EN pull-up, so no external RC power-up delay network is needed.
- where: the schematic comment that suppressed the EN RC network for 4 releases (removed with the fix)
- risk-if-false: EN rising with no RC delay races the 3V3 rail at power-up — the chip can latch a bad boot state; exactly the class of bug no geometric gate can see.
- evidence: FALSIFIED — the module routes EN out for exactly this external network; R3/C31 added in commit 1c3ded4 and gated by test_strapping_en_rc. Fabricated boards before that commit remain as-built without it.

## CLAIM-003 — USB-C front shield slot 1.60 mm solders despite the datasheet's 1.70 mm

- status: VERIFIED-ON-BENCH
- declared: 2026-07-25
- claim: The C2765186 USB-C front shield THT slot drilled 0.60x1.60 mm (a deliberate 0.10 mm below the datasheet's 1.70) still gives a sound solder joint, buying annular ring on the X axis.
- where: hardware/datasheet_specs.py (USB-C shield THT geometry); DFM constraints in project memory say "do not 'correct' it back"
- risk-if-false: an unsoldered or cracked shield joint loses the connector under cable strain — a field failure, not a bench one.
- evidence: prototype #1 was fabricated with the 1.60 slot and the USB-C soldered correctly (2026-07 build); the rear slot follows the datasheet.
