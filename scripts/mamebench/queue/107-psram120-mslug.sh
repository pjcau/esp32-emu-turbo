# EXPERIMENT: octal PSRAM at 120 MHz (flash 120 MHz SDR), the build of job 105
# otherwise. ESP-IDF calls it experimental: it may not boot, or crash after a
# temperature drift. If mame-go does not come up or panics: hard-reset, the
# launcher still works, reply with the raw serial tail, do not retry. If it runs:
# hashes = reference, and every PSRAM-bound number (68000, sprites, palette,
# clear) should drop. Keep the webcam on it for the whole run.
RG_SDKCONFIG_EXTRA=sdkconfig.psram120 NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 scripts/mamebench/board_run.sh psram120 mslug 70
