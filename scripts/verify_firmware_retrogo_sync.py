#!/usr/bin/env python3
"""Retro-go target ↔ board GPIO sync gate.

Round 30 (hardware-audit-bugs.md) found the shipping emulator firmware's
GPIO map — retro-go/components/retro-go/targets/esp32-emu-turbo/config.h —
contradicting board_config.h on 9 pins (buttons on Octal-PSRAM lines and
on USB D−, SD on the wrong pins, the display driver actively driving the
physical L/R button lines) while NO gate read that file. Every one of
R30-CRIT-1/2, R30-HIGH-2/4, R30-MED-1/2 was the same defect: the target
config lived outside the sync perimeter. This gate closes the class.

Cross-check base is scripts/generate_schematics/config.py::GPIO_NETS —
generate_board_config.py --check already pins that against
software/main/board_config.h, so agreeing with GPIO_NETS is agreeing with
both.

Checks:
  T1  every RG_KEY_* maps to the board's BTN_* GPIO (all 12 buttons)
  T2  MENU is the START|SELECT virtual combo (D1 diode-OR), not a GPIO
  T3  pull-ups: internal only on L (R14 is DNP by design), none elsewhere
  T4  SD SPI pins match SD_MOSI/MISO/CLK/CS
  T5  SD SPI clock is the board-validated 20 MHz, not HIGHSPEED
  T6  audio is the PDM driver on I2S_DOUT; ext/int DAC off; no BCK/WS
  T7  LCD i80 pins match; no RD/BCKL define (RD is a +3V3 hard-tie, the
      backlight is a fixed +5V-via-R27 feed — neither has a GPIO)
  T8  no RG define lands on PSRAM (26-37) or USB (19/20) pins
  T9  every GPIO the target claims exists in GPIO_NETS (i.e. is routed)
  T10 the target sdkconfig sets CPU freq / console / PSRAM mode, IDF5 names
  T11 a generated software/sdkconfig (if present) does not contradict
      sdkconfig.defaults on console/PSRAM — R31-MED-2's stale-file class

Round 31 found the same perimeter hole one file over: this gate read
config.h only, so the target's sdkconfig — handed to the build as
SDKCONFIG_DEFAULTS by rg_tool.py:195, where an unknown symbol is silently
DROPPED and the Kconfig default wins — kept IDF4 symbol names.
R31-HIGH-3: CONFIG_ESP32S3_DEFAULT_CPU_FREQ_* was renamed in IDF 5.0, so
the emulator built at the 160 MHz default, a 33% deficit against the
SNES-at-240 MHz plan. R31-MED-1: no CONFIG_ESP_CONSOLE_* line at all, so
the console fell back to UART0 on GPIO43/44 = SD_MISO/SD_MOSI. T10 asserts
the three settings whose silent absence is invisible in a build log.

Usage: python3 scripts/verify_firmware_retrogo_sync.py
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from generate_schematics.config import GPIO_NETS  # noqa: E402

TARGET_DIR = os.path.join(
    BASE, "retro-go", "components", "retro-go",
    "targets", "esp32-emu-turbo")
CONFIG_H = os.path.join(TARGET_DIR, "config.h")
SDKCONFIG = os.path.join(TARGET_DIR, "sdkconfig")

# Settings the target sdkconfig must carry, with the IDF5 symbol name and
# the consequence of the line going missing. Every one of these is silent
# when absent: the build succeeds and the wrong default ships.
SDKCONFIG_REQUIRED = [
    ("CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ=240",
     "IDF5 CPU freq (the IDF4 CONFIG_ESP32S3_DEFAULT_CPU_FREQ_MHZ name is "
     "dropped silently and the build runs at 160 MHz — R31-HIGH-3)"),
    ("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y",
     "console on USB (the IDF default is UART0 = GPIO43/44 = "
     "SD_MISO/SD_MOSI on this board — R31-MED-1)"),
    ("CONFIG_SPIRAM_MODE_OCT=y",
     "N16R8 PSRAM is Octal; Quad mode leaves the 8 MB unusable"),
]

# IDF4 symbol names that must not come back: renamed in IDF 5.0, so they
# are inert here and read as configuration that is not actually applied.
SDKCONFIG_FORBIDDEN = [
    ("CONFIG_ESP32S3_DEFAULT_CPU_FREQ_", "renamed to CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_*"),
    ("CONFIG_ESP32S3_SPIRAM_SUPPORT", "renamed to CONFIG_SPIRAM"),
]

# RG key -> board net name in GPIO_NETS. MENU is deliberately absent: it
# must NOT have a GPIO (T2 checks the virtual combo instead).
KEY_TO_NET = {
    "RG_KEY_UP": "BTN_UP", "RG_KEY_DOWN": "BTN_DOWN",
    "RG_KEY_LEFT": "BTN_LEFT", "RG_KEY_RIGHT": "BTN_RIGHT",
    "RG_KEY_A": "BTN_A", "RG_KEY_B": "BTN_B",
    "RG_KEY_X": "BTN_X", "RG_KEY_Y": "BTN_Y",
    "RG_KEY_START": "BTN_START", "RG_KEY_SELECT": "BTN_SELECT",
    "RG_KEY_L": "BTN_L", "RG_KEY_R": "BTN_R",
}

# GPIO numbers that must never appear in the target config, and why.
# 26-32: module Octal PSRAM bus; 33-37: module PSRAM data (N16R8);
# 19/20: native USB D-/D+.
FORBIDDEN = {n: "Octal PSRAM" for n in range(26, 38)}
FORBIDDEN.update({19: "USB D-", 20: "USB D+"})

PASS = FAIL = 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def main():
    if not os.path.exists(CONFIG_H):
        print(f"FAIL: {CONFIG_H} missing — is the retro-go submodule checked out?")
        return 1
    src = open(CONFIG_H).read()
    net_to_gpio = {net: gpio for gpio, net in GPIO_NETS.items()}

    # -- parse the gamepad map: {RG_KEY_X, .num = GPIO_NUM_n, .pullup = p, ...}
    keymap = {}   # RG_KEY_* -> (gpio, pullup)
    for m in re.finditer(
            r"\{(RG_KEY_\w+),\s*\.num\s*=\s*GPIO_NUM_(\d+)\s*,"
            r"\s*\.pullup\s*=\s*(\d+)", src):
        keymap[m.group(1)] = (int(m.group(2)), int(m.group(3)))

    # -- parse plain GPIO defines: #define RG_GPIO_X GPIO_NUM_n
    defines = dict(re.findall(r"#define\s+(RG_GPIO_\w+)\s+GPIO_NUM_(\d+)", src))
    defines = {k: int(v) for k, v in defines.items()}

    # -- parse value defines (numeric or symbolic)
    values = dict(re.findall(r"#define\s+(RG_\w+)\s+(\S+)", src))

    print("── T1: 12 buttons on the board's GPIOs ──")
    for key, net in KEY_TO_NET.items():
        want = net_to_gpio.get(net)
        got = keymap.get(key, (None, None))[0]
        check(f"[T1] {key} = GPIO{want} ({net})", got == want,
              f"config.h has GPIO{got}")

    print("── T2: MENU is the D1 diode-OR combo, not a GPIO ──")
    check("[T2] RG_KEY_MENU has no GPIO map entry", "RG_KEY_MENU" not in keymap,
          f"mapped to GPIO{keymap.get('RG_KEY_MENU', (None,))[0]}")
    virt = re.search(
        r"\{RG_KEY_MENU\s*,\s*\.src\s*=\s*RG_KEY_(START|SELECT)\s*\|\s*RG_KEY_(START|SELECT)",
        src)
    check("[T2] VIRT_MAP: MENU = START|SELECT", virt is not None
          and {virt.group(1), virt.group(2)} == {"START", "SELECT"})

    print("── T3: pull-ups (internal only on L — R14 is DNP by design) ──")
    for key, (gpio, pullup) in sorted(keymap.items()):
        want = 1 if key == "RG_KEY_L" else 0
        check(f"[T3] {key} .pullup = {want}", pullup == want,
              f"config.h has {pullup}")

    print("── T4/T5: SD card ──")
    for rg, net in (("RG_GPIO_SDSPI_MISO", "SD_MISO"),
                    ("RG_GPIO_SDSPI_MOSI", "SD_MOSI"),
                    ("RG_GPIO_SDSPI_CLK", "SD_CLK"),
                    ("RG_GPIO_SDSPI_CS", "SD_CS")):
        check(f"[T4] {rg} = GPIO{net_to_gpio[net]} ({net})",
              defines.get(rg) == net_to_gpio[net],
              f"config.h has GPIO{defines.get(rg)}")
    speed = values.get("RG_STORAGE_SDSPI_SPEED", "")
    ok = speed == "SDMMC_FREQ_DEFAULT" or (speed.isdigit() and int(speed) <= 20000)
    check("[T5] SD SPI clock <= 20 MHz (board-validated cap)", ok,
          f"config.h has {speed!r}")

    print("── T6: audio = PDM on I2S_DOUT ──")
    check("[T6] RG_AUDIO_USE_PDM = 1", values.get("RG_AUDIO_USE_PDM") == "1")
    check("[T6] RG_AUDIO_USE_EXT_DAC = 0", values.get("RG_AUDIO_USE_EXT_DAC") == "0")
    check("[T6] RG_AUDIO_USE_INT_DAC = 0", values.get("RG_AUDIO_USE_INT_DAC") == "0")
    check(f"[T6] RG_GPIO_SND_I2S_DATA = GPIO{net_to_gpio['I2S_DOUT']} (I2S_DOUT)",
          defines.get("RG_GPIO_SND_I2S_DATA") == net_to_gpio["I2S_DOUT"],
          f"config.h has GPIO{defines.get('RG_GPIO_SND_I2S_DATA')}")
    for dead in ("RG_GPIO_SND_I2S_BCK", "RG_GPIO_SND_I2S_WS"):
        check(f"[T6] {dead} absent (pins unconnected on the board)",
              dead not in defines, f"defined as GPIO{defines.get(dead)}")

    print("── T7: LCD i80 bus ──")
    lcd = {f"RG_GPIO_LCD_D{i}": f"LCD_D{i}" for i in range(8)}
    lcd.update({"RG_GPIO_LCD_CS": "LCD_CS", "RG_GPIO_LCD_RST": "LCD_RST",
                "RG_GPIO_LCD_DC": "LCD_DC", "RG_GPIO_LCD_WR": "LCD_WR"})
    for rg, net in lcd.items():
        check(f"[T7] {rg} = GPIO{net_to_gpio[net]} ({net})",
              defines.get(rg) == net_to_gpio[net],
              f"config.h has GPIO{defines.get(rg)}")
    for dead, why in (("RG_GPIO_LCD_RD", "panel RD is a +3V3 hard-tie"),
                      ("RG_GPIO_LCD_BCKL", "LED-A is a +3V3 hard-tie")):
        check(f"[T7] {dead} absent ({why})", dead not in defines,
              f"defined as GPIO{defines.get(dead)} — R30-CRIT-2 regression")
    check("[T7] RG_SCREEN_BACKLIGHT = 0 (no PWM path exists)",
          values.get("RG_SCREEN_BACKLIGHT") == "0")

    print("── T8/T9: no forbidden or unrouted pins anywhere ──")
    used = {k: g for k, (g, _p) in keymap.items()}
    used.update(defines)
    for name, gpio in sorted(used.items()):
        if gpio in FORBIDDEN:
            check(f"[T8] {name} not on a forbidden pin", False,
                  f"GPIO{gpio} is {FORBIDDEN[gpio]}")
    check("[T8] no target define on PSRAM/USB pins",
          all(g not in FORBIDDEN for g in used.values()))
    unrouted = {n: g for n, g in used.items() if g not in GPIO_NETS}
    check("[T9] every claimed GPIO is routed (exists in GPIO_NETS)",
          not unrouted, f"unrouted: {unrouted}")

    print("── T10: target sdkconfig (IDF5 symbol names) ──")
    check(f"[T10] {os.path.relpath(SDKCONFIG, BASE)} exists",
          os.path.exists(SDKCONFIG),
          "rg_tool.py only passes SDKCONFIG_DEFAULTS if this file is present "
          "— without it EVERY setting below falls back to the Kconfig default")
    if os.path.exists(SDKCONFIG):
        active = {ln.strip() for ln in open(SDKCONFIG)
                  if ln.strip() and not ln.lstrip().startswith("#")}
        for setting, why in SDKCONFIG_REQUIRED:
            check(f"[T10] {setting}", setting in active,
                  f"MISSING from {os.path.relpath(SDKCONFIG, BASE)} — {why}")
        for relic, renamed_to in SDKCONFIG_FORBIDDEN:
            hits = sorted(s for s in active if s.startswith(relic))
            check(f"[T10] no IDF4 relic {relic}*", not hits,
                  f"{os.path.relpath(SDKCONFIG, BASE)} still has {hits} — "
                  f"{renamed_to}; the IDF4 name is dropped silently, so this "
                  f"line configures NOTHING")

    print("── T11: Phase-1 app generated sdkconfig (R31-MED-2 class) ──")
    # idf.py prefers an existing sdkconfig over sdkconfig.defaults, so a
    # stale generated file silently reverts every defaults-only choice.
    # R31-MED-2: a 2026-02 software/sdkconfig predating the USB-JTAG
    # console fix built the Phase-1 app with the console on UART0 =
    # GPIO43/44 = SD_MISO/SD_MOSI. The file is gitignored, so only a
    # gate that reads the live tree can see it. Absent file = PASS
    # (idf.py regenerates from defaults, which T11 also re-asserts here).
    app_defaults = os.path.join(BASE, "software", "sdkconfig.defaults")
    app_sdkconfig = os.path.join(BASE, "software", "sdkconfig")
    APP_MUST_AGREE = [
        ("CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y",
         "console falls back to UART0 = GPIO43/44 = SD_MISO/SD_MOSI "
         "(R2-MED-3, regressed once as R31-MED-2)"),
        ("CONFIG_SPIRAM_MODE_OCT=y",
         "N16R8 PSRAM is Octal; Quad mode leaves the 8 MB unusable"),
    ]
    defaults_active = {ln.strip() for ln in open(app_defaults)
                       if ln.strip() and not ln.lstrip().startswith("#")}
    for setting, why in APP_MUST_AGREE:
        check(f"[T11] defaults carry {setting}", setting in defaults_active,
              f"MISSING from software/sdkconfig.defaults — {why}")
    if os.path.exists(app_sdkconfig):
        app_active = {ln.strip() for ln in open(app_sdkconfig)
                      if ln.strip() and not ln.lstrip().startswith("#")}
        for setting, why in APP_MUST_AGREE:
            check(f"[T11] generated sdkconfig keeps {setting}",
                  setting in app_active,
                  f"software/sdkconfig (generated, gitignored) contradicts "
                  f"sdkconfig.defaults — {why}. Delete it and let idf.py "
                  f"regenerate")
    else:
        check("[T11] no stale generated software/sdkconfig", True)

    print("=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("STATUS: " + ("PASS — retro-go target agrees with the board"
                        if FAIL == 0 else
                        "FAIL — the shipping firmware disagrees with the copper"))
    print("=" * 60)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
