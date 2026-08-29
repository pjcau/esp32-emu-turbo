# First-boot session log — 2026-08-29 — article 0003 (v4.9.0, W2026081721393881)

Live session log for the staged sequence in
`website/docs/manufacturing/first-boot.md`. Resume point for any machine.

| Stage | Exit criterion | Result | Evidence |
|---|---|---|---|
| 0 pre-flight | board matches renders, both sides | ✅ PASS | `docs/first-article-phaseB-2026-08-29.md` (continuity check skipped — no multimeter, per "as far as your tools allow") |
| 1 USB only | VBUS LED on | ✅ PASS | `hardware/first-article/v4.9.0-W2026081721393881/IMG_5905.jpeg` — VBUS lit with SW16 OFF (rails correctly dark: Q2 gating works) |
| 2 rails | 5V/3V3 LEDs | ✅ PASS | `IMG_5906.jpeg` — SW16 ON: VBUS+5V+3V3 lit, HB dark (chip blank — expected). **Resolves the doc's open question: IP5306 DOES supply 5V batteryless.** CHG+FULL both lit with no cell (undefined-but-harmless, re-check at Stage 4) |
| 3 boot | HB LED 1 Hz + BRINGUP verdict | ✅ PASS | `hardware/first-article/v4.9.0-W2026081721393881/bringup-stage3-serial-2026-08-29.log` — **GREEN, 47 PASS / 0 FAIL / 11 expected SKIP**, reproduced on two consecutive warm resets; HB at 1 Hz confirmed by eye (operator, 2026-08-29). Two latent bring-up firmware bugs found and fixed on the way (see below) |
| 4 battery | boots from cell alone | ☐ | includes C33 wake test (respin watch list) |
| 5 subsystems | blink codes clear one by one | ☐ | SD, LCD, audio checks will FAIL until peripherals attached — normal |

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
