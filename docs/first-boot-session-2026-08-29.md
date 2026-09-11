# First-boot session log — 2026-08-29 — article 0003 (v4.9.0, W2026081721393881)

Live session log for the staged sequence in
`website/docs/manufacturing/first-boot.md`. Resume point for any machine.

| Stage | Exit criterion | Result | Evidence |
|---|---|---|---|
| 0 pre-flight | board matches renders, both sides | ✅ PASS | `docs/first-article-phaseB-2026-08-29.md` (continuity check skipped — no multimeter, per "as far as your tools allow") |
| 1 USB only | VBUS LED on | ✅ PASS | `hardware/first-article/v4.9.0-W2026081721393881/IMG_5905.jpeg` — VBUS lit with SW16 OFF (rails correctly dark: Q2 gating works) |
| 2 rails | 5V/3V3 LEDs | ✅ PASS | `IMG_5906.jpeg` — SW16 ON: VBUS+5V+3V3 lit, HB dark (chip blank — expected). **Resolves the doc's open question: IP5306 DOES supply 5V batteryless.** CHG+FULL both lit with no cell (undefined-but-harmless, re-check at Stage 4) |
| 3 boot | HB LED 1 Hz + BRINGUP verdict | ✅ PASS | `hardware/first-article/v4.9.0-W2026081721393881/bringup-stage3-serial-2026-08-29.log` — **GREEN, 47 PASS / 0 FAIL / 11 expected SKIP**, reproduced on two consecutive warm resets; HB at 1 Hz confirmed by eye (operator, 2026-08-29). Two latent bring-up firmware bugs found and fixed on the way (see below) |
| 4 battery | boots from cell alone | ⏸️ DEFERRED | no cell on hand (2026-08-29) — C33 wake test stays on the respin watch list |
| 5 subsystems | blink codes clear one by one | ✅ PASS (SD, LCD, audio) | **SD: PASS** — `bringup-stage5-sd-serial-2026-08-29.log`, GREEN 52/0/6 with a 16GB card: full chain incl. FAT mount at 20 MHz. (A no-name 128GB card was rejected at CMD59/CRC_ON_OFF by the IDF driver on every try incl. freshly powered — card-side fault, do not use it.) **LCD: PASS (2026-09-11)** — `bringup-stage5-lcd-serial-2026-09-11.log`, GREEN 53/0/6 with the panel on the R37 workaround (40P extension board + type-B FFC): `lcd.data.risetime` 1000–1200 ns on all of D0–D7 (was ~200 ns unloaded), 8 colour bars confirmed by eye in the documented order, then the black/white load-test fills; no 3V3 event. R37-HIGH-1 stays open only as the v2 top-contact J4 item. **Audio: PASS (operator-confirmed)** — speaker soldered, 3×1 kHz beep pattern clearly recognizable over the R38 carrier hiss (test tone reworked for it; channel now silenced after the check). Clean audio deferred to the R38 v2 fix. Nothing remaining at stage 5 |

## R37-HIGH-1 — J4 contact face is inverted for the purchased panel (found at first article, 2026-08-29)

The purchased panel (marked **LHC400IT005-9488**, ILI9488, 40P 0.5 mm,
separate 4-wire resistive-touch tail left unconnected) carries its tail
contacts on the **opposite face** from what J4 expects. J4 (FPC-05F-NPH20,
C2856812) is a flip-lock **bottom-contact** ("翻盖下接") connector, and its
mouth faces the FPC slot, so the ribbon's entry direction is fixed —
which locks contact-face and pin-order parity together: **no fold or
twist can give "contacts toward PCB + pin 40 on pad 1" at the same
time.** Confirmed on the bench both ways: contacts-up = correct 41−N
order but zero contact (rise-time probe flat at ~200 ns, backlight dark);
flipped = contact but mirrored order → **+3V3 rail collapse** (panel GND
onto 3V3 — operator cut power immediately, board unharmed, next runs
GREEN).

- **First-article workaround**: 40P 0.5 mm FPC extension adapter board +
  **type-B ("opposite side") FFC cable**, as short as possible (3-5 cm —
  the 8080 bus runs at 20 MHz). Type A does not invert; do not use it.
- **v2 fix**: change J4 to the **top-contact** variant of the same
  connector family ("翻盖上接", same footprint) — inverts the face,
  keeps the routed 41−N order, no adapter needed.
- New bring-up check `lcd.data.risetime` (added this session) is the
  no-multimeter contact probe: ~200 ns = panel not loading the data
  lines; a seated panel must slow every line.

## R38-MED-1 — no PDM reconstruction filter in the audio path (found at first article, 2026-08-29)

Speaker soldered (SPK+/SPK− pads, BTL) and the 440 Hz bring-up tone IS
audible — the chain GPIO17 → C22 → PAM8403 → speaker is electrically
alive — but it sounds like a loud fan-like hiss with a faint tone under
it, and cutting the tone amplitude −12 dB did not reduce the hiss:
**the PDM carrier dominates**. Root cause: the board has NO low-pass
between the PDM pin and the amplifier input — C22 is a series DC-block
(a high-pass), and the `audio.c` comment claiming the "existing RC
network acts as a low-pass filter" was wrong (there is no shunt element).
The full-swing MHz PDM stream drives the PAM8403 input directly.

- **v2 fix**: series R (~1k) + shunt C (~10 nF) between C22 and
  PAM_IN_AC — or moot entirely under the planned v2 audio coprocessor
  with a true I2S DAC.
- **First-article rework (optional, fiddly)**: requires inserting a
  series element — deferred unless audio testing needs it.
- Firmware mitigation this session: the bring-up suite now calls
  `audio_stop()` after the audio checks — an enabled-but-idle PDM
  channel emits its 50%-density carrier continuously, which was a
  constant hiss for as long as the board stayed on.
- `audio.audible` verdict: chain alive = the check's purpose met;
  fidelity is R38's problem, not the board assembly's.

## Session close (2026-08-29 evening)

Final board state: **BRINGUP GREEN 53/0/6, HB steady at 1 Hz,
operator-verified.** LED legend learned on the bench: 10-blinks/s
flutter + 1 s pause = "failure with no code", in practice almost always
`bringup.previous_run` after a capture-harness reset killed a run
mid-flight — one clean run (or SW16 power-cycle) clears it; a flutter
that survives a power-cycle would be a real failure.

Resume points, in arrival order:
1. ~~**~2026-09-12** — type-B FFC adapter arrives → LCD retry~~ **DONE
   2026-09-11, PASS** — see "LCD retry" below.
2. Battery cell → stage 4 (LIVE operation, C33 wake test).
3. v2 backlog from today: R37 (top-contact J4), R38 (PDM RC filter),
   plus a +/− silkscreen for the SPK pads.

## LCD retry (2026-09-11) — R37-HIGH-1 workaround validated, stage 5 complete

Parts arrived: 40P 0.5 mm FPC extension board + type-B ("opposite side")
FFC, operator-verified as type B (contacts on opposite faces at the two
ends) and kept short. Chain: panel tail → extension board → type-B FFC →
J4, pin 40 toward the "LCD" silk. Powered from USB, 3V3 LED steady.

Operator observation at power-up: panel white (backlight on, panel not
yet initialised — normal), then **8 vertical colour bars** in the
documented order, then the slow black and white full-screen wipes of
`power.load` (each `display_fill` takes ~1.5 s while both cores are
saturated by the load tasks — 2 fills in 3 s — so the wipes read as a
"curtain"; not a panel symptom), ending on white. HB 1 Hz throughout.

Serial: `bringup-stage5-lcd-serial-2026-09-11.log`, **GREEN 53/0/6**,
`bringup.previous_run` clean (reset=11). The contact probe that was
flat at ~200 ns in August now reads **D0–D3 = 1000 ns, D4–D7 = 1200 ns**
— every data line is loaded by the panel, which with the bars by eye
closes the only LCD check the firmware cannot make itself
(`lcd.panel.readback` is SKIP by design, LCD_RD tied HIGH).

Capture recipe used (same as August, now as a one-shot script): open the
port with DTR=RTS=1 (no reset on open), drain 12 s, one esptool-style
reset (DTR low → RTS high 0.2 s → RTS low), read until a line starting
with `BRINGUP-END`.

Stage 5 is therefore complete on article 0003: SD, LCD and audio all
PASS. Still open on the board: stage 4 (battery — no cell yet). The v2
backlog is unchanged: R37 top-contact J4 (the adapter is a first-article
workaround, not a fix), R38 PDM RC filter, SPK +/− silkscreen.

All seven LED polarities are now physically confirmed (HB beating at 1 Hz
at Stage 3 closed the last one) — the LED `_PENDING_VALIDATION` is fully
closed.

## Stage 3 — how to flash (machine-specific)

Binaries are reproducible from the repo: `make bringup-build` (Docker;
`bringup-check` must stay green). Flash offsets (from
`software/bringup_test/build/flasher_args.json`): `0x0` bootloader,
`0x8000` partition-table, `0x20000` app; DIO, 80 MHz, 16 MB.

- **Linux**: `make bringup-flash` works natively (Docker maps the port).
  The blank S3's USB-Serial-JTAG enumerates as **`/dev/ttyACM0`**, not
  ttyUSB0 — run `ESP_PORT=/dev/ttyACM0 make bringup-flash`.
- **macOS**: Docker cannot pass USB through — flash with local esptool
  (`pip3 install --user esptool`), port `/dev/cu.usbmodem*`:
  `python3 -m esptool --chip esp32s3 -p /dev/cu.usbmodem* -b 460800 \
   write_flash --flash_mode dio --flash_freq 80m --flash_size 16MB \
   0x0 build/bootloader/bootloader.bin 0x8000 build/partition_table/partition-table.bin \
   0x20000 build/esp32-emu-turbo-bringup.bin` (from `software/bringup_test/`).

Board prerequisites for flashing: **USB-C to the computer, SW16 ON** (with
the switch OFF there is no +3V3 and the chip never enumerates). Flash is
factory-blank so the ROM enters download mode by itself; after the first
flash, reset (replug) and expect HB at 1 Hz + the 58-check serial report at
115200 baud (`BRINGUP-SUMMARY` / `BRINGUP-LED` lines are the verdict).

## Stage 3 findings (2026-08-29) — two firmware bugs, zero board defects

Both bugs lived in the bring-up firmware itself and produced false RED
verdicts on a healthy board; both fixed in `generate.py` and re-verified:

1. **`bringup.previous_run` self-poisoning** — `run_check()` stamps the
   crash-forensics marker with the check's own id *before* running it, so
   check 01 read its own freshly-written marker instead of the previous
   run's, and failed on every warm (USB) reset by construction. It only
   ever passed on a true power-on, which is why the doc's "replug" flow
   never showed it. Fix: snapshot the marker in `app_main()` before the
   first `run_check()`.
2. **`usb.serial_jtag` FIFO race** — the check sampled
   `usb_serial_jtag_ll_txfifo_writable()` once, while the report itself
   was filling that FIFO; whenever the host's read cadence left the FIFO
   momentarily full, a live link was reported dead. Fix: poll up to 50 ms
   (an attached host drains it in microseconds).

Capture-harness gotchas for any future machine (all reproduced here):
- **Any DTR/RTS edge on the port resets the chip** (USB-Serial-JTAG reset
  logic; `rst:0x15 USB_UART_CHIP_RESET`): Linux cdc-acm raises DTR on
  open, drops it on close — so `stty`+`cat`, idf_monitor attach, or a
  pyserial open/close each reboot the board mid-run.
- To capture a clean full run: open the port plainly (lines settle at
  DTR=RTS=1, no reset), wait ~12 s for any in-flight run to finish, then
  do one esptool-style reset (DTR low → RTS high 0.2 s → RTS low) and
  read to `BRINGUP-END` while draining continuously.
- Grep for `BRINGUP-END` at start-of-line only: check 01's PASS detail
  contains the literal string "reached BRINGUP-END".

## Retro-Go first boot (2026-09-11) — Phase 2.8 reached, R39-HIGH-1 found

Retro-Go (fork, target `esp32-emu-turbo`) built from the submodule and
flashed as a full image (`rg_tool.py install` at 0x0 — `make
retro-go-flash` cannot be the first flash: it writes per-partition and
the board still carried the bring-up partition table). Card: the 16 GB
SD, FAT32, `roms/<system>/` with the free test ROMs from `test-roms/`.
Four firmware findings, all fixed in the fork (commit 0e533078 +
follow-ups) — none is a board defect:

1. **Half-drawn windows.** `rg_display` streams a window as 4-line DMA
   chunks and the IDF i80 IO sends a command with every chunk; the driver
   sent 0x2C each time, which resets the write pointer to the window
   origin, so only the first 4 rows of every rectangle were written (half
   glyphs, stale rows from the previous image). Fix: 0x2C on the first
   chunk after `set_window`, 0x3C (Memory Write Continue) after. The
   bring-up never showed it because `esp_lcd` sends a whole bitmap in one
   0x2C.
2. **Portrait target on a landscape handheld.** The panel sits along the
   board's long axis (D-pad left, ABXY right); the target was 320x480
   portrait. Now 480x320, MADCTL 0x28 — operator-confirmed upright with
   the clusters on the correct sides. The docs' "2x vertical" scaling
   plan is void (see Phase 2 docs).
3. **PDM carrier hiss in the launcher.** With no reconstruction filter
   (R38) an enabled PDM channel is a loud hiss even on zero samples.
   `pdm.c` now keeps the channel disabled while muted or at volume 0
   (time-paced like the dummy driver) and this target starts at volume 0
   (`RG_AUDIO_DEFAULT_VOLUME`, generic default 50 unchanged).
4. **R39-HIGH-1 — module pins 38/39 swapped in every project table.**
   Symptom: D-pad RIGHT opened the game menu (the A action) and A did
   nothing. The WROOM-1 datasheet on disk (`hardware/datasheets/U1_…pdf`,
   "Pin Definitions") has **pin 38 = IO2, pin 39 = IO1**; `_PIN_TO_GPIO`,
   `datasheet_specs.py`, the schematic symbol/pin table, `board_config.h`
   and the Retro-Go target all had 38=GPIO1/39=GPIO2, and the gate
   `Pin 38 = GPIO1` asserted the wrong fact (a table copied into its own
   check). Pins 4-37 verified against the datasheet: only this pair.
   **The copper is right**: BTN_RIGHT lands on pad 38 = GPIO2, BTN_A on
   pad 39 = GPIO1 — so the fix is names only: `BTN_RIGHT=GPIO2`,
   `BTN_A=GPIO1` in board_config.h / config.py / Retro-Go target, tables
   and symbol corrected, gate now asserts 38=GPIO2 and 39=GPIO1. The
   regenerated PCB is byte-identical to the built board. Bring-up
   firmware regenerated (its 2026-09-11 log predates the rename: its
   `btn.RIGHT` lines really exercised GPIO1 = the A button, and vice
   versa — idle/pull checks only, verdict unaffected).

Result: launcher usable (L/R added as system prev/next), all 12 buttons
operator-verified in the launcher, **Owlia (NES) launched and played** —
Phase 2.8 done on free homebrew; Super Mario Bros is the user's own copy,
kept out of git (`.gitignore` now ignores every ROM under `test-roms/`
except the committed homebrew set).
