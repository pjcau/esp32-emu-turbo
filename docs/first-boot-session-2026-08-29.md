# First-boot session log — 2026-08-29 — article 0003 (v4.9.0, W2026081721393881)

Live session log for the staged sequence in
`website/docs/manufacturing/first-boot.md`. Resume point for any machine.

| Stage | Exit criterion | Result | Evidence |
|---|---|---|---|
| 0 pre-flight | board matches renders, both sides | ✅ PASS | `docs/first-article-phaseB-2026-08-29.md` (continuity check skipped — no multimeter, per "as far as your tools allow") |
| 1 USB only | VBUS LED on | ✅ PASS | `hardware/first-article/v4.9.0-W2026081721393881/IMG_5905.jpeg` — VBUS lit with SW16 OFF (rails correctly dark: Q2 gating works) |
| 2 rails | 5V/3V3 LEDs | ✅ PASS | `IMG_5906.jpeg` — SW16 ON: VBUS+5V+3V3 lit, HB dark (chip blank — expected). **Resolves the doc's open question: IP5306 DOES supply 5V batteryless.** CHG+FULL both lit with no cell (undefined-but-harmless, re-check at Stage 4) |
| 3 boot | HB LED 1 Hz + BRINGUP verdict | ⏭️ **NEXT** | firmware built, flash pending |
| 4 battery | boots from cell alone | ☐ | includes C33 wake test (respin watch list) |
| 5 subsystems | blink codes clear one by one | ☐ | SD, LCD, audio checks will FAIL until peripherals attached — normal |

Six LEDs lit = six LED polarities physically confirmed (closes the visible
part of the LED `_PENDING_VALIDATION`; HB polarity confirms at Stage 3).

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
