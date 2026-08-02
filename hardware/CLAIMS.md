# Load-bearing claims ledger

Containment layer 2 of `docs/archived/containment-roadmap.md` (closes residual-risk
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

- status: VERIFIED-ON-DATASHEET
- declared: 2026-07-31
- claim: The metal shell/retention tabs of SW16 (MSK12C02 slide switch) are internally isolated from the slide contacts, so net-assigning shell pads 4b/4d to BTN_SELECT is electrically inert.
- where: scripts/generate_pcb/routing/_assemble.py:110 and hardware/datasheet_specs.py:472 (the justification comments); _PAD_NETS SW16 pads 4b/4d
- risk-if-false: BTN_SELECT is GPIO0, a strapping pin, and the shell is exposed metal — a shell tied to the slide contacts puts the boot strap on touchable metal 0.025 mm from a live track. Do NOT just remove the _PAD_NETS entries; verify_trace_through_pad hard-blocks while the overlap exists, so a false claim means rerouting the track.
- evidence: VERIFIED 2026-08-02 against hardware/datasheets/SW16_Slide-Switch_C431540.pdf (Shenzhen Shouhan, MSK12C02, spec version A/0, 2015-03-26 — the datasheet is for MSK12C02, so footprints.py's "C431540 = MSK12C02, not SS-12D00G3" comment is right and the SS-12D00G3 dict key is a legacy alias). Two independent statements, both explicit. (1) PDF page 4 (printed "Page 2/8") section 3.2, Insulation Resistance: "Measurement shall be made following application of 100V DC potential, **across terminals, and across terminals and cover**, for one minute" — requirement ≥100 MΩ; repeated in technical note 2 of the outline drawing (PDF page 1) as "绝缘电阻100MΩmin, 100V DC". Section 3.3 adds 250 V AC dielectric withstand across terminals for 1 min with no breakdown. (2) The manufacturer's own circuit diagram (电路图, PDF page 1) draws terminals (1)(2)(3) as the slide contact strip and terminal (4) as a SEPARATE node carrying an earth symbol, joined to nothing — and the mounting reference view (安装参考图) labels all four corner anchor pads (4). The parts list confirms cover and base are distinct parts (6 盖板/cover, phosphor bronze 0.2 mm silver-plated; 2 底座/base, LCP). Residual worth knowing, and NOT part of this claim: the manufacturer draws terminal (4) with an earth symbol, i.e. the cover is intended to be grounded. This board ties 4b/4d to BTN_SELECT instead, which is inert for the switch but does leave GPIO0 reachable through exposed metal — an ESD path, not a short.

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

## CLAIM-004 — VBUS needs no discrete surge TVS on the v1 prototype

- status: VERIFIED-ON-DATASHEET
- declared: 2026-08-01
- claim: VBUS carries no surge-rated TVS (SMF5.0A class) by decision. U4's (USBLC6-2SC6) VBUS pin provides the rail's IEC 61000-4-2 ESD clamp, and the only VBUS source is a current-limited USB-C supply behind fuse F1, so the remaining 8/20 us surge class is accepted for the v1 prototype. v2/production should add a discrete surge TVS at J1.
- where: scripts/verify_esd_protection.py (the surge-TVS check reads this claim); J1 / U4 / F1 on the board
- risk-if-false: a surge event on VBUS (hot-plug overshoot into an inductive cable, non-compliant charger) exceeds U4's ESD-clamp energy rating and kills U4 and/or U2 — a field failure the bench never sees.
- evidence: USBLC6-2SC6 datasheet (ST, DS5814) — the VBUS pin clamp is specified for IEC 61000-4-2 ESD transients, not 8/20 us surge; F1 (landed in 1c3ded4) limits fault current on VBUS_IN; the supply is a consumer USB-C PSU, not an automotive/industrial rail.

## CLAIM-005 — IP5306 delivers stable VOUT from VIN with no battery cell attached

- status: UNVERIFIED
- declared: 2026-08-01
- claim: With USB power on VIN and NO cell on the BAT pin, the IP5306 passes power through to VOUT stably enough to run the whole board (ESP32 + display + SD), so the bring-up procedure may run USB-only and defer the battery to last. The datasheet (Chinese, C181692) does not document the no-battery case; power-bank ICs of this class are known to sometimes hiccup or gate VOUT off when the charger finds no cell.
- where: the bring-up order in website/docs/manufacturing/bring-up-protocol.md (USB first, battery last — rests on this claim); the charge-and-play power path in website/docs/design/schematics.md
- risk-if-false: first power-on without a battery yields a dead or flickering +5V and the bring-up telemetry reads as a broken board — hours lost chasing a phantom fault, or worse, a battery hot-plugged onto an unproven board to "fix" it, which is exactly what the procedure forbids.
- evidence: none (verification is free: first USB-only power-on with the bring-up firmware's brownout telemetry settles it either way — stable rails → VERIFIED-ON-BENCH; no/unstable VOUT → FALSIFIED and the battery becomes a bring-up prerequisite)

## CLAIM-006 — the TF-01A's Cd contact does not ground BTN_R when a card is inserted

- status: UNVERIFIED
- declared: 2026-08-02
- claim: U6 pad 9 is the socket's own card-detect contact ("Cd" on the TF-01A drawing, not DAT2 and not NC), and it carries the BTN_R net because the BTN_R track crosses it. The claim is that this is electrically inert — i.e. the Cd blade does NOT short to the socket shell (GND, pads 10/12) when a card is inserted, so BTN_R stays free to read the R shoulder button with a card in the socket.
- where: hardware/datasheet_specs.py::U6 pin 9 and scripts/generate_pcb/routing/_assemble.py (_PAD_NETS[("U6","9")] = BTN_R); scripts/vbench/sdcard.py; the sd.cmd0 skip text in software/bringup_test/
- risk-if-false: if the Cd blade is shell-referenced and closes on insertion, BTN_R sits at GND whenever a card is in the socket and the R shoulder button is dead in every game — a functional defect no geometric gate can see, since the short is inside the component. Boot is NOT at risk: GPIO3's strap selects the JTAG source and is ignored unless EFUSE_STRAP_JTAG_SEL is burned (module datasheet table 8, p.15), which the factory default leaves unselected. Do not "fix" this by deleting the _PAD_NETS entry — verify_trace_through_pad hard-blocks while the overlap exists, so a false claim means rerouting BTN_R away from pad 9.
- evidence: none. What IS established from U6_TF-01A_MicroSD_C91145.pdf p.1: the "PCB Layout (Pattern Side)" view labels the pad row (1)(2)(3)(4)(5)(6)(7)(8) then **Cd**, and the parts list is shell x1 / spring x1 / contact x9 / housing x1 — so pad 9 is a socket contact, and a microSD card (eight contacts) can never drive it. What is NOT in that document: any schematic, switch symbol or normally-open/normally-closed statement for Cd, hence this claim. Verification is free and needs no instruments — read BTN_R with the socket empty and then with a known-good card inserted (procedure in website/docs/manufacturing/bring-up-protocol.md): stays HIGH → VERIFIED-ON-BENCH; goes LOW → FALSIFIED and pad 9 becomes a respin item.
