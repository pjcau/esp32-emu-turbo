---
id: n64-native-ports
title: Nintendo 64 through native ports
sidebar_position: 10
---

# Nintendo 64 through native ports

There is no Nintendo 64 emulator for the ESP32-S3 and there will not be one: the
console is out of reach of this chip. Two of its games have been decompiled to
C, though, and a game compiled for the board is not emulated. That is the same
route as DOOM, Quake and Duke Nukem 3D here.

## Where we are

| Game | State (2026-10-05) |
|:---|:---|
| **Super Mario 64** | **runs on the board.** Title, demos and Peach's castle grounds were played by the user. No sound yet. Not installed: the flash has no room for it, so it is tested in the arcade app's slot and the arcade app is put back afterwards |
| **Mario Kart 64** | started the same day: the decompilation is imported, nothing builds for the board yet |

What was measured on Super Mario 64 (board, 2026-10-05; the 3D picture is drawn
at the size given and the HUD and text are always 320x240):

| Render size | Scene | Game ticks per second (30 = full speed) | Drawn frames per second |
|:---|:---|:---|:---|
| 160x120, first build | castle grounds | 28.3 | 7.4 |
| 320x240, first build | castle grounds | 14.5 | 3.6 |
| **320x240, now** | castle grounds | **30.5** | 4.1 |
| **320x240, now** | Bowser demo | **30.9** | 6.1 |

- At 320x240 the game now runs at full speed; what is left is the drawn-frame
  rate. A drawn frame costs about 230 ms in the castle grounds (rasteriser 164,
  display list 47, copy to the screen format 18).
- No crash in a 5.5-minute cycle of title and demos and a walk through the
  castle grounds. Entering the castle (a level load during play) is not tested yet.
- Internal RAM free: 80 KB (it was 1 to 4 KB in the first builds). PSRAM free:
  about 765 KB.
- Sound (2026-10-06): plays, read from the pack on the card, about 2.5 ms a
  game tick; the game stays at 30 ticks a second with it (castle grounds, 5.6
  frames drawn). Not yet judged by ear: the board tests run at volume 0.
- One hang seen once and not reproduced (after 160 s in the castle grounds, no
  log output, frozen frame; a hard reset recovered it). Cause unknown.
- App 1.6 MB, plus a 10.3 MB asset pack on the SD card.

## What was done

**Super Mario 64** (repo `pjcau/sm64-esp32`, private, submodule
`retro-go/sm64-go`). The starting point was an existing ESP32 port
(pcgamer404/retro-go-pro, itself from the FunKey port) that links every asset
into a 12 MB app. That does not fit a 16 MB flash shared with twelve other apps,
so the work was to take the assets out of the program:

1. A PC build of the port as a reference, dumping frames without a display; two
   runs give identical frames.
2. The decompilation's own segment system, switched back on: each asset segment
   (levels, actors, texture bins, skyboxes, behaviours, Mario's animations) is
   linked at its N64 segment address, kept out of the program image, and read
   from one pack file when a level asks for it. On the PC, 3000 frames (title
   and two demos) are identical to the reference, pixel for pixel, in 64-bit and
   32-bit builds.
3. The ESP32 build: the app and the segments are linked separately (they name
   each other: the app uses the assets' addresses, the assets hold the app's
   function addresses). App 11.6 MB → 1.38 MB.
4. First board run: title screen, then a crash at the first level load. The
   cause was in our own fast SD read (`rg_storage_fread_raw`), which returned
   data from the wrong place when internal RAM was too short for its buffer;
   fixed in the retro-go fork. After that the game played.

5. Speed at 320x240, measured step by step on the board with a profile line the
   app logs once a second. What moved it: drawing the sky and other white-vertex
   triangles as plain texture (the sky alone was 77 of 220 ms), and above all
   **rendering on the second core**: the game task only builds each tick's
   display list and goes on ticking, a render task draws the newest one. What
   did not: removing the per-pixel division, integer arithmetic alone, inlining,
   hand-written pixel loops (a few percent each). A benchmark run on the board
   showed why: memory was never the cost (122 ns for the depth test and both
   stores, against 1000 ns a pixel for the sky).

One command builds it from the user's ROM, in a work directory outside git:
`retro-go/sm64-go/build_esp32.sh <baserom.us.z64>` (`SM64_RENDER=WxH` for
another render size). **No ROM and no extracted asset is in any repository**; the
asset pack is built on the machine that has the ROM.

**Mario Kart 64** (repo `pjcau/mk64-esp32`, private, submodule
`retro-go/mk64-go`). Baseline: the n64decomp/mk64 decompilation, all C. Unlike
Super Mario 64 no port to a small machine exists (the PC port, SpaghettiKart, is
C++ on a GPU), so the PC layer has to be brought over from the Super Mario 64
port and the code that unpacks data for a big-endian console fixed first.

## What is left

| Item | Notes |
|:---|:---|
| Super Mario 64: more drawn frames at 320x240 (4 to 6 a second now) | writing the screen format directly (the copy is 18 ms), part of the rasteriser on the first core, which is 70 % idle |
| Super Mario 64: level loads during play (castle door, paintings) with the render task | to be tried by hand on the board |
| Super Mario 64: sound by ear | built and measured, never listened to at a normal volume |
| Super Mario 64: internal RAM | 4 KB free is too little to rely on |
| Mario Kart 64: PC build, reference frames, assets on the card, board | the plan is in the repo's README |
| Mario Kart 64 in the launcher | it will need its own partition: on the 16 MB flash that means another app set aside, or the 32 MB module ([Plan D](/docs/next-steps/plan-esp32-s3-n32r16v)) |

## In the launcher

Decided by the user on 2026-10-05, after playing it: Super Mario 64 gets a place
on the current board, in a **Nintendo 64** section of the launcher, as it is
now (320x240, no sound), to be improved afterwards. An earlier decision the same
day had been to wait for the 32 MB module; this replaces it for Super Mario 64.

- Partition `sm64-go`, 1.75 MB, binary 1.55 MB.
- The launcher tab "Nintendo 64" lists the files `*.sm64` in `/sd/roms/n64`. An
  empty file there, for example `Super Mario 64.sm64`, starts the game; its
  assets are the pack `/sd/retro-go/sm64/sm64.seg`, which must come from the
  same build as the app.
- The app is not built by `rg_tool.py` like the others, because its assets come
  from the user's ROM and stay out of git: `retro-go/sm64-go/build_esp32.sh
  <baserom.us.z64>` builds it and leaves `sm64-go/build/sm64-go.bin`, which the
  image build then takes as it is.

### Duke Nukem 3D and Quake, set aside

The 16 MB flash was full (64 KB free), so the room came from two apps the user
chose: Duke Nukem 3D (1 MB) and Quake (0.75 MB), exactly the 1.75 MB of the new
partition. The arcade game cache (`mamerom`, 4 MB) and every other app are
untouched and at the same addresses as before.

Nothing of the two was deleted:

- their sources are still in the fork (`retro-go/duke3d-go`, `retro-go/quake-go`)
  and still build: `python rg_tool.py --target=esp32-emu-turbo build duke3d-go`;
- their launcher tabs and art are still in the launcher; a tab shows only when
  its partition exists, so they are hidden, not removed;
- their game files on the SD card (`/sd/roms/duke3d`, `/sd/roms/quake`) and
  their saves are not touched.

To put them back: in `retro-go/rg_tool.py` restore the two commented lines in
`PROJECT_APPS`, add the two names to `DEFAULT_APPS`, find 1.75 MB (remove
`sm64-go`, or another app, or use the 32 MB module), build the image and flash
it. That is a full flash write, like this change was.
