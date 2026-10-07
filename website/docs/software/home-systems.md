---
id: home-systems
title: Atari 5200 / 7800, Commodore 64, MSX
sidebar_position: 3
---

# Atari 5200 / 7800, Commodore 64, MSX

Asked by the user on 2026-10-07: emulators for the Atari 5200, the Atari 7800,
the Commodore 64 and the MSX 1/2 that weigh little and play with the
handheld's buttons. Amiga was asked too; see [Amiga](#amiga) for why it is not
in this round.

:::info On the board since 2026-10-07
Flashed on 2026-10-07 (fork branch `home-computers`, `fmsx` from 97ae8890 /
9543588b, `retro-home` from 23934129) and checked with the webcam and the
serial console:

| System | Game checked | Result |
|---|---|---|
| MSX 1 | Nemesis | ✅ runs, keys work, 61 fps, core 21–26 % busy |
| MSX 2 | Metal Gear 2 | ✅ runs (Konami logo, title) with the real MSX2 BIOS pair |
| Atari 5200 | Galaxian, Pole Position, Space Invaders | ✅ all three in play, 60 fps, 33 % busy |
| Commodore 64 | Ghostbusters (.d64) | ✅ loads by itself to the title, 50 fps (PAL), 70 % busy |
| Atari 7800 | Donkey Kong | ⚠️ plays, keys work, but **42 fps of 60**: the MARIA display chip takes 17.1 ms of a 23.7 ms frame, the 6502 6.5 ms |

The first round found three faults, all fixed on the branch: the 5200 loader
overflowed a 64-byte log buffer with the cartridge's path (crashes or a jump
into zero page), fMSX quit when `MSX2.ROM` was missing (it now starts as an
MSX1), and the 7800 looked only for the US BIOS file (it takes either now).
The 7800's speed is the open item.

BIOS files used for the check (none is in any repository): MSX `MSX.ROM` =
Sharp HotBit 1.1, `MSX2.ROM` + `MSX2EXT.ROM` = MSX System v2.1 (a matching
pair: C-BIOS's `MSX2.ROM` with the real `MSX2EXT.ROM` gives a black screen),
`DISK.ROM`; Atari `5200.rom` (US), `7800 BIOS (E).rom`; C64 KERNAL 901227-03,
BASIC 901226-01, CHARGEN 901225-01. The C64GS KERNAL (390852-01, 16 KB) is not
a C64 KERNAL and does not work.
:::

## Where each one lives

| System | Launcher tab | Emulator | App (partition) | Size |
|:---|:---|:---|:---|:---|
| Atari 5200 | Atari 5200 (`a52`) | Atari800 core, as cut down for microcontrollers by [MCUME](https://github.com/Jean-MarcHarvengt/MCUME) | `retro-home` | 677 KB for the three |
| Atari 7800 | Atari 7800 (`a78`) | [ProSystem](https://github.com/libretro/prosystem-libretro) (Greg Stanton), the libretro core | `retro-home` | |
| Commodore 64 | Commodore 64 (`c64`) | Teensy64 (Frank Bösing), the ESP32 version in MCUME, with Dag Lem's reSID for the sound | `retro-home` | |
| MSX 1 / 2 / 2+ | MSX (`msx`) | [fMSX](https://fms.komkon.org/fMSX/) (Marat Fayzullin) | `fmsx` | 654 KB |

`retro-home` is one app for the three: the launcher starts it with the tab's
name and it runs the matching emulator, as `retro-core` does for the Nintendo
and Sega consoles. fMSX was in the firmware until 2026-09-29 and is the same
code as then, with four more keys mapped.

The code is on the retro-go fork's branch `home-computers`. Its two
partitions (`fmsx` 704 KB, `retro-home` 1088 KB) go in the room the Nintendo 64
ports gave back; that is a change of the partition table, so a full image
write, to be approved by the user.

Licences: fMSX has its own non-commercial licence; ProSystem and the Atari800
core are GPL v2 or later; Teensy64 is GPL v3 or later, which makes the
`retro-home` app GPL v3 or later.

A tab shows in the launcher only when its app's partition is in the flash.

## On the SD card

```
/roms/a52/      Atari 5200 cartridges   .a52 .bin (8, 16 or 32 KB), or .zip
/roms/a78/      Atari 7800 cartridges   .a78 .bin, or .zip
/roms/c64/      Commodore 64 programs   .prg .d64, or .zip
/roms/msx/      MSX cartridges/disks    .rom .mx1 .mx2 .dsk

/retro-go/bios/5200.rom                 Atari 5200 BIOS, 2 KB      required
/retro-go/bios/7800 BIOS (U).rom        Atari 7800 BIOS, NTSC      optional
/retro-go/bios/7800 BIOS (E).rom        Atari 7800 BIOS, PAL       optional
/retro-go/bios/c64/kernal.rom           Commodore 64 KERNAL, 8 KB  required
/retro-go/bios/c64/basic.rom            Commodore 64 BASIC, 8 KB   required
/retro-go/bios/c64/chargen.rom          Commodore 64 characters, 4 KB  required
/retro-go/bios/msx/MSX.ROM              MSX BIOS                   required
/retro-go/bios/msx/MSX2.ROM, MSX2EXT.ROM, MSX2P.ROM, MSX2PEXT.ROM, DISK.ROM, ...  for MSX2 / 2+ / disks

/romart/<a52|a78|c64|msx>/<rom file name>.png   game covers (optional)
```

The system ROMs are not in the firmware: they belong to their makers and the
project keeps no ROM in any repository. The emulator that misses a required
one says which file and where. Covers come from the libretro thumbnail server
with `scripts/console_art.py fetch <card> <tab> <rom files...>` (the four
systems were added to it).

## Buttons

The handheld has a D-pad, A, B, X, Y, START, SELECT, L, R, MENU and OPTION.
MENU opens retro-go's game menu (save, load, quit) and OPTION its options in
every emulator.

### Atari 7800

| Button | 7800 |
|:---|:---|
| D-pad | joystick |
| A (and X) | button 1 |
| B | button 2 |
| START | console RESET: starts most games |
| SELECT | console SELECT: game variation |
| Y | console PAUSE |
| L, R | flip the left / right difficulty switch |

The BIOS is optional: without it the game starts at once, with it after the
Atari logo, as on the console. Save states work.

### Atari 5200

The 5200 controller has a stick, two fire buttons and a twelve-key keypad
with START, PAUSE and RESET; games use the keypad to choose players and
levels.

| Button | 5200 |
|:---|:---|
| D-pad | stick (full deflection) |
| A | fire (lower button) |
| B | side button (upper) |
| START | START |
| SELECT alone | PAUSE |
| X / Y | keypad 1 / 2 |
| L / R | keypad * / # |
| SELECT held + X, Y, A, B | keypad 3, 4, 5, 6 |
| SELECT held + UP, RIGHT, DOWN, LEFT | keypad 7, 8, 9, 0 |
| SELECT held + L | RESET |

Cartridges of 8, 16 and 32 KB (nearly the whole library); the bank-switched
ones (64 KB and up: "Bounty Bob Strikes Back") are not supported. No save
states.

### Commodore 64

| Button | C64 |
|:---|:---|
| D-pad | joystick, in port 2 (most games) |
| A, B | fire |
| L | swap the joystick to port 1 and back (some games read port 1) |
| START | SPACE (starts most title screens) |
| SELECT | RUN/STOP |
| X / Y | F1 / F3 (players and options in many games) |
| R | RETURN |

The options menu adds **Joystick port** (2 / 1) and **Type key**: left and
right choose a key among A–Z, 0–9, SPACE, RETURN, RUN/STOP and F1/F3/F5/F7, A
types it (several can be queued; they are typed when the menu closes).

A game starts by itself: pick a `.prg` or a `.d64` in the launcher and the
emulator waits for BASIC's `READY.`, puts the program in memory and types
`RUN` (or `SYS <address>` for a program that does not load at the start of
BASIC). Of a `.d64` it loads the first program on the disk. There is no
1541 drive: games that load more parts from the disk while they run stop
after the first part, and saving to disk is not supported. Save states work.
PAL timing (50 frames a second), SID sound through reSID at 32 kHz.

Whether it keeps 50 frames a second is the open question: reSID computes
the SID at every C64 cycle (about a million a second), on top of the video
chip drawn line by line.

### MSX

| Button | MSX |
|:---|:---|
| D-pad | joystick (or the cursor keys, see below) |
| A / B | fire A / fire B |
| X | SPACE (many games fire with it) |
| Y | RETURN |
| L | F1 (starts many games) |
| R | ESC |
| SELECT | on-screen keyboard on/off: D-pad moves, A types the key, B closes |
| START | fMSX's own menu (machine type, disks, cursor keys instead of joystick) |

## Amiga

Not in this round. The only Amiga emulator that runs on a microcontroller is
MCUME's UAE port, which needs a Teensy 4.1 (600 MHz, 2 MB chip + 4 MB fast
RAM) to run at full speed; the ESP32-S3 runs at 240 MHz and there is no
ESP32 version of it. On top of that Amiga games mostly want a mouse and a
keyboard, and the system ROM (Kickstart) is copyrighted (the free AROS
replacement runs only part of the library). It could be tried once the other
four are proven on the board, with this fork's 68000 dynamic recompiler
([68000 dynarec](m68k-dynarec)) as the way to the speed; it is a separate,
uncertain piece of work.
